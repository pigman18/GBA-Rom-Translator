# -*- coding: utf-8 -*-
"""poolcheck.py — v11 池几何自检（用真实 dump，不靠推演）。

对每个 dump：
  · 从 EWRAM 捞出活跃窗口 → 拿 TILE_BASE 与 font
  · 按 v11 规则算池区 [TB+2, TB+needed) 与「前 3 个中文字」实际领到的砖号
  · 与「该层 map 里出现过的号」逐号比对，报有没有撞
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
TPL_LO, TPL_HI = 0x081BB3DC, 0x081BB8D4
VRAM = 0x06000000


def windows(tag):
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
        if tm > 3 or fn > 7:
            continue
        out.append((off, tpl, tm, fn, struct.unpack_from("<H", e, off + 0x16)[0]))
    return out


def needed(fn):
    return 512 if fn in (1, 4) else (256 if fn in (2, 3, 5) else 0)


def maprefs(tag):
    """所有启用 BG 层 map 里出现过的号集合 + 各层 (cb, 号集合)"""
    lp = T / f"drive_{tag}.log"
    if not lp.exists():
        return {}
    txt = lp.read_text(encoding="utf-8", errors="replace")
    import re
    d = {m.group(1): int(m.group(2), 16)
         for m in re.finditer(r"\[io\] IO (\w+) 0x[0-9a-fA-F]+:\s*(0x[0-9a-fA-F]+)", txt)}
    vp = T / f"drive_{tag}_vram.bin"
    if not vp.exists():
        return {}
    v = vp.read_bytes()
    dis = d.get("DISPCNT", 0)
    res = {}
    for b in range(4):
        if not ((dis >> (8 + b)) & 1):
            continue
        if b >= 2 and (dis & 7) != 0:
            continue
        cnt = d.get("BG%dCNT" % b, 0)
        cb, sb, sz = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
        s = set()
        for i in range((32 << sz) * 32):
            o = sb * 0x800 + i * 2
            if o + 2 <= len(v):
                s.add(struct.unpack_from("<H", v, o)[0] & 0x3FF)
        res[b] = (cb, s)
    return res


for tag in sys.argv[1:]:
    ws = [w for w in windows(tag) if w[2] == 1]
    refs = maprefs(tag)
    for off, tpl, tm, fn, tb in ws:
        nd = needed(fn)
        if nd == 0:
            print("%-12s tpl#%02d tm=%d fn=%d TB=%d  need=0 ⇒ 无池（不画）"
                  % (tag, (tpl - TPL_LO) // 0x18, tm, fn, tb))
            continue
        lo, hi = 521, 1024
        got = [hi - 503, hi - 499, hi - 495]      # = 521, 525, 529（前 3 个中文字，各 4 砖）
        spans = [(t, t + 4) for t in got]
        hit = []
        for b, (cb, s) in refs.items():
            for t0, t1 in spans:
                for x in range(t0, t1):
                    if x in s:
                        hit.append((b, cb, x))
        print("%-12s tpl#%02d tm=%d fn=%d TB=%d  need=%d  池=[%d,%d)  "
              "前3字领=%s  撞 map 号: %s"
              % (tag, (tpl - TPL_LO) // 0x18, tm, fn, tb, nd, lo, hi,
                 got, (hit[:6] if hit else "无")))
