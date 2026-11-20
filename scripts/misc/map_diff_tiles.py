"""按各 BG 的 charBase 反查差异 tile 在 tilemap 中的屏幕坐标。

用法: python scripts/misc/map_diff_tiles.py <run_dir> <frame>
"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]

OV = (RUN / "origin" / f"{FRAME}.vram.bin").read_bytes()
TV = (RUN / "translated" / f"{FRAME}.vram.bin").read_bytes()
OIO = (RUN / "origin" / f"{FRAME}.io.bin").read_bytes()
OPAL = (RUN / "origin" / f"{FRAME}.pal.bin").read_bytes()
TPAL = (RUN / "translated" / f"{FRAME}.pal.bin").read_bytes()


def u16(b, off):
    return struct.unpack_from("<H", b, off)[0]


def tile_of(vram, base_char, num):
    off = base_char + num * 32
    return vram[off:off + 32]


def main():
    diff = set()
    for off in range(0, 0x18000 - 31, 32):
        if OV[off:off + 32] != TV[off:off + 32]:
            diff.add(off)
    dispcnt = u16(OIO, 0)
    print(f"DISPCNT=0x{dispcnt:04X}  差异 tile(按 vram 偏移)={len(diff)}")
    print("  偏移示例:", [f"0x{x:05X}" for x in sorted(diff)[:20]])

    for bg in range(4):
        c = u16(OIO, 8 + bg * 2)
        if not (dispcnt & (0x100 << bg)):
            continue
        cb = ((c >> 2) & 3) * 0x4000
        sb = ((c >> 8) & 0x1F) * 0x800
        print(f"\n=== BG{bg} charBase=0x{cb:05X} screenBase=0x{sb:05X}")
        hits = 0
        for idx in range(0x400):
            t = u16(OV, sb + idx * 2)
            if not t:
                continue
            num = t & 0x3FF
            off = cb + num * 32
            if off not in diff:
                continue
            hits += 1
            x, y = idx % 32, idx // 32
            print(f"  ({x:2d},{y:2d}) idx=0x{idx:03X} tile=0x{num:03X} vram=0x{off:05X} pal={(t >> 12) & 0xF}")
        print(f"  -> 命中 {hits}")

    pal_diff = [i for i in range(256) if OPAL[i * 2:i * 2 + 2] != TPAL[i * 2:i * 2 + 2]]
    print(f"\n调色板差异项: {len(pal_diff)} -> {pal_diff[:40]}")


if __name__ == "__main__":
    main()
