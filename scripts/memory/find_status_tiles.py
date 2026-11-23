"""定位队伍帧里「状态椭圆」对应的 BG tilemap 表项，并对比 origin/translated。

做法：
  1. 从 io.bin 读 DISPCNT / BGxCNT，算出各 BG 的 charBase / screenBase / 尺寸；
  2. 对 BG0/BG1 逐项扫 tilemap，找 tile 号落在 origin 有、translated 被清零的差异区；
  3. 打印这些表项的屏幕坐标，帮助定位状态椭圆。

用法: python scripts/memory/find_status_tiles.py <run_dir> <frame>
"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]

VRAM = (RUN / "origin" / f"{FRAME}.vram.bin").read_bytes()
TIO = (RUN / "translated" / f"{FRAME}.io.bin").read_bytes()
OIO = (RUN / "origin" / f"{FRAME}.io.bin").read_bytes()


def u16(b, off):
    return struct.unpack_from("<H", b, off)[0]


def bg_map(c, screen_size=0):
    char_base = (c >> 2) & 3
    screen_base = (c >> 8) & 0x1F
    return char_base, screen_base


def read_map(screen_base):
    """读 32x32 tilemap（256 项 × 2B）。"""
    addr = screen_base * 0x800
    return [u16(VRAM, addr + i * 2) for i in range(0x400)]


def main():
    dispcnt = u16(OIO, 0)
    print(f"DISPCNT=0x{dispcnt:04X}")
    for i in range(4):
        c = u16(OIO, 8 + i * 2)
        cb = (c >> 2) & 3
        sb = (c >> 8) & 0x1F
        print(f"BG{i}: CNT=0x{c:04X} charBase=0x{cb * 0x4000:05X} screenBase=0x{sb * 0x800:05X} "
              f"size={(c >> 14) & 3} on={bool(dispcnt & (0x100 << i))}")

    for bg in (0, 1, 2, 3):
        c = u16(OIO, 8 + bg * 2)
        if not (dispcnt & (0x100 << bg)):
            continue
        sb = (c >> 8) & 0x1F
        m = read_map(sb)
        used = [(i, t) for i, t in enumerate(m) if t]
        print(f"\nBG{bg} screenBase=0x{sb * 0x800:05X}: 非空表项 {len(used)}")
        # 找出 tile 号在 0x200..0x250（状态椭圆附近）的表项
        near = [(i, t) for i, t in used if 0x210 <= (t & 0x3FF) <= 0x240]
        for i, t in near[:60]:
            x, y = i % 32, i // 32
            print(f"  ({x:2d},{y:2d}) idx=0x{i:03X} tile=0x{t & 0x3FF:03X} pal={(t >> 12) & 0xF} "
                  f"flipX={(t >> 10) & 1} flipY={(t >> 11) & 1}")


if __name__ == "__main__":
    main()
