# -*- coding: utf-8 -*-
"""shared.py — 验证「我们写坏的 tile 被原盘引擎的其它格子引用」。
用法: python .tmp/shared.py <tagA 我们> <tagB 原盘> <bgNo>
输出: 原盘 map 里被 >=2 格引用的号（共享号）；以及我们改过内容的号 ∩ 共享号。
"""
import re, struct, sys
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")

def io(tag):
    txt = (T / ("drive_%s.log" % tag)).read_text(encoding="utf-8", errors="replace")
    return {m.group(1): int(m.group(2), 16)
            for m in re.finditer(r"IO (\w+) 0x[0-9a-f]+:\s*(0x[0-9a-fA-F]+)", txt)}

def load(tag, n):
    v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
    c = io(tag).get("BG%dCNT" % n, 0)
    return v, ((c >> 2) & 3) * 0x4000, ((c >> 8) & 0x1F) * 0x800

def main(a, b, n):
    va, cba, sba = load(a, n)
    vb, cbb, sbb = load(b, n)
    ref = {}
    for ty in range(20):
        for tx in range(30):
            t = struct.unpack_from("<H", vb, sbb + (ty*32+tx)*2)[0] & 0x3FF
            if t:
                ref.setdefault(t, []).append((ty, tx))
    shared = {t: c for t, c in ref.items() if len(c) >= 2}
    print("原盘 BG%d 引用号 %d 个；其中被 >=2 格共享 %d 个" % (n, len(ref), len(shared)))
    changed = [t for t in ref
               if va[cba+t*32:cba+t*32+32] != vb[cbb+t*32:cbb+t*32+32]]
    print("我们改过内容的「原盘引用号」%d 个: %s" % (len(changed), sorted(changed)))
    hit = sorted(set(changed) & set(shared))
    print("⚠ 其中「原盘被 >=2 格共享」的 %d 个（= 一改就串到别处）: %s" % (len(hit), hit))
    for t in hit[:8]:
        print("   号 %3d  ← 原盘格子 %s   原内容 vs 现内容:" % (t, ref[t]))
        for r in range(8):
            x = "".join("%X" % (vb[cbb+t*32+r*4+(c>>1)] >> 4 if (c & 1)
                                else vb[cbb+t*32+r*4+(c>>1)] & 0xF) for c in range(8))
            y = "".join("%X" % (va[cba+t*32+r*4+(c>>1)] >> 4 if (c & 1)
                                else va[cba+t*32+r*4+(c>>1)] & 0xF) for c in range(8))
            print("      %s   |   %s" % (x, y))

main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
