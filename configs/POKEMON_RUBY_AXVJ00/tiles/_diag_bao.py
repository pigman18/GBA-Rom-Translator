"""Diagnose red-column density on Chinese logo to find 宝 gap."""
from pathlib import Path

from PIL import Image

chs = Image.open(Path(__file__).resolve().parent / "_chs_noball.png").convert("RGBA")
bb = chs.getbbox()
assert bb
cpx = chs.load()
top0, top1 = bb[1], bb[1] + 26
cols = []
for x in range(bb[0], bb[2]):
    c = 0
    for y in range(top0, top1):
        r, g, b, a = cpx[x, y]
        if a >= 10 and r > 150 and r > g + 25 and r > b + 25:
            c += 1
    cols.append((x, c))

for x, c in cols:
    if c > 0:
        print(f"{x:3d} {c:2d} {'#' * c}")

# local minima after first peak
peak_started = False
minima = []
for i in range(2, len(cols) - 2):
    x, c = cols[i]
    if c >= 5:
        peak_started = True
    if not peak_started:
        continue
    window = [cols[j][1] for j in range(i - 2, i + 3)]
    if c <= 2 and c == min(window) and cols[i - 3][1] >= 4:
        # look ahead for another peak
        ahead = max(cols[j][1] for j in range(i + 1, min(i + 20, len(cols))))
        if ahead >= 5:
            minima.append((x, c, ahead))
print("gap candidates", minima)
