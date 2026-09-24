# -*- coding: utf-8 -*-
"""决定性对比：
   ① BDF 正确字形 -> 4bpp 64B（墨=15）
   ② ROM 0x09400000 + gid*128 实际 64B
   ③ BDF 模式在 ROM 全局是否命中
"""
import numpy as np

BDF = r"C:\code\GBA-Rom-Translator\fonts\default\Middle.bdf"
ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
LIB = 0x09400000
MEDIA = 128

def parse_bdf(path):
    d, cur, enc, bb, bm, st = {}, None, None, None, [], 0
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.startswith("STARTCHAR"):
            cur, enc, bb, bm = line[10:], None, None, []
        elif line.startswith("ENCODING"):
            enc = int(line.split()[1])
        elif line.startswith("BBX"):
            bb = [int(v) for v in line.split()[1:4]]
        elif line.startswith("BITMAP"):
            st = 1
        elif line.startswith("ENDCHAR"):
            if enc is not None:
                d[enc] = (cur, bb, bm[:])
            st = 0
        elif st:
            bm.append(line)
    return d

D = parse_bdf(BDF)

def bdf_rows(bm, bb):
    return ["".join("#" if (int(h, 16) >> (bb[0] - 1 - c)) & 1 else "."
                    for c in range(bb[0])) for h in bm]

def to4bpp(rows, ink=15):
    out = bytearray()
    for r in range(16):
        s = rows[r] if r < len(rows) else "." * 16
        for c in range(0, 8, 2):
            lo = ink if s[c] == "#" else 0
            hi = ink if s[c + 1] == "#" else 0
            out.append((hi << 4) | lo)
    return bytes(out)

rom = open(ROM, "rb").read()
liboff = LIB - 0x08000000

print("ROM len = 0x%X" % len(rom))

# 已知 gid（来自前期实证）
KNOWN = {"领": 1727, "航": 995, "宝": 99, "可": 1495, "梦": 1894, "员": 3517}

for ch, gid in KNOWN.items():
    r = D.get(ord(ch))
    if not r:
        print("\n%s: BDF 未找到" % ch); continue
    rows = bdf_rows(r[2], r[1])
    want = to4bpp(rows, 15)
    got = rom[liboff + gid * MEDIA: liboff + gid * MEDIA + 64]
    print("\n=== %s  gid=%d  (BDF U+%04X) ===" % (ch, gid, ord(ch)))
    print("  want:", want.hex())
    print("  got :", got.hex())
    print("  EQUAL:", want == got)
    if want != got:
        # 灰阶容差：把 got 的任意非零 nibble 当墨
        norm = bytes(((1 if (b >> 4) else 0) << 4) | (1 if (b & 0x0F) else 0) for b in got)
        want1 = bytes(((1 if (b >> 4) else 0) << 4) | (1 if (b & 0x0F) else 0) for b in want)
        print("  EQUAL(binary):", norm == want1)
        print("  want(bin):", want1.hex())
        print("  got (bin):", norm.hex())

print("\n=== BDF「只」正确模式在 ROM 全局搜索（binary 版）===")
r = D[ord("只")]
rows = bdf_rows(r[2], r[1])
for ink in (15,):
    pat = to4bpp(rows, ink)
    hits, i = [], 0
    while True:
        i = rom.find(pat, i)
        if i < 0:
            break
        hits.append(0x08000000 + i); i += 1
    print("  ink=%d pat=%s hits=%d" % (ink, pat.hex(), len(hits)))
    for h in hits[:10]:
        print("    0x%08X  (gid if in lib: %s)" % (h, (h - LIB) // MEDIA if LIB <= h < LIB + 0xE0000 else "-"))
