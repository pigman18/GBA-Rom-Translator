import numpy as np, sys
from PIL import Image
from collections import Counter
p = r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T08-34-54-307Z-4d6b3feb.png"
im = Image.open(p)
print("mode", im.mode, "size", im.size)
a = np.array(im.convert("RGB"))
print("shape", a.shape)
c = Counter(map(tuple, a.reshape(-1,3)))
print("top 12 colors:")
for col,n in c.most_common(12):
    print("   ", col, n)
