"""打印 PNG 指定区域的调色板索引 ASCII 图，对比 origin / translated。

用法: python scripts/image/pixel_ascii.py <run_dir> <frame> x0 y0 x1 y1
"""
import struct
import sys
from pathlib import Path

from PIL import Image

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]
X0, Y0, X1, Y1 = (int(v) for v in sys.argv[3:7])

PAL = (RUN / "origin" / f"{FRAME}.pal.bin").read_bytes()


def pal_rgb(i):
    r, g, b = struct.unpack_from("<H", PAL, i * 2)[0], 0, 0
    v = struct.unpack_from("<H", PAL, i * 2)[0]
    r = (v & 0x1F) << 3
    g = ((v >> 5) & 0x1F) << 3
    b = ((v >> 10) & 0x1F) << 3
    return r, g, b


def main():
    imgs = {}
    for side in ("origin", "translated"):
        imgs[side] = Image.open(RUN / side / f"{FRAME}.png").convert("RGB")

    # 建 rgb -> 索引 反查（用 origin 调色板）
    rev = {}
    for i in range(256):
        rev.setdefault(pal_rgb(i), i)

    for side in ("origin", "translated"):
        im = imgs[side]
        print(f"--- {side}  x[{X0},{X1}) y[{Y0},{Y1})")
        for y in range(Y0, Y1):
            line = ""
            for x in range(X0, X1):
                rgb = im.getpixel((x, y))
                idx = rev.get(rgb)
                line += "." if idx is None else f"{idx:X}"
            print(f"  y={y:3d} {line}")
        print()


if __name__ == "__main__":
    main()
