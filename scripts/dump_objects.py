#!/usr/bin/env python3
"""从「玩家坐标副本」出发，定位 object 数组，并解出所有 NPC 的坐标。

── 上一版发现 ──────────────────────────────────────────────────────────
在 gym_dewford 的帧里，玩家坐标 (8,15) 出现在 4 个地址：
  0x02025494  SaveBlock1+0x00（正本）
  0x0202549C  SaveBlock1+0x08（location 里的 x/y 区？）
  0x020254B4  SaveBlock1+0x20（lastHealLocation 的 x/y）
  0x0202955C  ← ★ 这个不在 SaveBlock1 里，很可能就是 object 结构

── 本脚本怎么做 ────────────────────────────────────────────────────────
以 0x0202955C 为锚，按候选步长（0x20/0x24/0x28/0x40）向两边扫，
把每个 slot 里「+8/+10 处的 s16 对」读出来当坐标候选，
并打印 slot 的前 16 字节，让人眼看结构。

判定「像 NPC」的标准：坐标在 0..120 之间、且不等于 (0,0)、
且 slot 开头有非 0 的 active 类标志。

用法：
  python scripts/dump_objects.py <run_dir> [帧名]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000
ANCHOR = 0x0202955C


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
    print(f"帧 {name}")

    # 玩家坐标（从 SaveBlock1 拿）
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
    print(f"玩家 = ({px},{py})  SaveBlock1=0x{sb1:08X}")

    a = off_of(ANCHOR)
    for step in (0x20, 0x24, 0x28, 0x40):
        print(f"\n=== 以 0x{ANCHOR:08X} 为锚，步长 0x{step:02X}，前后各 6 个 slot ===")
        for k in range(-6, 7):
            p = a + k * step
            if p < 0 or p + 0x14 > len(data):
                continue
            head = data[p:p + 4]
            # 试几个可能的坐标偏移
            cands = []
            for co in (0x08, 0x0A, 0x0C, 0x10):
                if p + co + 4 > len(data):
                    continue
                x = int.from_bytes(data[p + co:p + co + 2], "little", signed=True)
                y = int.from_bytes(data[p + co + 2:p + co + 4], "little", signed=True)
                if 0 < x <= 120 and 0 < y <= 120:
                    cands.append((co, x, y))
            if not cands:
                continue
            tag = ""
            for co, x, y in cands:
                if (x, y) == (px, py):
                    tag = f"  ← 玩家坐标在 +0x{co:02X}"
            print(f"  slot[{k:+2d}] 0x{addr_of(p):08X} head={head.hex(' ')}"
                  f" 候选={[(hex(c), x, y) for c, x, y in cands]}{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
