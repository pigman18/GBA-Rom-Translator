"""读 bot 帧 ram.bin 里的 TextPrinter 状态（win=0x03004170 等）。"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]

EWRAM_BASE = 0x02000000
IWRAM_BASE = 0x03000000


def load(side):
    b = (RUN / side / f"{FRAME}.ram.bin").read_bytes()
    return b


def rb(b, addr, n=1):
    if EWRAM_BASE <= addr < EWRAM_BASE + 0x40000:
        o = addr - EWRAM_BASE
    elif IWRAM_BASE <= addr < IWRAM_BASE + 0x8000:
        o = 0x40000 + (addr - IWRAM_BASE)
    else:
        return None
    return b[o:o + n]


def dump_win(b, addr, label):
    d = rb(b, addr, 0x28)
    if d is None or len(d) < 0x28:
        print(f"  {label} 越界")
        return
    u16 = lambda o: struct.unpack_from("<H", d, o)[0]
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    print(f"  {label} @0x{addr:08X}")
    print(f"    tpl=0x{u32(0x00):08X} state=0x{u16(0x04):04X} textMode=0x{d[0x0A]:02X} "
          f"fontNum=0x{d[0x0B]:02X}")
    print(f"    C={d[0x0C]:02X} D={d[0x0D]:02X} E={d[0x0E]:02X} pal={d[0x0F]:02X}")
    print(f"    textPtr=0x{u32(0x10):08X} index=0x{u16(0x14):04X} "
          f"tileBase=0x{u16(0x16):04X} tileOff=0x{u16(0x18):04X}")
    print(f"    curX={d[0x1A]:02X} curTX={d[0x1B]:02X} curY={d[0x1C]:02X} curTY={d[0x1D]:02X}")
    tpl = u32(0x00) & ~1
    td = rb(b, tpl, 0x14)
    if td:
        print(f"    tpl@0x{tpl:08X}: " + " ".join(f"{x:02X}" for x in td))


def main():
    for side in ("origin", "translated"):
        b = load(side)
        print(f"=== {side}")
        for a in (0x03004170,):
            dump_win(b, a, "statusWin")
        print()


if __name__ == "__main__":
    main()
