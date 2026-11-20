"""扫 RAM 找所有 TextPrinter 状结构（tpl 指向 ROM 且 textPtr 指向 ROM），
并标出正在打印 まひ 的窗口。

用法: python scripts/misc/scan_wins.py <run_dir> <frame>
"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]

EW = 0x02000000
IW = 0x03000000
EW_LEN = 0x40000
IW_LEN = 0x8000

TARGETS = {0x083DCAAF: "まひ@3DCAAF", 0x083EAE01: "まひ@3EAE01",
           0x083E9AF9: "fill@3E9AF9"}


def addr_of(off):
    if off < EW_LEN:
        return EW + off
    return IW + (off - EW_LEN)


def main():
    b = (RUN / "translated" / f"{FRAME}.ram.bin").read_bytes()
    hits = []
    for off in range(0, len(b) - 0x28, 4):
        tpl = struct.unpack_from("<I", b, off)[0] & ~1
        if not (0x08000000 <= tpl < 0x09000000):
            continue
        textptr = struct.unpack_from("<I", b, off + 0x10)[0]
        if not (0x08000000 <= textptr < 0x09000000):
            continue
        idx = struct.unpack_from("<H", b, off + 0x14)[0]
        if idx > 0x4000:
            continue
        state = struct.unpack_from("<H", b, off + 4)[0]
        if state > 0x20:
            continue
        hits.append((addr_of(off), tpl, textptr, idx, b[off:off + 0x28]))

    print(f"候选 TextPrinter 结构: {len(hits)}")
    for a, tpl, tp, idx, d in hits:
        mark = ""
        for t, name in TARGETS.items():
            if tpl == t or tp == t:
                mark = f"  <<< {name}"
        print(f"\n@0x{a:08X} tpl=0x{tpl:08X} textPtr=0x{tp:08X} idx=0x{idx:04X}{mark}")
        print("   state=0x%04X textMode=0x%02X fontNum=0x%02X C=%02X D=%02X E=%02X pal=%02X"
              % (struct.unpack_from("<H", d, 4)[0], d[0x0A], d[0x0B],
                 d[0x0C], d[0x0D], d[0x0E], d[0x0F]))
        print("   tileBase=0x%04X tileOff=0x%04X curX=%02X curTX=%02X curY=%02X curTY=%02X"
              % (struct.unpack_from("<H", d, 0x16)[0], struct.unpack_from("<H", d, 0x18)[0],
                 d[0x1A], d[0x1B], d[0x1C], d[0x1D]))


if __name__ == "__main__":
    main()
