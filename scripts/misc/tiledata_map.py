"""VRAM tile-data 占用图：按 charblock 列出非空 tile 区间，并统计每 tile 的非零字节数。

用法: python scripts/misc/tiledata_map.py <run_dir> <side> <frame> <charblock>
"""
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
SIDE = sys.argv[2]
FRAME = sys.argv[3]
CB = int(sys.argv[4]) if len(sys.argv) > 4 else 0
LO = int(sys.argv[5], 0) if len(sys.argv) > 5 else 0
HI = int(sys.argv[6], 0) if len(sys.argv) > 6 else 1024

BASE = CB * 0x4000


def main():
    vram = (RUN / SIDE / f"{FRAME}.vram.bin").read_bytes()
    print(f"== {SIDE} {FRAME} charblock {CB} tiles 0x{LO:03X}..0x{HI:03X}")
    runs = []
    start = None
    for t in range(LO, HI):
        blk = vram[BASE + t * 32: BASE + t * 32 + 32]
        nz = sum(1 for b in blk if b)
        if nz and start is None:
            start = t
        elif not nz and start is not None:
            runs.append((start, t - 1))
            start = None
    if start is not None:
        runs.append((start, HI - 1))
    for a, b in runs:
        print(f"  非空 0x{a:03X}..0x{b:03X} ({b - a + 1} tiles)")
    if not runs:
        print("  （全空）")


if __name__ == "__main__":
    main()
