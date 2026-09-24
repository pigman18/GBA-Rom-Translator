# -*- coding: utf-8 -*-
"""通用 BG 层重建：从 --dump 的 vram/pal 还原指定 BG 的单独画面。
用法: python .tmp/an_bg.py <tag> [bg0 bg1 bg2 bg3]
"""
import struct
import sys
from pathlib import Path
from PIL import Image

D = Path(r"C:/code/GBA-Rom-Translator/.tmp")
GBA = 0x06000000


def rgb555(w):
    r = w & 0x1F
    g = (w >> 5) & 0x1F
    b = (w >> 10) & 0x1F
    return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))


def main():
    tag = sys.argv[1]
    which = sys.argv[2:] or ["bg0", "bg1", "bg2", "bg3"]
    vr = (D / ("drive_%s_vram.bin" % tag)).read_bytes()
    pal = (D / ("drive_%s_pal.bin" % tag)).read_bytes()

    def palcolor(bank, idx):
        return rgb555(struct.unpack_from("<H", pal, (bank * 16 + idx) * 2)[0])

    # 从截图无法拿寄存器，用 mgba 输出的已知值；这里接受 tag 对应表
    REG = {
        "party":   {"bg0": 0x1E06, "bg1": 0x0703, "bg2": 0x0F08, "bg3": 0x0602},
        "orgparty": {"bg0": 0x1E06, "bg1": 0x0703, "bg2": 0x0F08, "bg3": 0x0602},
        "h2":      {"bg0": 0x0F08},
        "org2":    {"bg0": 0x0F08},
    }[tag]

    for name in which:
        cnt = REG[name]
        cb = ((cnt >> 2) & 3) * 0x4000 - 0
        sb = ((cnt >> 8) & 0x1F) * 0x800
        bpp8 = (cnt >> 7) & 1
        im = Image.new("RGB", (240, 160), (0, 0, 0))
        px = im.load()
        for ty in range(20):
            for tx in range(30):
                w = struct.unpack_from("<H", vr, sb + (ty * 32 + tx) * 2)[0]
                n = w & 0x3FF
                bank = (w >> 12) & 0xF
                for r in range(8):
                    for c in range(8):
                        if bpp8:
                            v = vr[cb + n * 64 + r * 8 + c]
                        else:
                            b = vr[cb + n * 32 + r * 4 + (c >> 1)]
                            v = (b >> 4) if (c & 1) else (b & 0xF)
                        px[tx * 8 + c, ty * 8 + r] = palcolor(bank, v)
        out = D / ("bgview_%s_%s.png" % (tag, name))
        im.resize((240 * 3, 160 * 3), Image.NEAREST).save(out)
        print("saved", out)


main()
