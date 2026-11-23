"""打印 BG0 状态椭圆附近所有 tile（0x150..0x162）origin/translated 对比 + 调色板 11 颜色。"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]

OV = (RUN / "origin" / f"{FRAME}.vram.bin").read_bytes()
TV = (RUN / "translated" / f"{FRAME}.vram.bin").read_bytes()
OPAL = (RUN / "origin" / f"{FRAME}.pal.bin").read_bytes()

CB = 0x4000  # BG0 charBase


def pal_rgb(idx):
    v = struct.unpack_from("<H", OPAL, idx * 2)[0]
    return ((v & 0x1F) * 255 // 31, ((v >> 5) & 0x1F) * 255 // 31,
            ((v >> 10) & 0x1F) * 255 // 31)


def tile_rows(vram, num):
    off = CB + num * 32
    t = vram[off:off + 32]
    return ["".join(f"{b & 0xF:X}{(b >> 4):X}" for b in t[r * 4:(r + 1) * 4])
            for r in range(8)]


def main():
    print("调色板 11 (BG0 状态椭圆用):")
    for i in range(16):
        r, g, b = pal_rgb(11 * 16 + i)
        print(f"  idx {i:X} = #{r:02X}{g:02X}{b:02X}")

    for num in range(0x150, 0x163):
        o = tile_rows(OV, num)
        t = tile_rows(TV, num)
        same = o == t
        print(f"\n=== tile 0x{num:03X} (vram 0x{CB + num * 32:05X}) {'SAME' if same else 'DIFF'}")
        for r in range(8):
            print(f"   O {o[r]}   T {t[r]}")


if __name__ == "__main__":
    main()
