# -*- coding: utf-8 -*-
"""shot.py <tag...> — 从 dump 合成整屏（按 prio 叠 BG 层），不依赖模拟器截图。
用法: python .tmp/shot.py t_party t_bag ...
"""
import re, struct, sys
from pathlib import Path
from PIL import Image
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")

def io(tag):
    txt = (T / ("drive_%s.log" % tag)).read_text(encoding="utf-8", errors="replace")
    return {m.group(1): int(m.group(2), 16)
            for m in re.finditer(r"IO (\w+) 0x[0-9a-f]+:\s*(0x[0-9a-fA-F]+)", txt)}

def rgb555(w):
    r, g, b = w & 0x1F, (w >> 5) & 0x1F, (w >> 10) & 0x1F
    return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))

def render(tag):
    v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
    p = (T / ("drive_%s_pal.bin" % tag)).read_bytes()
    reg = io(tag)
    dc = reg.get("DISPCNT", 0x1F40)
    layers = []
    for n in range(4):
        if not ((dc >> n) & 1):
            continue
        c = reg.get("BG%dCNT" % n, 0)
        layers.append((c & 3, n, c))
    img = Image.new("RGB", (240, 160), (0, 0, 0))
    px = img.load()
    for prio, n, c in sorted(layers, key=lambda x: -x[0]):   # 低 prio = 后画 = 在前
        cb = ((c >> 2) & 3) * 0x4000
        sb = ((c >> 8) & 0x1F) * 0x800
        bpp8 = (c >> 7) & 1
        for ty in range(20):
            for tx in range(30):
                e = struct.unpack_from("<H", v, sb + (ty*32+tx)*2)[0]
                tno = e & 0x3FF
                pal = (e >> 12) & 0xF
                base = cb + tno * (64 if bpp8 else 32)
                for y in range(8):
                    for x in range(8):
                        if bpp8:
                            ci = v[base + y*8 + x]
                        else:
                            by = v[base + y*4 + (x >> 1)]
                            ci = (by >> 4) if (x & 1) else (by & 0xF)
                        if ci == 0:
                            continue
                        po = (pal*32 + ci*2) if not bpp8 else (ci*2)
                        col = rgb555(struct.unpack_from("<H", p, po)[0])
                        px[tx*8+x, ty*8+y] = col
    return img

for tag in sys.argv[1:]:
    im = render(tag)
    im.save(T / ("shot_%s.png" % tag))
    im.resize((im.width*3, im.height*3), Image.NEAREST).save(T / ("shot_%s_3x.png" % tag))
    print("shot_%s.png" % tag)
