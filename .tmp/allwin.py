# -*- coding: utf-8 -*-
"""allwin.py <tag> -- 扫 EWRAM 找所有 TextPrinter（模板指针落在模板表 0x081BB3DC..0x081BB8D4），
打印 tm/font/字符串指针/真实文本。"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
ew = (T / f"drive_{tag}_ewram.bin").read_bytes()
iw = (T / f"drive_{tag}_iwram.bin").read_bytes()
rom = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
EWB, IWB, RB = 0x02000000, 0x03000000, 0x08000000
TPL0, TPLN, TPLS = 0x081BB3DC, 53, 0x18


def tplidx(a):
    if TPL0 <= a < TPL0 + TPLN * TPLS and (a - TPL0) % TPLS == 0:
        return (a - TPL0) // TPLS
    return None


def rd(addr, n):
    if EWB <= addr < EWB + len(ew):
        return ew[addr - EWB:addr - EWB + n]
    if IWB <= addr < IWB + len(iw):
        return iw[addr - IWB:addr - IWB + n]
    if RB <= addr < RB + len(rom):
        return rom[addr - RB:addr - RB + n]
    return b""


def render(raw, maxn=60):
    out, i = [], 0
    while i < len(raw) and len(out) < maxn:
        b = raw[i]
        if b == 0xFF:
            out.append("|")
            break
        if b == 0x00:
            out.append("{}")
            i += 1
            continue
        if b in (0xFA, 0xFB, 0xFC, 0xFD, 0xFE):
            out.append("<%02X>" % b)
            i += 1
            continue
        if b < 0x20:
            out.append("\\%02X" % b)
            i += 1
            continue
        if i + 1 < len(raw):
            out.append("{c%04X}" % (((raw[i] << 8) | raw[i + 1])))
            i += 2
        else:
            i += 1
    return " ".join(out)


seen = []
for off in range(0, len(ew) - 0x28, 4):
    v = struct.unpack_from("<I", ew, off)[0]
    ti = tplidx(v)
    if ti is None:
        continue
    tm = ew[off + 0x0A]
    fn = ew[off + 0x0B]
    tp = struct.unpack_from("<I", ew, off + 0x10)[0]
    if not (IWB <= tp < IWB + len(iw) or RB <= tp < RB + len(rom)):
        continue
    if tm > 7 or fn > 7:
        continue
    seen.append((EWB + off, ti, tm, fn, ew[off + 0x0C], ew[off + 0x0D], ew[off + 0x0E],
                 ew[off + 0x0F], ew[off + 0x1A], ew[off + 0x1B], ew[off + 0x1C], ew[off + 0x1D], tp))

print("找到 %d 个 TextPrinter 样结构" % len(seen))
for (w, ti, tm, fn, c, d, e, pal, cx, tx, cy, ty, tp) in seen[:40]:
    print("\n@%08X tpl#%02d tm=%d fn=%d C=%d D=%d E=%d pal=%d curX=%2d tX=%2d curY=%2d tY=%2d"
          % (w, ti, tm, fn, c, d, e, pal, cx, tx, cy, ty))
    print("   str@%08X seq= %s" % (tp, render(rd(tp, 48))))
    print("   raw= %s" % rd(tp, 24).hex(" "))
