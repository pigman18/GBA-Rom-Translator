# -*- coding: utf-8 -*-
"""定位「普通」的「通」缺左半：用 BDF 真值复算期望 tile，与实机 dump 逐格比对。

真值来源：
  · BDF        fonts/default/Normal.bdf（ink_fixed 11x11+0+2）
  · 实机 dump  .tmp/drive_h2_vram.bin（BG0CNT 0x0F08 → charBase 0x8000 / screenBase 0x7800）
零手抄：几何/掩码表全部复用 scripts/verify_plan4.py 的复刻原语。
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_plan4 as V  # noqa: E402  （复刻 blend/extract/chs_cell_from_1bpp）

D = ROOT / ".tmp"
VRAM = (D / "drive_h2_vram.bin").read_bytes()
CHR = 0x06008000 - 0x06000000
SCR = 0x06007800 - 0x06000000

BDF = V.parse_bdf(ROOT / "fonts/default/Normal.bdf")


def own(ch):
    return V.chs_cell_from_1bpp(V.pack_1bpp(BDF[ord(ch)]), V.W, V.H, V.ROW_OFF_BIG)


def dump_glyph(ch):
    rows = BDF[ord(ch)]
    print("=== %s BDF 11x11（y0=2）===" % ch)
    for r in range(V.H):
        y = V.Y0 + r
        row = rows[y] if 0 <= y < len(rows) else 0
        print("  %2d %s" % (r, "".join("#" if (row >> (15 - (V.X0 + c))) & 1 else "." for c in range(V.W))))


def tile_to_bitmap(tile):
    out = []
    for r in range(8):
        w = struct.unpack_from("<I", VRAM, CHR + tile * 32 + r * 4)[0]
        out.append([(w >> (4 * c)) & 0xF for c in range(8)])
    return out


# 设置页「对话速度 慢 普通 快」：普/通 块 (CUR_X,CUR_Y)=(19,5)，TILE_BASE=1
# block_base = (5>>1)*64 + 19*2 = 128+38 = 166 → t0(普)=167
TB, BB = 1, 166
PHASE_AFTER_PU = 4  # (0+12)&7
ADV_PU = 1          # (0+12)>>3


def main():
    for ch in ("普", "通"):
        dump_glyph(ch)

    # 1) 复算：普 phase=0 → t0=TB+BB+0, t1=t0+2; 之后 TILE_OFFSET += adv*2 = 2
    g_pu, g_tong = own("普"), own("通")
    tiles = {}
    for n in range(166, 180):
        tiles[n] = [0] * 32  # 空 tile

    def blit(tile, g128, xs, w, phase):
        up, lo = V.extract_cols(g128, xs, w)
        V.blend_glyph_4bpp(tiles[tile], up, w, phase, V.COLORS)
        V.blend_glyph_4bpp(tiles[tile + 1], lo, w, phase, V.COLORS)

    # 普：ink=11 adv=12 phase=0 → w0=8 w1=3
    blit(167, g_pu, 0, 8, 0)
    blit(169, g_pu, 8, 3, 0)
    # 通：phase=4 → w0=4 w1=7
    blit(169, g_tong, 0, 4, 4)
    blit(171, g_tong, 4, 7, 0)
    # chs_fill_bg(171, w1=7..8) → 清 px7
    up, lo = V.extract_cols(b"\x00" * 128, 0, 1)
    V.blend_glyph_4bpp(tiles[171], up, 1, 7, V.COLORS)
    V.blend_glyph_4bpp(tiles[172], lo, 1, 7, V.COLORS)

    print("\n===== 期望 vs 实际（值: 1=墨 15=底 8=影 0=未写）=====")
    for n in (167, 169, 171):
        exp, act = tiles[n], tile_to_bitmap(n)
        print("--- tile %d ---" % n)
        print("   期望            实际")
        for r in range(8):
            e = " ".join("%X" % v for v in exp[r * 4:(r + 1) * 4])
            a = " ".join("%X" % v for v in act[r])
            # 期望展开成 8 列
            ee = []
            for i in range(8):
                b = exp[r * 4 + (i >> 1)]
                ee.append((b >> 4) if (i & 1) else (b & 0xF))
            e = " ".join("%X" % v for v in ee)
            flag = "" if e == a else "   <<< 差异"
            print("   %s    | %s%s" % (e, a, flag))

    # 2) 组装屏幕：把 167/169/171 横向拼成 24 列，看「通」缺哪几列
    print("\n===== 屏幕合成（col19..21 × 上下 8 行）=====")
    def pixel_v(tile, r, c):
        return tile_to_bitmap(tile)[r][c]
    for r in range(16):
        line = []
        for n in (167, 169, 171):
            rr = r & 7
            t = n if r < 8 else n + 1
            for c in range(8):
                v = pixel_v(t, rr, c)
                line.append("#" if v == 1 else ("+" if v == 8 else "."))
        print("  r%-2d %s" % (r, "".join(line)))

    print("\n===== 期望（BDF 拼接，无 tile 影响）=====")
    for r in range(11):
        row = BDF[ord("普")][V.Y0 + r] if True else 0
        rowt = BDF[ord("通")][V.Y0 + r]
        s = "".join("#" if (row >> (15 - (V.X0 + c))) & 1 else "." for c in range(11))
        s += "|"
        s += "".join("#" if (rowt >> (15 - (V.X0 + c))) & 1 else "." for c in range(11))
        print("  %2d %s" % (r, s))


main()
