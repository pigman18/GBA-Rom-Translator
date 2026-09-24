# -*- coding: utf-8 -*-
"""cmp2.py — 左右并排对比两张 bgview（3x）"""
import sys
from pathlib import Path
from PIL import Image
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
out = T / sys.argv[1]
paths = sys.argv[2:]
ims = [Image.open(p).convert("RGB") for p in paths]
w = sum(i.width for i in ims) + 8 * (len(ims) - 1)
h = max(i.height for i in ims)
c = Image.new("RGB", (w, h), (30, 30, 30))
x = 0
for i in ims:
    c.paste(i, (x, 0)); x += i.width + 8
c.save(out)
print(out, c.size)
