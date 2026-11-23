"""在 VRAM 的所有 screenblock 里找包含指定 tile 号的行。

用法: python scripts/tilemap/find_tile.py <run_dir> <side> <frame> 0x1B8 [0x2C0 ...]
"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
SIDE = sys.argv[2]
FRAME = sys.argv[3]
TARGETS = [int(x, 0) for x in sys.argv[4:]]

VR = 0x06000000


def main():
    vram = (RUN / SIDE / f"{FRAME}.vram.bin").read_bytes()
    print(f"== {SIDE} {FRAME} targets={['0x%03X' % t for t in TARGETS]}")
    for sb in range(0, 32):
        base = sb * 0x800
        if base + 0x800 > len(vram):
            break
        for y in range(32):
            row = struct.unpack_from("<32H", vram, base + y * 64)
            hits = [(x, v & 0x3FF) for x, v in enumerate(row)
                    if (v & 0x3FF) in TARGETS]
            if hits:
                xs = " ".join(f"({x},0x{t:03X})" for x, t in hits)
                print(f"  sb={sb:2d} @0x{VR + base:08X} y={y:2d}: {xs}")


if __name__ == "__main__":
    main()
