#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""crop.py <img> <x0> <y0> <x1> <y1> <out> [scale]
Crop + nearest-neighbour upscale for pixel-level inspection.
"""
import sys, os

def main():
    if len(sys.argv) < 7:
        print("usage: crop.py <img> <x0> <y0> <x1> <y1> <out> [scale]")
        return 2
    img, x0, y0, x1, y1, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
    scale = int(sys.argv[7]) if len(sys.argv) > 7 else 4
    try:
        from PIL import Image
    except ImportError:
        print("NO_PIL")
        return 3
    im = Image.open(img)
    print("size", im.size, im.mode)
    x0 = max(0, x0); y0 = max(0, y0)
    x1 = min(im.size[0], x1); y1 = min(im.size[1], y1)
    c = im.crop((x0, y0, x1, y1))
    c = c.resize((c.size[0] * scale, c.size[1] * scale), Image.NEAREST)
    c.save(out)
    print("wrote", out, c.size)
    return 0

sys.exit(main())
