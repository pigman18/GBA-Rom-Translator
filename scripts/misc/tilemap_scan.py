"""战斗帧 tilemap 全景：哪些 tile 号被引用、哪些 >= 0x1E8。

用法: python scripts/misc/tilemap_scan.py <run_dir> <side> <frame> <charblock> <y0> <y1>

charblock = 0..7 (0x0600C000 = charblock 3)
"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
SIDE = sys.argv[2]
FRAME = sys.argv[3]
CB = int(sys.argv[4]) if len(sys.argv) > 4 else 3
Y0 = int(sys.argv[5]) if len(sys.argv) > 5 else 32
Y1 = int(sys.argv[6]) if len(sys.argv) > 6 else 40

VR = 0x06000000
BASE = CB * 0x4000


def main():
    vram = (RUN / SIDE / f"{FRAME}.vram.bin").read_bytes()
    print(f"== {SIDE} {FRAME} charblock {CB} rows {Y0}..{Y1}")
    used = {}
    for y in range(Y0, Y1):
        row = struct.unpack_from("<32H", vram, BASE + y * 64)
        print(f"  y={y:2d}: " + " ".join(f"{v & 0x3FF:03x}" for v in row))
        for x, v in enumerate(row):
            t = v & 0x3FF
            used.setdefault(t, []).append((y, x, v >> 12))
    hi = sorted(t for t in used if t >= 0x1E0)
    print(f"  引用 tile 总数={len(used)}  max=0x{max(used):03X}")
    print(f"  >=0x1E0: " + " ".join(f"0x{t:03X}({len(used[t])})" for t in hi))
    # 每行最低/最高
    for y in range(Y0, Y1):
        row = struct.unpack_from("<32H", vram, BASE + y * 64)
        ts = [v & 0x3FF for v in row]
        print(f"    y={y:2d} min=0x{min(ts):03X} max=0x{max(ts):03X}")


if __name__ == "__main__":
    main()
