"""把 PNG 区域打印成 ASCII（按区域内出现频率给每个颜色分配符号）。

用法: python scripts/misc/region_ascii.py <run_dir> <frame> x0 y0 x1 y1
"""
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]
X0, Y0, X1, Y1 = (int(v) for v in sys.argv[3:7])

SYMS = "@#*+o=-:. "[::-1]


def main():
    imgs = {s: Image.open(RUN / s / f"{FRAME}.png").convert("RGB")
            for s in ("origin", "translated")}
    cnt = Counter()
    for s in imgs:
        for y in range(Y0, Y1):
            for x in range(X0, X1):
                cnt[imgs[s].getpixel((x, y))] += 1
    colors = [c for c, _ in cnt.most_common()]
    table = {c: SYMS[i % len(SYMS)] for i, c in enumerate(colors)}
    print("颜色图例:")
    for i, c in enumerate(colors):
        print(f"  {SYMS[i % len(SYMS)]} = #{c[0]:02X}{c[1]:02X}{c[2]:02X}  n={cnt[c]}")

    for s in ("origin", "translated"):
        im = imgs[s]
        print(f"\n--- {s}  x[{X0},{X1}) y[{Y0},{Y1})")
        hdr = "".join(str(x // 10 % 10) for x in range(X0, X1))
        hdr2 = "".join(str(x % 10) for x in range(X0, X1))
        print(f"        {hdr}")
        print(f"        {hdr2}")
        for y in range(Y0, Y1):
            line = "".join(table[im.getpixel((x, y))] for x in range(X0, X1))
            print(f"  y={y:3d} {line}")


if __name__ == "__main__":
    main()
