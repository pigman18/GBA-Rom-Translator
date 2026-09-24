# -*- coding: utf-8 -*-
"""menu_cmp.py - 开始菜单 BG0 文字区对比器。

读 .tmp/drive_<tag>_vram.bin，按 BG0CNT 解出 screenBase/charBase，
把菜单框区域的 tilemap 打成砖号表，并把文字区每个砖按 4bpp 渲染成 ASCII。

用法： python menu_cmp.py <tag> [--art]
"""
from __future__ import annotations
import sys
import os

ROOT = r"C:\code\GBA-Rom-Translator"
TMP = os.path.join(ROOT, ".tmp")
VRAM_BASE = 0x06000000

# 16 色 GB A 调色板（menu 用 palette bank 0xF ⇒ 0x1F0 起）
PAL_RAMP = " .:-=+*#%@"

def read_io(tag):
    p = os.path.join(TMP, "drive_%s_io.bin" % tag)
    d = open(p, "rb").read()
    return {0x04000000 + i: d[i] | (d[i + 1] << 8) for i in range(0, len(d) - 1, 2)}

def vram(tag):
    return open(os.path.join(TMP, "drive_%s_vram.bin" % tag), "rb").read()

def parse_cnt(v):
    """BGnCNT: bit0-1 prio, bit2-3 charBase block, bit4-5 mosaic, bit6-7 unused,
    bit8-12 screenBase block(2K), bit13-14 wrap, bit15 256c"""
    cb = (v >> 2) & 3
    sb = (v >> 8) & 0x1F
    return cb * 0x4000, sb * 0x800, bool(v & 0x8000)

def show_map(vr, sb_ofs, rows=30, cols=32, base_r=0, base_c=0):
    print("== BG0 tilemap @0x%08X (砖号, 高 4 bit = palette bank) ==" % (VRAM_BASE + sb_ofs))
    for r in range(base_r, base_r + rows):
        cells = []
        for c in range(base_c, base_c + cols):
            off = sb_ofs + (r * 32 + c) * 2
            t = vr[off] | (vr[off + 1] << 8)
            cells.append("%3X" % (t & 0x3FF))
        print(" r%02d | %s" % (r, " ".join(cells)))

def show_art(vr, cb_ofs, sb_ofs, r0, c0, r1, c1, pal_bin=None):
    """把 [r0..r1) x [c0..c1) 的每个砖按 4bpp 渲染成 ASCII（8px 宽/tile）。
    nibble 值直接映射密度（chs8_blit 写 fg=colC/bg=colD，非 0 即墨）。"""
    print("== 文字区 4bpp 渲染（nibble 值 → 密度）==")
    for r in range(r0, r1):
        for row in range(8):  # 每 tile 8 行
            line = []
            for c in range(c0, c1):
                moff = sb_ofs + (r * 32 + c) * 2
                t = vr[moff] | (vr[moff + 1] << 8)
                tile = t & 0x3FF
                toff = cb_ofs + tile * 32 + row * 4
                if toff + 4 > len(vr):
                    line.append(" " * 16)
                    continue
                for nib in range(4):
                    b = vr[toff + nib]
                    line.append(PAL_RAMP[min((b >> 4) * 2, len(PAL_RAMP) - 1)])
                    line.append(PAL_RAMP[min((b & 0xF) * 2, len(PAL_RAMP) - 1)])
            print("  %s" % "".join(line))
        print("")

def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "v9menu"
    do_art = "--art" in sys.argv
    try:
        io = read_io(tag)
    except FileNotFoundError:
        io = {}
    bg0 = io.get(0x04000008, 0x1F08)
    cb, sb, _ = parse_cnt(bg0)
    print("tag=%s  BG0CNT=0x%04X  charBase=0x%08X  screenBase=0x%08X"
          % (tag, bg0, VRAM_BASE + cb, VRAM_BASE + sb))
    vr = vram(tag)
    # 菜单框大约在 r2..r9（标题画面下的开始菜单），全 32 列先看整体
    show_map(vr, sb, rows=12, cols=32)
    if do_art:
        show_art(vr, cb, sb, 2, 23, 12, 31)

if __name__ == "__main__":
    main()
