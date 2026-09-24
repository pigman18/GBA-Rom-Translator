# -*- coding: utf-8 -*-
"""检查 0x86xxxxx 命中区：是不是官方日文 1bpp 字库？"""
import numpy as np
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
rom = np.fromfile(ROOT / "roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba", dtype=np.uint8)
rb = rom.tobytes(); BASE = 0x08000000

HITS = [0x854e37d, 0x86deef4, 0x86e8014, 0x86e8214, 0x86f5460, 0x8720184,
        0x87b02a3, 0x86dabca, 0x83576e3]

print("=== 命中点周边 64 字节 ===")
for h in HITS[:6]:
    o = h - BASE
    print("\n  0x%08X: %s" % (h, rb[o - 16:o + 48].hex()))

# 检查 0x86deef4 附近是否是密集字库：统计熵
for h in (0x86deef4, 0x86e8014, 0x86f5460):
    o = h - BASE
    seg = rom[o - 2048:o + 2048]
    vals, cnts = np.unique(seg, return_counts=True)
    print("\n  0x%08X 附近 4096B: 唯一值 %d, 最常见 %s"
          % (h, len(vals), sorted(zip(cnts, vals))[-4:]))

# 假设 0x86xxxxx 是 1bpp 字库：试试各种字宽，看能否解出"日"字
print("\n=== 试着把 0x86deef4 附近按 1bpp 8x8 解码（每字 8B）===")
o0 = 0x86dee00 - BASE
for g in range(24):
    b = rom[o0 + g * 8: o0 + g * 8 + 8]
    print("  g%-3d %s   %s" % (g, b.tobytes().hex(),
          "|".join("{:08b}".format(v) for v in b[:4])))
