# -*- coding: utf-8 -*-
"""dumpfoot.py — 对所有既有 VRAM dump：逐启用 BG 层算「引用号范围」+「该层 char 区的非零段」。

用来回答：引擎/游戏在一层里到底用到第几号砖？我方池起点 514 是否踩线？
"""
import os
import re
import struct
import sys

T = r"C:\code\GBA-Rom-Translator\.tmp"
VRAM = 0x06000000


def parse_io(tag):
    p = os.path.join(T, "drive_%s.log" % tag)
    if not os.path.exists(p):
        return None
    txt = open(p, encoding="utf-8", errors="replace").read()
    d = {}
    for m in re.finditer(r"\[io\] IO (\w+) 0x[0-9a-fA-F]+:\s*(0x[0-9a-fA-F]+)", txt):
        d[m.group(1)] = int(m.group(2), 16)
    return d or None


def runs_of(nz):
    if not nz:
        return "全零"
    out, s, p = [], nz[0], nz[0]
    for x in nz[1:]:
        if x == p + 1:
            p = x
        else:
            out.append((s, p)); s = p = x
    out.append((s, p))
    return " ".join(("%d-%d" % r) if r[0] != r[1] else str(r[0]) for r in out)


def analyze(tag):
    vp = os.path.join(T, "drive_%s_vram.bin" % tag)
    io = parse_io(tag)
    if not os.path.exists(vp) or not io:
        return
    v = open(vp, "rb").read()
    dis = io.get("DISPCNT", 0)
    print("=" * 92)
    print("%s  DISPCNT=%04X (mode%d bg%s obj%d)" %
          (tag, dis, dis & 7,
           "".join(str(b) for b in range(4) if (dis >> (8 + b)) & 1),
           (dis >> 12) & 1))
    for b in range(4):
        if not ((dis >> (8 + b)) & 1):
            continue
        cnt = io.get("BG%dCNT" % b, 0)
        cb = (cnt >> 2) & 3
        sb = (cnt >> 8) & 0x1F
        size = (cnt >> 14) & 3
        affine = (b >= 2) and ((dis & 7) != 0)
        cbase = VRAM + cb * 0x4000
        mbase = VRAM + sb * 0x800
        if affine:
            print("  BG%d cb%d map=%05X  affine（跳过 map 扫描）" % (b, cb, mbase))
            continue
        nz = [t for t in range(1024)
              if any(v[cbase - VRAM + t * 32: cbase - VRAM + t * 32 + 32])]
        ref = {}
        for ty in range(32 << size):
            for tx in range(32):
                o = mbase - VRAM + (ty * 32 + tx) * 2
                if o + 2 > len(v):
                    continue
                t = struct.unpack_from("<H", v, o)[0] & 0x3FF
                ref[t] = ref.get(t, 0) + 1
        ts = sorted(ref)
        print("  BG%d cb%d map=%05X size%d | map引用%3d号 max=%4d | cb maxnz=%4d"
              % (b, cb, mbase, size, len(ts), ts[-1] if ts else -1,
                 nz[-1] if nz else -1))
        print("      char 非零段: %s" % runs_of(nz)[:170])
        hi = [t for t in ts if t >= 500]
        print("      引用号 >=500: %s" % hi[:40])


tags = sys.argv[1:] or ["optIO", "opt", "v_opt", "nav", "navH", "v_nav",
                        "navm", "t_party", "o_party", "orgparty",
                        "o_sum2", "t_bag", "t_moves", "o_start", "t_menu"]
for t in tags:
    try:
        analyze(t)
    except Exception as e:
        print(t, "ERR", e)
