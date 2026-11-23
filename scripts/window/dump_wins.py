"""扫 RAM 找所有 TextPrinter 状结构并完整打印（含 tilemap 指针、模板、文本串）。

用法: python scripts/window/dump_wins.py <run_dir> <side> <frame> [--all]

side = origin | translated
默认只打印「textPtr 指向的串前 32 字节可读」的窗口。
"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
SIDE = sys.argv[2]
FRAME = sys.argv[3]
SHOW_ALL = "--all" in sys.argv

EW = 0x02000000
IW = 0x03000000
EW_LEN = 0x40000
IW_LEN = 0x8000


def addr_of(off):
    if off < EW_LEN:
        return EW + off
    return IW + (off - EW_LEN)


def ram_read(b, addr, n):
    off = addr - EW if addr >= EW else (addr - IW + EW_LEN)
    if off < 0 or off + n > len(b):
        return None
    return b[off:off + n]


def hexs(d):
    return " ".join(f"{x:02x}" for x in d)


def main():
    b = (RUN / SIDE / f"{FRAME}.ram.bin").read_bytes()
    hits = []
    for off in range(0, len(b) - 0x28, 4):
        tpl = struct.unpack_from("<I", b, off)[0] & ~1
        if not (0x08000000 <= tpl < 0x09000000):
            continue
        textptr = struct.unpack_from("<I", b, off + 0x10)[0]
        if not (0x02000000 <= textptr < 0x04000000):
            continue
        idx = struct.unpack_from("<H", b, off + 0x14)[0]
        if idx > 0x2000:
            continue
        state = struct.unpack_from("<H", b, off + 4)[0]
        if state > 0x20:
            continue
        tb = struct.unpack_from("<H", b, off + 0x16)[0]
        to = struct.unpack_from("<H", b, off + 0x18)[0]
        if tb > 0x3FF:
            continue
        hits.append((addr_of(off), tpl, textptr, idx, tb, to, b[off:off + 0x28]))

    print(f"{SIDE} {FRAME}: 候选 TextPrinter {len(hits)} 个")
    for a, tpl, tp, idx, tb, to, d in hits:
        stream = ram_read(b, tp, 48)
        if stream is None:
            continue
        printable = sum(1 for x in stream if x not in (0xFF,))
        if not SHOW_ALL and printable == 0:
            continue
        print(f"\n@0x{a:08X} tpl=0x{tpl:08X} text=0x{tp:08X} idx=0x{idx:04X}")
        print("  state=%d tm=%d fn=%d C=%02X D=%02X E=%02X pal=%02X"
              % (struct.unpack_from("<H", d, 4)[0], d[0x0A], d[0x0B],
                 d[0x0C], d[0x0D], d[0x0E], d[0x0F]))
        print("  TB=0x%04X TOFF=0x%04X curX=%02X curTX=%02X curY=%02X curTY=%02X delay=%02X"
              % (tb, to, d[0x1A], d[0x1B], d[0x1C], d[0x1D], d[8]))
        print(f"  tpl: {hexs(ram_read(b, tpl, 16) or b'')}")
        print(f"  stream: {hexs(stream)}")
        # tilemap 指针
        tm = ram_read(b, tpl, 0x14)
        if tm and len(tm) >= 0x14:
            tmptr = struct.unpack_from("<I", tm, 0x10)[0]
            print(f"  tpl+0x10 tilemap=0x{tmptr:08X}")


if __name__ == "__main__":
    main()
