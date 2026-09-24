# -*- coding: utf-8 -*-
"""画面放大存图 + 完整 ASCII dump（分色）。"""
import numpy as np
from PIL import Image

SHOT = r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T08-34-54-307Z-4d6b3feb.png"
OUT = r"C:\code\GBA-Rom-Translator\.tmp\an"

a = np.array(Image.open(SHOT).convert("RGB"))
g = a[54:214, 1:241]

Image.fromarray(g).resize((240 * 5, 160 * 5), Image.NEAREST).save(OUT + r"\scr_x5.png")
print("saved scr_x5.png")
