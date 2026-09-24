# -*- coding: utf-8 -*-
"""gidmatch.py - 决定性诊断：v11menu 菜单区每个砖到底写了哪个字模。

对每个菜单砖 T：
  1) 与原盘同砖比较 → SAME = 引擎自烤日文（hook 没碰）
  2) nibble 是否 ⊆ {1,F} → 是 = hook 用 fg=1/bg=F 写的
  3) 把 32B 与 FontChsMiddle 每个 gid 的「上半 32B」「下半 32B」精确匹配
     （字体 nibble 0xF→1(墨), 0x0→F(空)）
输出：map 位置 / 砖号 / 归属 / 命中的 gid（及该 gid 的 ASCII 字形）
"""
from __future__ import annotations
import os

TMP = r"C:\code\GBA-Rom-Translator\.tmp"
ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
FONT_VA = 0x09400000
CB = 0x8000      # charBase block 2
SB = 0xF800      # screenBase
MAX_GID = 1200

def load(tag, suffix):
    return open(os.path.join(TMP, "drive_%s_%s.bin" % (tag, suffix)), "rb").read()

def remap_byte(b):
    hi, lo = b >> 4, b & 0xF
    if hi not in (0x0, 0xF) or lo not in (0x0, 0xF):
        return None
    return ((1 if hi else 0xF) << 4) | (1 if lo else 0xF)

def build_font_tables():
    rom = open(ROM, "rb").read()
    off = FONT_VA - 0x08000000
    up, lo = [], []
    for g in range(MAX_GID):
        base = off + g * 128
        u, l = [], []
        ok = True
        for i in range(32):
            ru = remap_byte(rom[base + i])
            rl = remap_byte(rom[base + 32 + i])
            if ru is None or rl is None:
                ok = False
                break
            u.append(ru)
            l.append(rl)
        if not ok:
            up.append(None)
            lo.append(None)
        else:
            up.append(bytes(u))
            lo.append(bytes(l))
    return up, lo

def font_art(g, half):
    """half='U' rows0-7 / 'L' rows8-15；ink(0xF)='#'"""
    rom = open(ROM, "rb").read()
    base = (FONT_VA - 0x08000000) + g * 128 + (0 if half == "U" else 32)
    out = []
    for row in range(8):
        b = rom[base + row * 4: base + row * 4 + 4]
        s = ""
        for byte in b:
            s += "#" if (byte >> 4) else "."
            s += "#" if (byte & 0xF) else "."
        out.append(s)
    return out

def main():
    v11 = load("v11menu", "vram")
    o = load("o_menu", "vram")
    up, lo = build_font_tables()
    upmap, lomap = {}, {}
    for g in range(MAX_GID):
        if up[g] is not None:
            upmap.setdefault(up[g], []).append(g)
        if lo[g] is not None:
            lomap.setdefault(lo[g], []).append(g)

    BORD = set(range(0x25B, 0x264))
    print("=== v11menu 菜单砖归属诊断（fg=1/bg=F 假设）===")
    for r in range(0, 20):
        for c in range(20, 30):
            moff = SB + (r * 32 + c) * 2
            t = v11[moff] | (v11[moff + 1] << 8)
            tile = t & 0x3FF
            if tile == 0 or tile in BORD:
                continue
            d = v11[CB + tile * 32: CB + tile * 32 + 32]
            od = o[CB + tile * 32: CB + tile * 32 + 32]
            same_as_orig = (d == od)
            nib_ok = all((x >> 4) in (1, 0xF) and (x & 0xF) in (1, 0xF) for x in d)
            tag = "原样(引擎自烤)" if same_as_orig else ("hook写" if nib_ok else "混合?")
            mu = upmap.get(bytes(d))
            ml = lomap.get(bytes(d))
            gid = None
            if mu:
                gid = ("U", mu[0])
            elif ml:
                gid = ("L", ml[0])
            gs = "%s gid=%d" % gid if gid else "无命中"
            print("  (r%02d,c%02d) T=0x%03X %-12s %s" % (r, c, tile, tag, gs))

if __name__ == "__main__":
    main()
