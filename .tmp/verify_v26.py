# -*- coding: utf-8 -*-
"""verify_v26.py <tag> <bgcol_chain...> — v26「相邻两字共享尾列」的 L1 判据。
   全部真值取自 VRAM，不手抄任何字模。

   链条: slot A(phase pA) → slot B(phase pB) → ...
   校验:
     ① 槽 B 的 L 砖 px[0,pB) 必须逐像素等于槽 A 的 R 砖 px[0,pB)   ← v26 的核心不变式
     ② 同一字符出现在链上两次时，按各自 (phase) 重建出的整字必须**完全相同**
     ③ 每槽 R 砖的 px[w1,8) 必须是背景（= chs_fill_bg 清干净）
"""
import sys
import struct
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag, bg = sys.argv[1], sys.argv[2]
slots = [int(x) for x in sys.argv[3:]]          # 槽号链
LAYER = {"0": (30, 1), "2": (15, 2)}
sb, cb = LAYER[bg]

vram = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
ew = (T / ("drive_%s_ewram.bin" % tag)).read_bytes()
SLAB = 0x3E000
BASE = 352          # 域 0 基址
STRIDE = 4
BG_KEYS = 0x8


def tile(n):
    return vram[cb * 0x4000 + n * 32: cb * 0x4000 + n * 32 + 32]


def px(t, x, y):
    return (t[y * 4 + (x >> 1)] >> ((x & 1) * 4)) & 0xF


def key_of(slot):
    return struct.unpack_from("<II", ew, SLAB + BG_KEYS + slot * 8)


ok = True
info = []
for s in slots:
    lo, hi = key_of(s)
    code, lib, ink, phase = (lo >> 3) >> 8, ((lo >> 3) >> 4) & 0xF, (lo >> 3) & 0xF, lo & 7
    info.append((s, code, ink, phase, lo, hi))
    print("slot%-3d code=%04X ink=%d phase=%d hi=%08X  L=%d R=%d"
          % (s, code, ink, phase, hi, BASE + s * STRIDE, BASE + s * STRIDE + 2))

# ① 共享尾列不变式
for i in range(1, len(info)):
    _, _, _, ph, _, hi = info[i]
    if hi == 0:
        print("① slot%d phase=%d 但 hi=0（不该有溢出）" % (info[i][0], ph))
        ok = False
        continue
    a_tl = BASE + info[i - 1][0] * STRIDE
    b_tl = BASE + info[i][0] * STRIDE
    src = tile(a_tl + 2)        # 上一字的 R 砖
    dst = tile(b_tl)            # 本字的 L 砖
    diff = [(x, y) for y in range(8) for x in range(ph) if px(src, x, y) != px(dst, x, y)]
    print("① slot%d.L px[0,%d) vs slot%d.R : %s"
          % (info[i][0], ph, info[i - 1][0], "OK" if not diff else "差异 %d 处 %s" % (len(diff), diff[:6])))
    if diff:
        ok = False

# ② 重建整字：L 的 px[phase,8) ++ R 的 px[0,w1)
def glyph_of(slot, phase, ink):
    tl = BASE + slot * STRIDE
    w0 = min(8 - phase, ink)
    w1 = ink - w0
    L, R = tile(tl), tile(tl + 2)
    g = [[0] * ink for _ in range(16)]
    for y in range(8):
        for x in range(w0):
            g[y][phase + x] = 1 if px(L, x, y) >= 14 else 0
        for x in range(w1):
            g[y + 8][x] = 1 if px(R, x, y) >= 14 else 0
    return g, w0, w1


glyphs = {}
for s, code, ink, phase, _, _ in info:
    g, w0, w1 = glyph_of(s, phase, ink)
    glyphs.setdefault(code, []).append((s, phase, g, w0, w1))
    print("② slot%-3d code=%04X phase=%d 重建 w0=%d w1=%d" % (s, code, phase, w0, w1))

for code, lst in glyphs.items():
    if len(lst) < 2:
        continue
    g0 = lst[0][2]
    for s, phase, g, _, _ in lst[1:]:
        bad = [(x, y) for y in range(16) for x in range(len(g0[0]))
               if g[y][x] != g0[y][x]]
        print("② code=%04X  槽%d(p%d) vs 槽%d(p%d) 重建整字: %s"
              % (code, lst[0][0], lst[0][1], s, phase,
                 "完全一致 OK" if not bad else "差异 %d 处 %s" % (len(bad), bad[:8])))
        if bad:
            ok = False

# ③ R 砖尾列必须是背景
for s, code, ink, phase, _, _ in info:
    _, w0, w1 = glyph_of(s, phase, ink)
    R = tile(BASE + s * STRIDE + 2)
    nonbg = [(x, y) for y in range(8) for x in range(w1, 8) if px(R, x, y) >= 14]
    print("③ slot%-3d R 尾列 px[%d,8) 残留墨迹: %s" % (s, w1, "无 OK" if not nonbg else "%d 处" % len(nonbg)))
    if nonbg:
        ok = False

print("\n==== L1 判据：%s ====" % ("全部通过" if ok else "存在差异"))
sys.exit(0 if ok else 1)
