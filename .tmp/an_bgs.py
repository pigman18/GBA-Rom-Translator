# -*- coding: utf-8 -*-
"""an_bgs.py — 从 mgba_drive 的 dump 还原每一层 BG，并做「一 tile 多用」撞号检测。

用法：
    python .tmp/an_bgs.py <tag> [<tag> ...]

对每个 tag：
  · 从 .tmp/drive_<tag>.log 解析 DISPCNT / BGxCNT / BGxHOFS / BGxVOFS
  · 逐层渲染 bgview_<tag>_bgN.png（240x160，3x 放大另存）
  · 打印「同一 tile 号被 ≥2 个屏幕格引用」的清单 + 该 tile 的点阵

BGxCNT 位域： [1:0]prio  [3:2]charBase(0x4000/unit)  [7]8bpp
             [12:8]screenBase(0x800/unit)  affine/BG 相关位忽略
"""
import re
import struct
import sys
from pathlib import Path

from PIL import Image

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")


def read_io(tag):
    """从日志抓寄存器；mgba_drive 的 HOFS/VOFS 读回是坏的（8 个同值），忽略。"""
    txt = (T / ("drive_%s.log" % tag)).read_text(encoding="utf-8", errors="replace")
    reg = {}
    for m in re.finditer(r"IO (\w+) 0x[0-9a-f]+:\s*(0x[0-9a-fA-F]+)", txt):
        reg[m.group(1)] = int(m.group(2), 16)
    return reg


def rgb555(w):
    r, g, b = w & 0x1F, (w >> 5) & 0x1F, (w >> 10) & 0x1F
    return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))


class Dump:
    def __init__(self, tag):
        self.tag = tag
        self.vram = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
        self.pal = (T / ("drive_%s_pal.bin" % tag)).read_bytes()
        self.reg = read_io(tag)

    def bg(self, n):
        """返回 (charBase, screenBase, bpp8)"""
        cnt = self.reg.get("BG%dCNT" % n, 0)
        return (((cnt >> 2) & 3) * 0x4000, ((cnt >> 8) & 0x1F) * 0x800,
                (cnt >> 7) & 1, cnt)

    def map_entries(self, n):
        """yield (ty, tx, tile, bank)"""
        cb, sb, bpp8, cnt = self.bg(n)
        for ty in range(20):
            for tx in range(30):
                w = struct.unpack_from("<H", self.vram, sb + (ty * 32 + tx) * 2)[0]
                yield ty, tx, (w & 0x3FF), ((w >> 12) & 0xF), cnt

    def render(self, n, out):
        cb, sb, bpp8, _ = self.bg(n)
        im = Image.new("RGB", (240, 160), (0, 0, 0))
        px = im.load()
        for ty in range(20):
            for tx in range(30):
                w = struct.unpack_from("<H", self.vram, sb + (ty * 32 + tx) * 2)[0]
                t, bank = w & 0x3FF, (w >> 12) & 0xF
                for r in range(8):
                    for c in range(8):
                        if bpp8:
                            v = self.vram[cb + t * 64 + r * 8 + c]
                        else:
                            bb = self.vram[cb + t * 32 + r * 4 + (c >> 1)]
                            v = (bb >> 4) if (c & 1) else (bb & 0xF)
                        k = (bank * 16 + v) * 2
                        px[tx * 8 + c, ty * 8 + r] = rgb555(
                            struct.unpack_from("<H", self.pal, k)[0])
        im.save(out)
        im.resize((720, 480), Image.NEAREST).save(
            out.with_name(out.stem + "_3x.png"))
        return out

    def art(self, base, t):
        """tile 点阵（4bpp，'#' 非零 / '.' 零）"""
        rows = []
        for r in range(8):
            s = ""
            for c in range(8):
                bb = self.vram[base + t * 32 + r * 4 + (c >> 1)]
                v = (bb >> 4) if (c & 1) else (bb & 0xF)
                s += "#" if v else "."
            rows.append(s)
        return "/".join(rows)

    def nz(self, base, t):
        return sum(1 for x in self.vram[base + t * 32:base + t * 32 + 32] if x)


def collisions(d, bgno, verbose=True):
    """找「同一 tile 号出现在 ≥2 个屏幕格」的情况。"""
    cb, sb, bpp8, cnt = d.bg(bgno)
    uses = {}
    for ty, tx, t, bank, _ in d.map_entries(bgno):
        if t == 0:
            continue
        uses.setdefault(t, []).append((ty, tx, bank))
    multi = {t: v for t, v in uses.items() if len(v) >= 2}
    print("  BG%d CNT=0x%04X cb=0x%05X sb=0x%05X 4bpp=%s | 引用号 %d 个，多引用 %d 个"
          % (bgno, cnt, cb, sb, not bpp8, len(uses), len(multi)))
    if verbose:
        for t in sorted(multi):
            v = multi[t]
            print("    tile %-4d x%d  @ %s   nz=%d"
                  % (t, len(v), " ".join("r%d c%d" % (a, b) for a, b, _ in v),
                     d.nz(cb, t)))
    return multi, cb


def main(argv):
    tags = argv[1:] or ["v_bag"]
    for tag in tags:
        d = Dump(tag)
        print("=== %s  DISPCNT=0x%04X" % (tag, d.reg.get("DISPCNT", 0)))
        for n in range(4):
            cnt = d.reg.get("BG%dCNT" % n, 0)
            if not cnt:
                continue
            out = T / ("bgview_%s_bg%d.png" % (tag, n))
            d.render(n, out)
            collisions(d, n, verbose=True)


if __name__ == "__main__":
    main(sys.argv)
