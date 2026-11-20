"""在整个 VRAM 里找「文字 tile 行」：哪块 2KB 对齐的 tilemap、哪一行引用了高号 tile。

用法: python scripts/misc/find_text_rows.py <run_dir> <side> <frame> [min_tile]
"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
SIDE = sys.argv[2]
FRAME = sys.argv[3]
MIN_TILE = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0x100

VR = 0x06000000


def main():
    vram = (RUN / SIDE / f"{FRAME}.vram.bin").read_bytes()
    print(f"== {SIDE} {FRAME} min_tile=0x{MIN_TILE:X}")
    for mb in range(0, 0x10000, 0x800):
        if mb + 0x800 > len(vram):
            break
        rows = []
        for y in range(32):
            row = struct.unpack_from("<32H", vram, mb + y * 64)
            hits = [(x, v & 0x3FF) for x, v in enumerate(row) if (v & 0x3FF) >= MIN_TILE]
            if len(hits) >= 3:
                rows.append((y, hits))
        if rows:
            print(f"\n  map base 0x{VR + mb:08X}")
            for y, hits in rows:
                xs = " ".join(f"({x},0x{t:03X})" for x, t in hits[:12])
                print(f"    y={y:2d} n={len(hits):2d} {xs}")


if __name__ == "__main__":
    main()
