# -*- coding: utf-8 -*-
"""hi_refs.py — 逐 dump 逐启用 BG 层：列出 map 引用号 >=521 的（即「窗口九宫格之上」）。

用来判：把池放到 [521,1024) 是否在所有实测层上都空。
"""
import re
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
VRAM = 0x06000000


def one(tag):
    lp, vp = T / f"drive_{tag}.log", T / f"drive_{tag}_vram.bin"
    ip = T / f"drive_{tag}_io.bin"
    if not vp.exists():
        return
    d = {}
    if ip.exists():
        ib = ip.read_bytes()
        d = {"DISPCNT": struct.unpack_from("<H", ib, 0)[0]}
        for i in range(4):
            d["BG%dCNT" % i] = struct.unpack_from("<H", ib, 0x08 + 2 * i)[0]
    elif lp.exists():
        txt = lp.read_text(encoding="utf-8", errors="replace")
        d = {m.group(1): int(m.group(2), 16)
             for m in re.finditer(r"\[io\] IO (\w+) 0x[0-9a-fA-F]+:\s*(0x[0-9a-fA-F]+)", txt)}
    if not d:
        return
    v = vp.read_bytes()
    dis = d.get("DISPCNT", 0)
    for b in range(4):
        if not ((dis >> (8 + b)) & 1):
            continue
        if b >= 2 and (dis & 7) != 0:
            continue
        cnt = d.get("BG%dCNT" % b, 0)
        cb, sb, sz = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
        hi = set()
        for i in range((32 << sz) * 32):
            o = sb * 0x800 + i * 2
            if o + 2 <= len(v):
                n = struct.unpack_from("<H", v, o)[0] & 0x3FF
                if n >= 521:
                    hi.add(n)
        if hi:
            print("  %-10s BG%d cb%d  >=521 的号: %s" % (tag, b, cb, sorted(hi)[:24]))


print("=== 所有 dump 里 map 引用 >=521 的层 ===")
for tag in sorted(p.stem.replace("drive_", "") for p in T.glob("drive_*_vram.bin")):
    try:
        one(tag)
    except Exception as e:
        print("  ", tag, "ERR", e)
