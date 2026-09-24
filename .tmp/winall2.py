# -*- coding: utf-8 -*-
"""winall2.py <tag> -- 宽松扫 EWRAM 全部「文本打印器样」结构（不要求模板在表内）。

判定字段（日版布局，见 game.h）：
  +00 tpl(u32, ROM 指针)  +0A textMode(u8)  +0B fontNum(u8)
  +10 textPtr(u32 → ROM/IWRAM)  +14 textIndex(u16 < 0x800)
  +16 TILE_BASE(u16 < 1024)  +1A CURSOR_X(u8<64) +1C CURSOR_Y(u8<64)
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
rom = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
tag = sys.argv[1]
ew = (T / f"drive_{tag}_ewram.bin").read_bytes()
iw = (T / f"drive_{tag}_iwram.bin").read_bytes()
EWB, IWB, RB = 0x02000000, 0x03000000, 0x08000000


def rd(addr, n):
    if RB <= addr < RB + len(rom):
        return rom[addr - RB:addr - RB + n]
    if IWB <= addr < IWB + len(iw):
        return iw[addr - IWB:addr - IWB + n]
    if EWB <= addr < EWB + len(ew):
        return ew[addr - EWB:addr - EWB + n]
    return b""


def jp(raw, maxn=40):
    """粗解码：>=0xFA 控制；0x01..0x1E 视为双字节前导。"""
    out, i = [], 0
    while i < len(raw) and len(out) < maxn:
        b = raw[i]
        if b == 0xFF:
            out.append("|")
            break
        if b >= 0xFA:
            out.append("<%02X %02X>" % (b, raw[i + 1] if i + 1 < len(raw) else 0))
            i += 2 if b <= 0xFE else 1
            continue
        if 0x01 <= b <= 0x1E and i + 1 < len(raw):
            out.append("%02X%02X" % (b, raw[i + 1]))
            i += 2
            continue
        if b == 0:
            out.append("00")
            i += 1
            continue
        out.append("%02X" % b)
        i += 1
    return " ".join(out)


hits = []
for off in range(0, len(ew) - 0x28):
    p = off + 0x10
    tp = struct.unpack_from("<I", ew, p)[0]
    if not (RB <= tp < RB + len(rom) or IWB <= tp < IWB + len(iw)):
        continue
    ti = struct.unpack_from("<H", ew, p + 4)[0]
    if ti > 0x800:
        continue
    tm = ew[off + 0x0A]
    fn = ew[off + 0x0B]
    if tm > 7 or fn > 7:
        continue
    tb = struct.unpack_from("<H", ew, off + 0x16)[0]
    cx, cy = ew[off + 0x1A], ew[off + 0x1C]
    if tb > 1023 or cx > 63 or cy > 63:
        continue
    tpl = struct.unpack_from("<I", ew, off)[0]
    if not (RB <= tpl < RB + len(rom)):
        continue
    hits.append((EWB + off, tpl, tm, fn, ew[off + 0x0C], ew[off + 0x0D], ew[off + 0x0E],
                 ew[off + 0x0F], tb, cx, cy, tp, ti))

print("候选 %d 个" % len(hits))
seen_tp = {}
for (w, tpl, tm, fn, c, d, e, pal, tb, cx, cy, tp, ti) in hits:
    key = (tpl, tb, cx, cy)
    s = jp(rd(tp, 40))
    print("@%08X tpl=%08X tm=%d fn=%d pal=%2d tb=%4d cx=%2d cy=%2d tp=%08X idx=%3d  %s"
          % (w, tpl, tm, fn, pal, tb, cx, cy, tp, ti, s))
    seen_tp.setdefault(tp, []).append(w)

print("\n--- 按 textPtr 分组（同一指针 = 共用一个串缓冲）---")
for tp, ws in sorted(seen_tp.items(), key=lambda kv: -len(kv[1])):
    print("%08X  x%d  %s" % (tp, len(ws), " ".join("%08X" % w for w in ws[:12])))
