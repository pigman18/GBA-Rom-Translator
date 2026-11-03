#!/usr/bin/env python3
"""扫全 RAM，把所有「像格子坐标的 s16 对」按 0x400 区块聚合，找出 object 数组。

── 思路 ────────────────────────────────────────────────────────────────
NPC 坐标在 RAM 里一定是 s16 对（x,y），值在 0..120 之间。
一帧里这样的对会有很多（地图数据里也有），但 **object 数组**的特点是：
  · 同一个 0x20~0x40 步长上连续排着 **多个** slot
  · 每个 slot 的同一偏移处都有一对合理坐标
  · 其中**有一个等于玩家坐标**

所以本脚本：对每个 4 字节对齐位置读 (s16 x, s16 y)，
若 0<x<=120 且 0<y<=120 就记账；再按 0x400 区块统计密度，
最后在密度最高的区块里按步长找「连续 N 个 slot 都有合理坐标」的起点。

用法：python scripts/scan_object_arrays.py <run_dir> [帧名]
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000


def load_frame(run: Path, key: str | None):
    side = run / "translated"
    if not side.is_dir():
        side = run / "origin"
    if key:
        for line in (side / "index.csv").read_text(encoding="utf-8", errors="replace").splitlines():
            p = line.split(",")
            if len(p) >= 4 and (p[2] == key or p[0] == key):
                f = side / f"{p[3].replace('.png', '')}.ram.bin"
                if f.is_file():
                    return f.read_bytes(), f.name
    for f in sorted(side.glob("*.ram.bin")):
        return f.read_bytes(), f.name
    return None, None


def off_of(addr: int) -> int:
    return (EWRAM_LEN + (addr - IWRAM_BASE)) if addr >= IWRAM_BASE else (addr - EWRAM_BASE)


def addr_of(off: int) -> int:
    return (IWRAM_BASE + off - EWRAM_LEN) if off >= EWRAM_LEN else (EWRAM_BASE + off)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = Path(sys.argv[1])
    key = sys.argv[2] if len(sys.argv) > 2 else None
    data, name = load_frame(run, key)
    if data is None:
        print("[ERR] 找不到 ram.bin")
        return 1

    sb1 = None
    for side in ("translated", "origin"):
        log = run / side / "scene.log"
        if log.is_file():
            m = re.search(r"sb1=0x([0-9A-Fa-f]{8})",
                          log.read_text(encoding="utf-8", errors="replace"))
            if m:
                sb1 = int(m.group(1), 16)
                break
    if sb1 is None:
        print("[ERR] 没有 sb1 地址")
        return 1
    o = off_of(sb1)
    px = int.from_bytes(data[o:o + 2], "little", signed=True)
    py = int.from_bytes(data[o + 2:o + 4], "little", signed=True)
    print(f"帧 {name}  玩家=({px},{py})  sb1=0x{sb1:08X}")

    # 1) 收集所有「合理坐标对」
    good = []
    for p in range(0, len(data) - 4, 2):
        x = int.from_bytes(data[p:p + 2], "little", signed=True)
        y = int.from_bytes(data[p + 2:p + 4], "little", signed=True)
        if 0 < x <= 120 and 0 < y <= 120:
            good.append(p)
    print(f"合理坐标对总数：{len(good)}")

    # 2) 按 0x400 区块统计
    buckets = defaultdict(int)
    for p in good:
        buckets[p // 0x400] += 1
    top = sorted(buckets.items(), key=lambda kv: -kv[1])[:8]
    print("\n密度最高的 8 个 0x400 区块：")
    for b, n in top:
        print(f"  0x{addr_of(b * 0x400):08X}..0x{addr_of(b * 0x400 + 0x3FF):08X}  {n} 对")

    # 3) 在最高密度区块里按步长找连续 slot
    print("\n在各区块里找「连续 slot 都有合理坐标」的起点：")
    goodset = set(good)
    for b, n in top[:4]:
        base = b * 0x400
        for step in (0x20, 0x24, 0x28, 0x40):
            for co in (0, 2, 4, 6, 8, 0x0A, 0x0C, 0x0E, 0x10, 0x12, 0x14):
                run_len = 0
                best = 0
                best_at = None
                for slot in range(0, 0x400 // step):
                    p = base + slot * step + co
                    if p in goodset:
                        run_len += 1
                        if run_len > best:
                            best = run_len
                            best_at = base + (slot - run_len + 1) * step + co
                    else:
                        run_len = 0
                if best >= 4:
                    # 打印这批 slot 的坐标
                    coords = []
                    for j in range(best):
                        p = best_at + j * step
                        x = int.from_bytes(data[p:p + 2], "little", signed=True)
                        y = int.from_bytes(data[p + 2:p + 4], "little", signed=True)
                        coords.append((x, y))
                    has_player = (px, py) in coords
                    print(f"  step=0x{step:02X} co=+0x{co:02X} n={best} "
                          f"@0x{addr_of(best_at):08X} "
                          f"{'★含玩家坐标' if has_player else ''}")
                    print(f"      {coords}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
