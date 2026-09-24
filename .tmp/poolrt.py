# -*- coding: utf-8 -*-
"""poolrt.py — **运行时**核查我方池所在的物理块有没有被别的 BG 层占用。

静态脚本（poolcb.py）只能按「同一函数里一起建窗的层」分组，会漏掉由别的函数
建的层、以及 8bpp（占两块）这种情形。这里直接用实机 dump 的寄存器：

  1. EWRAM 里捞 tm1 窗口 → 它的模板 → 该模板的 bg / charBase
  2. 该 bg 在 BGxCNT 里的实际 charBase（与模板互相印证）
  3. 我方池物理块 = charBase + 1
  4. 枚举**所有启用**的 BG 层，算其字模跨度：
       4bpp 文本层 → 1 块（bit7=0 且 bit6=0）
       8bpp 文本层 → 2 块（bit7=1）
       仿射层      → 2 块（恒为 8bpp）
     若有除本层外的层覆盖「我方池块」⇒ 拿别人的美术区写字，必花屏。
"""
import glob
import os
import re
import struct
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
TPL_LO, TPL_HI = 0x081BB3DC, 0x081BB8D4
VRAM = 0x06000000
BLK = 0x4000
rom = open(r"C:/code/GBA-Rom-Translator/roms/origin/POKEMON_RUBY_AXVJ00.gba", "rb").read()
RB = 0x08000000


def tmpl_cb(tpl):
    o = tpl - RB
    sb, cb, p3 = rom[o + 2], rom[o + 1], rom[o + 3]
    cnt = p3 | (sb << 8) | (cb << 2)
    return rom[o], cb, cnt


def io_of(tag):
    lp = T / f"drive_{tag}.log"
    if not lp.exists():
        return {}
    txt = lp.read_text(encoding="utf-8", errors="replace")
    return {m.group(1): int(m.group(2), 16)
            for m in re.finditer(r"\[io\] IO (\w+) 0x[0-9a-fA-F]+:\s*(0x[0-9a-fA-F]+)", txt)}


def wins_of(tag):
    p = T / f"drive_{tag}_ewram.bin"
    if not p.exists():
        return []
    e = p.read_bytes()
    out = []
    for off in range(0, len(e) - 0x28, 2):
        tpl = struct.unpack_from("<I", e, off)[0]
        if not (TPL_LO <= tpl < TPL_HI):
            continue
        tm, fn = e[off + 0x0A], e[off + 0x0B]
        if tm > 3 or fn > 7 or tm != 1:
            continue
        out.append((tpl, fn))
    return out


tags = sorted({os.path.basename(p)[len("drive_"):-len("_ewram.bin")]
               for p in glob.glob(str(T / "drive_*_ewram.bin"))})
bad = 0
checked = 0
for tag in tags:
    io = io_of(tag)
    if not io:
        continue
    d = io.get("DISPCNT", 0)
    if (d & 7) >= 3:
        continue                      # 位图模式，BG0/1 不是瓦片层
    layers = []
    for bg in range(4):
        if not (d & (0x100 << bg)):
            continue
        c = io.get("BG%dCNT" % bg)
        if c is None:
            continue
        cb = (c >> 2) & 3
        span = 2 if (c & 0x80 or c & 0x40) else 1
        layers.append((bg, cb, span, c))
    ws = wins_of(tag)
    checked += 1
    lines = []
    for tpl, fn in ws:
        bg, cb, cnt = tmpl_cb(tpl)
        real = [l for l in layers if l[0] == bg]
        cb_rt = real[0][1] if real else None
        blk = cb + 1
        pool = (bg, cb, blk)
        msg = "tm1 tpl#%02d bg%d 模板cb%d 实机cb%s ⇒ 池块%d" % (
            (tpl - TPL_LO) // 0x18, bg, cb, cb_rt if cb_rt is not None else "?", blk)
        if cb_rt is not None and cb_rt != cb:
            msg += "  [!模板/实机 cb 不一致]"
        hits = [(l[0], l[1], l[2]) for l in layers
                if l[0] != bg and l[1] <= blk < l[1] + l[2]]
        if hits:
            msg += "   !! 被 %s 覆盖" % ",".join("BG%d(cb%d,%d块)" % h for h in hits)
            bad += 1
        lines.append(msg)
    if lines:
        print("##### %-10s DISPCNT=%04X 层=%s" % (
            tag, d, ",".join("BG%d cb%d %dbpp%s" % (b, c, 8 if s == 2 else 4,
                                                   "" if x & 0x40 == 0 else "/affine")
                             for b, c, s, x in layers)))
        for m in lines:
            print("   ", m)

print()
print("有 io 的 dump 数:", checked, " 池块被覆盖的 tm1 窗口:", bad)
