"""图鉴列表跨行 tile 双重引用检测（BUG-B 可证伪判据）。

根因：tile = TB+2+(row&7)*62+col*2 只有 8 个 band，图鉴列表 11 行时
第 9~11 行 row&7 回绕到 5/6/7，与第 1~3 行同 tile，字模互相覆盖。

判据：同一 tile 被**不同屏幕行**的 tilemap 表项引用 -> dup 计数。
修复前 f043 实测 16 对（0x15F..0x16E）；修复后应为 0。

用法：python scripts/misc/dex_row_dup.py <run_dir> [frame ...]
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

TM = 0x7000   # 图鉴列表窗 tilemap（GDB 实测 tpl@0x081BB784 tilemap=0x06007000）
CB = 0x8000   # 同窗 tileData=0x06008000


def u16(b: bytes, o: int) -> int:
    return b[o] | (b[o + 1] << 8)


def ink(b: bytes, t: int) -> int:
    o = CB + (t & 0x3FF) * 32
    return sum(1 for x in b[o:o + 32] if x)


def analyze(vram: bytes) -> tuple[int, list[tuple[int, list[tuple[int, int]]]]]:
    """返回 (跨行重复的 tile 数, [(tile, [(row,col)...]), ...])"""
    own: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for row in range(32):
        for col in range(32):
            t = u16(vram, TM + (row * 32 + col) * 2) & 0x3FF
            if t and ink(vram, t) > 0:
                own[t].append((row, col))
    dups = []
    for t, cells in sorted(own.items()):
        rows = {r for r, _ in cells}
        # 只算「不同屏幕行」的重复；同一行的相邻列共用是正常的
        if len(rows) > 1:
            dups.append((t, cells))
    return len(dups), dups


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = Path(sys.argv[1])
    frames = sys.argv[2:] or ["034", "043", "052"]
    for side in ("origin", "translated"):
        print(f"===== {side} =====")
        for f in frames:
            p = run / side / f"{f}.vram.bin"
            if not p.exists():
                print(f"  f{f}: no vram dump")
                continue
            n, dups = analyze(p.read_bytes())
            print(f"  f{f}: 跨行重复 tile 数 = {n}")
            for t, cells in dups[:6]:
                print(f"      tile 0x{t:03X} -> {cells}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
