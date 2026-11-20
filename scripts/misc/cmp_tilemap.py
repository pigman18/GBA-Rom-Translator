"""对比 origin/translated 的 BG0 tilemap 表项（谁被改写、改成什么）。"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]

OV = (RUN / "origin" / f"{FRAME}.vram.bin").read_bytes()
TV = (RUN / "translated" / f"{FRAME}.vram.bin").read_bytes()
OIO = (RUN / "origin" / f"{FRAME}.io.bin").read_bytes()


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def main():
    c = u16(OIO, 8)
    SB = ((c >> 8) & 0x1F) * 0x800
    print(f"BG0 screenBase=0x{SB:05X}")
    print("对比表项 (只列不同的):")
    for idx in range(0x400):
        o = u16(OV, SB + idx * 2)
        t = u16(TV, SB + idx * 2)
        if o != t:
            x, y = idx % 32, idx // 32
            print(f"  ({x:2d},{y:2d}) origin=0x{o:04X}(tile 0x{o & 0x3FF:03X} p{o >> 12}) "
                  f"trans=0x{t:04X}(tile 0x{t & 0x3FF:03X} p{t >> 12})")


if __name__ == "__main__":
    main()
