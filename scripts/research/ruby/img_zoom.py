#!/usr/bin/env python3
"""放大对比指定区域，看清字形。

用法：
    python scripts/research/ruby/img_zoom.py <png> <x0> <y0> <x1> <y1> [scale] [out]
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    if len(sys.argv) < 6:
        sys.exit("用法: img_zoom.py <png> x0 y0 x1 y1 [scale] [out]")

    from PIL import Image

    path = sys.argv[1]
    x0, y0, x1, y1 = (int(sys.argv[i]) for i in range(2, 6))
    scale = int(sys.argv[6]) if len(sys.argv) > 6 else 6
    out = sys.argv[7] if len(sys.argv) > 7 else None

    im = Image.open(path).convert("RGB")
    crop = im.crop((x0, y0, x1, y1))
    crop = crop.resize((crop.width * scale, crop.height * scale),
                       Image.NEAREST)
    if out is None:
        p = Path(path)
        out = str(p.with_name(f"{p.stem}_zoom_{x0}_{y0}_{x1}_{y1}.png"))
    crop.save(out)
    print(f"{path} 裁 x[{x0},{x1}] y[{y0},{y1}] ×{scale} → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
