"""检查队伍状态椭圆：tilemap 表项 + 对应 tile 内容（origin vs translated）。

用法: python scripts/memory/status_oval.py <run_dir> <frame>
"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]

OV = (RUN / "origin" / f"{FRAME}.vram.bin").read_bytes()
TV = (RUN / "translated" / f"{FRAME}.vram.bin").read_bytes()
OIO = (RUN / "origin" / f"{FRAME}.io.bin").read_bytes()
TIO = (RUN / "translated" / f"{FRAME}.io.bin").read_bytes()


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def bg_info(io, bg):
    c = u16(io, 8 + bg * 2)
    return ((c >> 2) & 3) * 0x4000, ((c >> 8) & 0x1F) * 0x800, c


def tile_dump(vram, off):
    t = vram[off:off + 32]
    out = []
    for r in range(8):
        out.append(" ".join(f"{b:02X}" for b in t[r * 4:(r + 1) * 4]))
    return out


def main():
    print("BG 基址 (origin / translated):")
    for bg in range(4):
        print(f"  BG{bg}: origin char=0x{bg_info(OIO, bg)[0]:05X} scr=0x{bg_info(OIO, bg)[1]:05X} "
              f"| trans char=0x{bg_info(TIO, bg)[0]:05X} scr=0x{bg_info(TIO, bg)[1]:05X}")

    cb, sb, c = bg_info(OIO, 0)
    print(f"\nBG0 charBase=0x{cb:05X} screenBase=0x{sb:05X}")

    # 状态椭圆区域：屏幕 x48..71 y48..55 -> tile (6,6)-(8,6)
    for ty in (6,):
        for tx in range(5, 10):
            idx = ty * 32 + tx
            o = u16(OV, sb + idx * 2)
            t = u16(TV, sb + idx * 2)
            print(f"\n({tx},{ty}) idx=0x{idx:03X}")
            print(f"  origin tile=0x{o & 0x3FF:03X} pal={(o >> 12) & 0xF}  "
                  f"translated tile=0x{t & 0x3FF:03X} pal={(t >> 12) & 0xF}")
            for label, vram, entry in (("O", OV, o), ("T", TV, t)):
                num = entry & 0x3FF
                off = cb + num * 32
                print(f"   {label} tile 0x{num:03X} @0x{off:05X}")
                for row in tile_dump(vram, off):
                    print("     " + row)


if __name__ == "__main__":
    main()
