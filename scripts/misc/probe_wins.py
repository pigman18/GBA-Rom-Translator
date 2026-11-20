"""origin/translated 战斗帧：完整窗口 + tilemap 快照。

用法: python scripts/misc/probe_wins.py <run_dir> <side> <frame> [rows]

打印所有 TextPrinter 状结构（tpl 在 ROM、textPtr 在 RAM），以及其 tilemap
光标行附近 6 行的 tile 号，用来回答「原版把字画到哪些 tile」。
"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
SIDE = sys.argv[2]
FRAME = sys.argv[3]
ROWS = int(sys.argv[4]) if len(sys.argv) > 4 else 6

EW = 0x02000000
IW = 0x03000000
EW_LEN = 0x40000
IW_LEN = 0x8000
VR = 0x06000000
VR_LEN = 0x18000


def load(p):
    return p.read_bytes() if p.is_file() else b""


def rd(b, addr, n):
    if b is None:
        return None
    if VR <= addr < VR + VR_LEN:
        off = addr - VR
        src = b
    elif EW <= addr < EW + EW_LEN:
        off = addr - EW
        src = b
    else:
        return None
    if off + n > len(src):
        return None
    return src[off:off + n]


def hexs(d):
    return " ".join(f"{x:02x}" for x in d)


def main():
    ram = load(RUN / SIDE / f"{FRAME}.ram.bin")
    vram = load(RUN / SIDE / f"{FRAME}.vram.bin")
    print(f"== {SIDE} {FRAME} ram={len(ram)} vram={len(vram)}")
    hits = []
    for off in range(0, len(ram) - 0x28, 4):
        tpl = struct.unpack_from("<I", ram, off)[0] & ~1
        if not (0x08000000 <= tpl < 0x09000000):
            continue
        textptr = struct.unpack_from("<I", ram, off + 0x10)[0]
        if not (0x02000000 <= textptr < 0x04000000):
            continue
        idx = struct.unpack_from("<H", ram, off + 0x14)[0]
        if idx > 0x2000:
            continue
        state = struct.unpack_from("<H", ram, off + 4)[0]
        if state > 0x20:
            continue
        tb = struct.unpack_from("<H", ram, off + 0x16)[0]
        if tb > 0x3FF:
            continue
        hits.append((off, tpl, textptr, idx, tb))

    for off, tpl, textptr, idx, tb in hits:
        d = ram[off:off + 0x28]
        toff = struct.unpack_from("<H", d, 0x18)[0]
        curx, curtx, cury, curty = d[0x1A], d[0x1B], d[0x1C], d[0x1D]
        stream = rd(ram, textptr, 40) or b""
        print(f"\n@{EW + off:08X} tpl=0x{tpl:08X} text=0x{textptr:08X} idx=0x{idx:04X}")
        print("  tm=%d fn=%d TB=0x%04X TOFF=0x%04X curX=%d curTX=%d curY=%d curTY=%d C=%02X D=%02X E=%02X"
              % (d[0x0A], d[0x0B], tb, toff, curx, curtx, cury, curty, d[0x0C], d[0x0D], d[0x0E]))
        print(f"  stream: {hexs(stream)}")
        # tilemap 指针：tpl+0x10
        tp = None
        if 0x08000000 <= tpl < 0x09000000:
            # 从 ROM 读不了；但窗口结构里 +0x00 是 tpl，tilemap 在 tpl+0x10
            pass
        # 直接扫 VRAM 里含 TB 的表（前 0x400 项）
        if vram:
            ty = cury + curty
            found = 0
            for base in range(0, VR_LEN - 0x800, 0x800):
                row = struct.unpack_from("<32H", vram, base + ty * 64)
                if tb in row or (tb + 1) in row:
                    print(f"  tilemap@0x{VR + base:08X} (charblock {base // 0x4000}) rows {ty}..{ty + ROWS - 1}:")
                    for y in range(ty, ty + ROWS):
                        if base + y * 64 + 64 > len(vram):
                            break
                        r = struct.unpack_from("<32H", vram, base + y * 64)
                        print(f"    y={y:2d}: " + " ".join(f"{v & 0x3FF:03x}" for v in r))
                    found += 1
                    if found >= 1:
                        break


if __name__ == "__main__":
    main()
