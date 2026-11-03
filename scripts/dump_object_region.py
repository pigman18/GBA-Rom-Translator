#!/usr/bin/env python3
"""细查 0x03004800 附近（gObjectEvents 区域），解出 object 结构布局。

── 上一版线索 ──────────────────────────────────────────────────────────
扫全 RAM 后发现 0x03004800 区块有 31 个「合理坐标对」，
且按 step=0x24 能连续找到 4 个 slot。而符号表标 gObjectEvents=0x030048A0，
两者只差 0xA0 —— 说明 object 数组的真实起点可能在 0x03004800 附近，
而不是符号表说的 0x030048A0（日版偏移不同，这在本项目已多次出现）。

── 本脚本怎么做 ────────────────────────────────────────────────────────
把 0x03004800..0x03004980 逐 4 字节打成十六进制 + s16 解读，
人工对照「哪 4 字节像 (x,y) 格子坐标」「哪 1 字节像 active/localId」。

用法：python scripts/dump_object_region.py <run_dir> [帧名]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000
START = 0x03004800
LEN = 0x180


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
    o = off_of(sb1)
    px = int.from_bytes(data[o:o + 2], "little", signed=True)
    py = int.from_bytes(data[o + 2:o + 4], "little", signed=True)
    print(f"帧 {name}  玩家=({px},{py})")

    a = off_of(START)
    print(f"\n0x{START:08X}..0x{START + LEN:08X} 逐 4 字节：")
    print(f"{'addr':>12}  {'hex':<12} {'u8':<22} {'s16 pair'}")
    for k in range(0, LEN, 4):
        p = a + k
        if p + 4 > len(data):
            break
        b = data[p:p + 4]
        x = int.from_bytes(b[0:2], "little", signed=True)
        y = int.from_bytes(b[2:4], "little", signed=True)
        # 把「像格子坐标」的标出来
        mark = ""
        if 0 < x <= 120 and 0 < y <= 120:
            mark = "  ← 像坐标"
        if (x, y) == (px, py):
            mark = "  ★ 玩家坐标"
        u8 = " ".join(f"{v:3d}" for v in b)
        print(f"0x{START + k:08X}  {b.hex(' '):<12} {u8:<22} ({x},{y}){mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
