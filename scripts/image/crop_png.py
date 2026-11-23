"""裁剪并放大 PNG 区域，便于人眼/子代理核对。

用法: python scripts/image/crop_png.py <run_dir> <frame> [x0 y0 x1 y1] [scale]
输出: <run_dir>/_crop/<frame>_<side>_<tag>.png
"""
import sys
from pathlib import Path

from PIL import Image

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]
BOX = tuple(int(v) for v in sys.argv[3:7]) if len(sys.argv) >= 7 else (0, 32, 128, 104)
SCALE = int(sys.argv[7]) if len(sys.argv) >= 8 else 4

out_dir = RUN / "_crop"
out_dir.mkdir(exist_ok=True)

for side in ("origin", "translated"):
    p = RUN / side / f"{FRAME}.png"
    im = Image.open(p).convert("RGB")
    crop = im.crop(BOX).resize(
        ((BOX[2] - BOX[0]) * SCALE, (BOX[3] - BOX[1]) * SCALE), Image.NEAREST)
    dst = out_dir / f"{FRAME}_{side}.png"
    crop.save(dst)
    print(dst)
