"""扫所有 BG 的 tilemap，列出引用了 tile 0x140..0x180 的表项及其屏幕坐标。"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]

OV = (RUN / "origin" / f"{FRAME}.vram.bin").read_bytes()
OIO = (RUN / "origin" / f"{FRAME}.io.bin").read_bytes()


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def main():
    dispcnt = u16(OIO, 0)
    for bg in range(4):
        c = u16(OIO, 8 + bg * 2)
        if not (dispcnt & (0x100 << bg)):
            continue
        cb = ((c >> 2) & 3) * 0x4000
        sb = ((c >> 8) & 0x1F) * 0x800
        print(f"\n=== BG{bg} CNT=0x{c:04X} charBase=0x{cb:05X} screenBase=0x{sb:05X}")
        for idx in range(0x400):
            t = u16(OV, sb + idx * 2)
            if not t:
                continue
            num = t & 0x3FF
            if 0x140 <= num <= 0x180:
                x, y = idx % 32, idx // 32
                print(f"  ({x:2d},{y:2d}) tile=0x{num:03X} pal={(t >> 12) & 0xF}")


if __name__ == "__main__":
    main()
