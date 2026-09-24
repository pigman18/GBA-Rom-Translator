# -*- coding: utf-8 -*-
"""findopt.py -- 搜 ROM 里选项菜单字符串（FC 05 09 / FC 05 0F 前缀），逐条解码。"""
from pathlib import Path

rom = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()


def dec(b, i0, maxn=24):
    out, i = [], i0
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
            if i + 1 >= len(b):
                break
            out.append("[%04X/%d]" % ((b[i] << 8) | b[i + 1], ((b[i] << 8) | b[i + 1]) & 0x1FFF))
            i += 2
    return " ".join(out)


for pat in ("fc0509", "fc050f", "fc0505", "fc0501", "fc05"):
    pb = bytes.fromhex(pat)
    hits = []
    s = 0
    while len(hits) < 30:
        k = rom.find(pb, s)
        if k < 0:
            break
        hits.append(k)
        s = k + 1
    print("=== %s : %d 处 ===" % (pat, len(hits)))
    for k in hits[:24]:
        print("  @%08X  raw=%-26s  %s"
              % (0x08000000 + k, rom[k:k + 13].hex(" "), dec(rom, k)))
    print()
