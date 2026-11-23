"""列出 BG0 charBase 内所有差异 tile（按 tile 号），并标注 tilemap 引用位置。"""
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
    c = u16(OIO, 8)          # BG0
    CB = ((c >> 2) & 3) * 0x4000
    SB = ((c >> 8) & 0x1F) * 0x800
    print(f"BG0 charBase=0x{CB:05X} screenBase=0x{SB:05X}")

    refs = {}
    for idx in range(0x400):
        t = u16(OV, SB + idx * 2)
        if t:
            refs.setdefault(t & 0x3FF, []).append((idx % 32, idx // 32, (t >> 12) & 0xF))

    changed = []
    for n in range(0, 0x400):
        off = CB + n * 32
        if OV[off:off + 32] != TV[off:off + 32]:
            changed.append(n)

    print(f"\n差异 tile: {len(changed)}")
    for n in changed:
        r = refs.get(n)
        where = ", ".join(f"({x},{y})p{p}" for x, y, p in r) if r else "**未引用**"
        print(f"  tile 0x{n:03X}  {where}")


if __name__ == "__main__":
    main()
