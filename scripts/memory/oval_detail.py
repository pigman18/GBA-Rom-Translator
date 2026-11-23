"""dump 队伍状态相关：窗口模板 0x081BB43C、tilemap 行 5..8、tile 0x150..0x166。"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ROM = (ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba").read_bytes()

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]


def rom(a, n):
    return ROM[a - 0x08000000:a - 0x08000000 + n]


print("窗口模板 0x081BB43C (WindowTemplate):")
tpl = rom(0x081BB43C, 0x14)
names = ["bg", "tilemapLeft", "tilemapTop", "width", "height", "paletteNum",
         "baseBlock", "?+7", "?+8", "?+9", "?+A", "?+B"]
for i, b in enumerate(tpl):
    print(f"  +0x{i:02X} = 0x{b:02X}")
print("  u32 +0x0C (tileData ptr) = 0x%08X" % struct.unpack_from("<I", tpl, 0x0C)[0])
print("  u32 +0x10 (tilemap  ptr) = 0x%08X" % struct.unpack_from("<I", tpl, 0x10)[0])

OV = (RUN / "origin" / f"{FRAME}.vram.bin").read_bytes()
TV = (RUN / "translated" / f"{FRAME}.vram.bin").read_bytes()
OIO = (RUN / "origin" / f"{FRAME}.io.bin").read_bytes()


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


c = u16(OIO, 8)  # BG0
CB = ((c >> 2) & 3) * 0x4000
SB = ((c >> 8) & 0x1F) * 0x800
print(f"\nBG0 charBase=0x{CB:05X} screenBase=0x{SB:05X}")

print("\ntilemap (x=4..11, y=5..8):")
print("      " + "".join(f"x{x:<7d}" for x in range(4, 12)))
for y in range(5, 9):
    row = []
    for x in range(4, 12):
        t = u16(OV, SB + (y * 32 + x) * 2)
        row.append(f"{t & 0x3FF:03X}/p{(t >> 12) & 0xF} ")
    print(f"  y={y}: " + "".join(row))

print("\ntile 内容 (origin | translated)，CB=0x%05X" % CB)
for num in range(0x150, 0x167):
    off = CB + num * 32
    o = OV[off:off + 32]
    t = TV[off:off + 32]
    mark = "SAME" if o == t else "DIFF"
    print(f"\n  tile 0x{num:03X}  {mark}")
    for r in range(8):
        oo = "".join(f"{b & 0xF:X}{(b >> 4):X}" for b in o[r * 4:(r + 1) * 4])
        tt = "".join(f"{b & 0xF:X}{(b >> 4):X}" for b in t[r * 4:(r + 1) * 4])
        print(f"    O {oo}   T {tt}")
