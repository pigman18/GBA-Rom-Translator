# -*- coding: utf-8 -*-
"""ab.py — 两个 dump 的同一 BG 层做 map + tile 内容 A/B 对照。

用法: python .tmp/ab.py <tagA> <tagB> [bgNo ...]
      A = 我们的 ROM，B = 原盘。
每个 BG 打印：map 差异格（含号）、号集合差异、被引用号的内容差异。
"""
import re
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")


def read_io(tag):
    txt = (T / ("drive_%s.log" % tag)).read_text(encoding="utf-8", errors="replace")
    reg = {}
    for m in re.finditer(r"IO (\w+) 0x[0-9a-f]+:\s*(0x[0-9a-fA-F]+)", txt):
        reg[m.group(1)] = int(m.group(2), 16)
    return reg


class D:
    def __init__(self, tag):
        self.tag = tag
        self.vram = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
        self.reg = read_io(tag)

    def bg(self, n):
        c = self.reg.get("BG%dCNT" % n, 0)
        return (((c >> 2) & 3) * 0x4000, ((c >> 8) & 0x1F) * 0x800, (c >> 7) & 1, c)

    def art(self, cb, t):
        out = []
        for r in range(8):
            s = ""
            for c in range(8):
                bb = self.vram[cb + t * 32 + r * 4 + (c >> 1)]
                v = (bb >> 4) if (c & 1) else (bb & 0xF)
                s += "." if v == 0 else ("%X" % v)
            out.append(s)
        return "/".join(out)


def main(a_tag, b_tag, bgs):
    A, B = D(a_tag), D(b_tag)
    for n in bgs:
        cbA, sbA, _, cntA = A.bg(n)
        cbB, sbB, _, cntB = B.bg(n)
        print("=== BG%d  A(%s) cnt=%04X cb=%05X sb=%05X | B(%s) cnt=%04X cb=%05X sb=%05X"
              % (n, a_tag, cntA, cbA, sbA, b_tag, cntB, cbB, sbB))
        if (cntA & 0x1F07) != (cntB & 0x1F07):
            print("   ⚠ BG 配置不同，跳过")
            continue
        ma, mb, na, nb = {}, {}, set(), set()
        for ty in range(20):
            for tx in range(30):
                wa = struct.unpack_from("<H", A.vram, sbA + (ty * 32 + tx) * 2)[0]
                wb = struct.unpack_from("<H", B.vram, sbB + (ty * 32 + tx) * 2)[0]
                ma[(ty, tx)] = wa & 0x3FF
                mb[(ty, tx)] = wb & 0x3FF
                na.add(wa & 0x3FF)
                nb.add(wb & 0x3FF)
        diff = [(k, ma[k], mb[k]) for k in ma if ma[k] != mb[k]]
        print("   map 差异格 %d/%d" % (len(diff), len(ma)))
        # 只打印「非零 → 不同非零」的，按行分组
        byrow = {}
        for (ty, tx), x, y in diff:
            byrow.setdefault(ty, []).append((tx, x, y))
        for ty in sorted(byrow):
            print("     r%-2d " % ty + "  ".join("c%d:%d>%d" % v for v in byrow[ty]))
        only_a = sorted(x for x in na - nb if x)
        only_b = sorted(x for x in nb - na if x)
        print("   仅 A 引用号 %s" % (only_a[:60],))
        print("   仅 B 引用号 %s" % (only_b[:60],))
        # 相同号的 tile 内容差异
        same = sorted((na & nb) - {0})
        td = [t for t in same
              if A.vram[cbA + t * 32:cbA + t * 32 + 32]
              != B.vram[cbB + t * 32:cbB + t * 32 + 32]]
        print("   同号但内容不同的 tile %d 个: %s" % (len(td), td[:40]))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], [int(x) for x in a[2:]] or [0, 1, 2, 3])
