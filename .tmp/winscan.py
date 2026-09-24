# -*- coding: utf-8 -*-
"""winscan.py <tag> <tplhex> -- 扫 EWRAM 找出所有用该模板的窗口，跟随字符串指针打文本。"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
tpl = int(sys.argv[2], 16)
ew = (T / f"drive_{tag}_ewram.bin").read_bytes()
iw = (T / f"drive_{tag}_iwram.bin").read_bytes()
rom = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
EWB, IWB, RB = 0x02000000, 0x03000000, 0x08000000


def rd(addr, n):
    if EWB <= addr < EWB + len(ew):
        return ew[addr - EWB:addr - EWB + n]
    if IWB <= addr < IWB + len(iw):
        return iw[addr - IWB:addr - IWB + n]
    if RB <= addr < RB + len(rom):
        return rom[addr - RB:addr - RB + n]
    return b""


def render(raw, maxlen=80):
    out, i = [], 0
    while i < len(raw) and len(out) < maxlen:
        b = raw[i]
        if b == 0xFF:
            out.append("<END>")
            break
        if b == 0x00:
            out.append("{}")
            i += 1
            continue
        if b in (0xFA, 0xFB, 0xFC, 0xFE):
            out.append("<%02X>" % b)
            i += 1
            continue
        if b < 0x20:
            out.append("\\%02X" % b)
            i += 1
            continue
        if i + 1 < len(raw):
            code = (raw[i] << 8) | raw[i + 1]
            out.append("{%04X|%d}" % (code, code & 0x1FFF))
            i += 2
        else:
            out.append("%02X" % b)
            i += 1
    return " ".join(out)


hits = []
for off in range(0, len(ew) - 0x28, 4):
    v = struct.unpack_from("<I", ew, off)[0]
    if v == tpl:
        hits.append(EWB + off)
print("tpl=%08X 命中 %d 个窗口" % (tpl, len(hits)))
for w in hits[:24]:
    o = w - EWB
    tm = ew[o + 0x0A] & 0xFF
    fn = ew[o + 0x0B]
    c, d, e = ew[o + 0x0C], ew[o + 0x0D], ew[o + 0x0E]
    pal = ew[o + 0x0F]
    tp = struct.unpack_from("<I", ew, o + 0x10)[0]
    idx = struct.unpack_from("<H", ew, o + 0x14)[0]
    cx = ew[o + 0x1A]
    tx = ew[o + 0x1B]
    cy = ew[o + 0x1C]
    ty = ew[o + 0x1D]
    print("\n@%08X tm=%d fn=%d C=%d D=%d E=%d pal=%d curX=%d tX=%d curY=%d tY=%d idx=%d"
          % (w, tm, fn, c, d, e, pal, cx, tx, cy, ty, idx))
    print("   str@%08X raw=%s" % (tp, rd(tp, 24).hex(" ") if tp else "-"))
    print("   seq=", render(rd(tp, 40)) if tp else "-")
