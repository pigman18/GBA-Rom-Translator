# -*- coding: utf-8 -*-
"""findstr.py -- 在成品 ROM 里搜字节序列，打印命中处及其所在字符串（解码 2 字节汉字）。"""
import sys
from pathlib import Path

rom = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()


def dec(b, maxn=60):
    out, i = [], 0
    while i < len(b) and len(out) < maxn:
        c = b[i]
        if c == 0xFF:
            out.append("|END")
            break
        if c == 0x00:
            out.append("{}")
            i += 1
        elif c in (0xFA, 0xFB, 0xFC, 0xFD, 0xFE):
            out.append("<%02X>" % c)
            i += 1
        elif c < 0x20:
            out.append("\\%02X" % c)
            i += 1
        else:
            out.append("[%04X]" % ((b[i] << 8) | b[i + 1]))
            i += 2
    return " ".join(out)


pats = sys.argv[1:]
for p in pats:
    pb = bytes.fromhex(p)
    hits = []
    start = 0
    while True:
        k = rom.find(pb, start)
        if k < 0:
            break
        hits.append(k)
        start = k + 1
        if len(hits) > 40:
            break
    print("=== 模式 %s  命中 %d 处 ===" % (p, len(hits)))
    for k in hits[:16]:
        s = max(0, k - 12)
        print("  @%08X  ...%s" % (0x08000000 + k, dec(rom[s:k + 24])))
    print()
