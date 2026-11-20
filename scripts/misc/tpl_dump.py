"""读 ROM 里的窗口模板（16 字节），打印 tileData/tilemap 指针。

用法: python scripts/misc/tpl_dump.py 0x081BB3F4 [more...]
"""
import struct
import sys
from pathlib import Path

ROM = Path(r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba")


def main():
    rom = ROM.read_bytes()
    for a in sys.argv[1:]:
        addr = int(a, 0) & ~1
        off = addr - 0x08000000
        d = rom[off:off + 0x14]
        print(f"tpl @0x{addr:08X}: {d.hex(' ')}")
        if len(d) >= 0x14:
            pal, fg, bg, sh, fn, tm = d[4], d[5], d[6], d[7], d[8], d[9]
            tdata = struct.unpack_from("<I", d, 0x0C)[0]
            tmap = struct.unpack_from("<I", d, 0x10)[0]
            print(f"  pal={pal} fg={fg} bg={bg} shadow={sh} fontNum={fn} textMode={tm} "
                  f"tileData=0x{tdata:08X} tilemap=0x{tmap:08X}")


if __name__ == "__main__":
    main()
