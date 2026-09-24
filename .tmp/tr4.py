# -*- coding: utf-8 -*-
"""tr4.py <tag...> — 按窗口聚合 CHS_TRACE 环形记录"""
import struct, sys, re
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
for tag in sys.argv[1:]:
    ew = (T / ("drive_%s_ewram.bin" % tag)).read_bytes()
    base = ew.find(b"ADX2")
    if base < 0:
        print("%s: NO TRACE" % tag); continue
    w = struct.unpack_from("<2048I", ew, base)
    print("=== %s  magic@%05X calls=%d ring=%d win_uniq=%d dup=%d" % (tag, base, w[1], w[2], w[3], w[4]))
    wt = {}
    for i in range(24):
        o = 8+i*8
        win, tpl, tdata, mp, cnt, tb, cxcy, _ = w[o:o+8]
        if win: wt[win] = (tpl, tdata, mp, cnt, tb, cxcy&0xFF, (cxcy>>8)&0xFF)
    for win, v in wt.items():
        print("   WIN %08X tpl=%08X tdata=%08X map=%08X cnt=%3d TB=%d CUR=(%d,%d)"
              % (win, v[0], v[1], v[2], v[3], v[4], v[5], v[6]))
    agg = {}
    n = min(w[2], 256)
    for i in range(n):
        o = 200+i*5
        a,b,c,d,e = w[o:o+5]
        cx=b&0xFF; cy=(b>>8)&0xFF
        off=(c>>16)&0xFFFF
        tm=(e>>16)&0xFF; ch=(e>>24)&0xFF
        k=(a, tm)
        g = agg.setdefault(k, {"n":0,"off":[],"cx":set(),"cy":set()})
        g["n"] += 1
        if len(g["off"])<8: g["off"].append(off)
        g["cx"].add(cx); g["cy"].add(cy)
    for (win, tm), g in sorted(agg.items(), key=lambda x:-x[1]["n"]):
        v = wt.get(win, (0,0,0,0,0,0,0))
        print("   win=%08X tm=%d n=%3d tdata=%08X map=%08X TB=%d off=%s cx=%s cy=%s"
              % (win, tm, g["n"], v[1], v[2], v[4], g["off"], sorted(g["cx"]), sorted(g["cy"])))
