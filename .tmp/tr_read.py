# -*- coding: utf-8 -*-
"""tr_read.py — 解析 CHS_TRACE 采样块（EWRAM @0x0203C000）。

用法: python .tmp/tr_read.py <tag> [--raw]
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
ADDR = 0x0203C000
EWRAM_FOFF = ADDR - 0x02000000
MAGIC = 0x32584441

TR_WORDS = 2048
TR_HDR = 8
TR_TBL_W = 8
TR_TBL_N = 24
TR_REC_W = 5
TR_RING_W = TR_HDR + TR_TBL_W * TR_TBL_N      # 200
TR_RING_N = 256


def load(tag):
    e = (T / ("drive_%s_ewram.bin" % tag)).read_bytes()
    w = list(struct.unpack_from("<%dI" % TR_WORDS, e, EWRAM_FOFF))
    return w


def main(tag, raw=False):
    w = load(tag)
    print("== %s  magic=%08X %s" % (tag, w[0], "OK" if w[0] == MAGIC else "NO-MAGIC"))
    if w[0] != MAGIC:
        print("   glyph_calls=%d ring=%d：" % (w[1], w[2]))
        # 尝试直接给出前 32 个非零 word
        print("   前 32 word:", " ".join("%08X" % x for x in w[:32]))
        return
    print("   glyph_calls=%d  ring=%d  win_uniq=%d  dup=%d"
          % (w[1], w[2], w[3], w[4]))

    print("   --- 窗口表 (win, tpl, tileData, map, count, tb, cx/cy) ---")
    for i in range(TR_TBL_N):
        o = TR_HDR + i * TR_TBL_W
        if w[o] == 0:
            continue
        print("   [%2d] win=%08X tpl=%08X tdata=%08X map=%08X n=%-6d tb=%d cx=%d cy=%d"
              % (i, w[o], w[o + 1], w[o + 2], w[o + 3], w[o + 4],
                 w[o + 5], w[o + 6] & 0xFF, (w[o + 6] >> 8) & 0xFF))

    n = min(w[2], TR_RING_N)
    print("   --- 环形 %d 条 ---" % n)
    print("   %-4s %-8s %-4s %-4s %-4s %-4s %-4s %-6s %-6s %-5s %-4s %-3s %-3s %-4s"
          % ("#", "win", "cx", "cy", "ctx", "cty", "tb", "off", "t0", "t1",
             "phs", "adv", "tm", "ch"))
    for k in range(n):
        o = TR_RING_W + k * TR_REC_W
        win, a, b, c, d = w[o:o + TR_REC_W]
        cx, cy = a & 0xFF, (a >> 8) & 0xFF
        ctx, cty = (a >> 16) & 0xFF, (a >> 24) & 0xFF
        tb, off = b & 0xFFFF, (b >> 16) & 0xFFFF
        t0, t1 = c & 0xFFFF, (c >> 16) & 0xFFFF
        phs, adv, tm, ch = d & 0xFF, (d >> 8) & 0xFF, (d >> 16) & 0xFF, (d >> 24) & 0xFF
        bb = ((cy >> 1) * 64 + cx * 2)
        print("   %-4d %-8X %-4d %-4d %-4d %-4d %-4d %-6d %-6d %-5d %-4d %-3d %-3d 0x%02X"
              % (k, win, cx, cy, ctx, cty, tb, off, t0, t1, phs, adv, tm, ch))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0] if a else "t_bag", "--raw" in a)
