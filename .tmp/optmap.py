# -*- coding: utf-8 -*-
"""optmap.py — 设置页 BG0 的 tilemap 引用了哪些砖号（尤其 >=512）。

设置页（drive_optIO）: DISPCNT=0x7140, BG0CNT=0x0f08 → cb2, sb15, size0, 4bpp
BG0 char 区 = 0x06008000 .. 0x06010000（tile 0..1023）
我方池(chs cb2 层) = 0x0600C040..0x06010000  ⇒ 对应 cb2 tile 514..1023
"""
import os
import struct
from collections import Counter

T = r"C:\code\GBA-Rom-Translator\.tmp"
VRAM = 0x06000000

for tag in ("optIO", "opt", "v_opt"):
    vp = os.path.join(T, "drive_%s_vram.bin" % tag)
    if not os.path.exists(vp):
        print(tag, "MISSING");  continue
    v = open(vp, "rb").read()
    print("=" * 78)
    print("=== %s  vram=%d ===" % (tag, len(v)))

    cnts = {"optIO": 0x0f08, "opt": 0x0f08, "v_opt": None}
    if tag == "v_opt":
        # 从日志抓
        lg = open(os.path.join(T, "drive_v_opt.log"), encoding="utf-8",
                  errors="replace").read()
        import re
        m = re.search(r"BG0CNT 0x4000008:\s*(0x[0-9a-fA-F]+)", lg)
        cnts["v_opt"] = int(m.group(1), 16) if m else 0x0f08
    cnt = cnts[tag]
    cb = (cnt >> 2) & 3
    sb = (cnt >> 8) & 0x1F
    size = (cnt >> 14) & 3
    cbase = VRAM + cb * 0x4000
    mbase = VRAM + sb * 0x800
    print("BG0CNT=0x%04X  cb=%d(char=%05X)  sb=%d(map=%05X)  size=%d"
          % (cnt, cb, cbase, sb, mbase, size))

    w = h = 32 << size
    ref = Counter()
    for ty in range(min(h, 32)):
        for tx in range(min(w, 32)):
            o = (mbase - VRAM) + (ty * 32 + tx) * 2
            e = struct.unpack_from("<H", v, o)[0]
            ref[e & 0x3FF] += 1
    ts = sorted(ref)
    print("  引用号 %d 个  min=%d max=%d" % (len(ts), ts[0], ts[-1]))
    # 分布
    lo = [t for t in ts if t < 512]
    hi = [t for t in ts if t >= 512]
    print("  <512 : %d 个 (max %s)" % (len(lo), lo[-1] if lo else "-"))
    print("  >=512: %d 个  %s" % (len(hi), hi[:40]))
    print("  共享号(>=2格引用):",
          sorted([t for t, c in ref.items() if c >= 2])[:40])

    # 各 char 块非零 tile 段
    for blk in range(6):
        b = blk * 0x4000
        if b + 0x4000 > len(v):
            break
        nz = [t for t in range(1024)
              if any(v[b + t * 32: b + t * 32 + 32])]
        if not nz:
            print("  cb%d @%05X: 全零" % (blk, VRAM + b));  continue
        runs, s, p = [], nz[0], nz[0]
        for x in nz[1:]:
            if x == p + 1:
                p = x
            else:
                runs.append((s, p)); s = p = x
        runs.append((s, p))
        rs = " ".join(("%d-%d" % r) if r[0] != r[1] else str(r[0]) for r in runs)
        print("  cb%d @%05X: nz=%4d max=%4d 段: %s"
              % (blk, VRAM + b, len(nz), nz[-1], rs[:150]))
