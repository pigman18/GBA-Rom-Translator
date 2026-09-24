# -*- coding: utf-8 -*-
"""findmid.py — 反查「观测到的砖」到底是哪一档/哪一槽的字模。

观测像素值 = blend_glyph_4bpp 的输出 = colors[cell值]：
    cell 0  → colors[0] = color_d
    cell 14 → colors[14] = color_e
    cell 15 → colors[15] = color_c
所以先把观测砖的「调色板值集合」映射回 cell 值集合 {0,14,15}：
    出现 3 种值时按「最多=15、次多=14、最少=0」猜（阴影比墨少）。
用法:
    python .tmp/findmid.py <tag> <tile_hi> <tile_lo> [--lib big|middle|small]
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
ROM = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/"
           r"POKEMON_RUBY_AXVJ00_translated.gba")
FONTS = {"big": (0x09500000, 11, 11, 16),
         "middle": (0x09700000, 9, 11, 13),
         "small": (0x09600000, 9, 9, 11)}


def cell_from_1bpp(bits, width, rows, line_off):
    ink = [[0, 0] for _ in range(16)]
    for r in range(rows):
        if line_off + r >= 16:
            break
        for x in range(width):
            bi = r * width + x
            if (bits[bi >> 3] >> (7 - (bi & 7))) & 1:
                if x < 8:
                    ink[line_off + r][0] |= 1 << x
                else:
                    ink[line_off + r][1] |= 1 << (x - 8)
    cell = bytearray(128)
    for r in range(16):
        for half in range(2):
            b = [0, 0, 0, 0]
            for x in range(8):
                gx = half * 8 + x
                if ink[r][half] & (1 << x):
                    v = 15
                elif r >= 1 and gx >= 1 and \
                        (ink[r - 1][(gx - 1) >> 3] & (1 << ((gx - 1) & 7))):
                    v = 14
                else:
                    v = 0
                b[x >> 1] |= v << (4 if (x & 1) else 0)
            q = (0x40 if half else 0) + (0 if r < 8 else 0x20) + (r & 7) * 4
            cell[q:q + 4] = bytes(b)
    return cell


def nibs(t32):
    out = []
    for v in t32:
        out.append(v & 0xF)
        out.append(v >> 4)
    return out


def main():
    tag, thi, tlo = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    which = "middle"
    if "--lib" in sys.argv:
        which = sys.argv[sys.argv.index("--lib") + 1]
    cb = 0x4000
    vr = (T / ("drive_%s_vram.bin" % tag)).read_bytes()

    def tile(n):
        o = cb + n * 32
        return vr[o:o + 32]

    obs_hi, obs_lo = tile(thi), tile(tlo)
    vals = nibs(obs_hi) + nibs(obs_lo)
    uniq = sorted(set(vals))
    print("观测砖 %d: %s" % (thi, obs_hi.hex()))
    print("观测砖 %d: %s" % (tlo, obs_lo.hex()))
    print("出现的调色板值:", ["%X" % v for v in uniq])
    if len(uniq) != 3:
        print("⚠ 不是 3 种值，无法唯一映射 cell 值")
    # 尝试全部 6 种「哪个值对应 cell 0/14/15」的指派
    import itertools
    cands = []
    for perm in itertools.permutations(uniq):
        m = {perm[0]: 0, perm[1]: 14, perm[2]: 15}
        want_hi = bytes(sum(
            [(m[x] | (m[y] << 4)) for x, y in zip(nibs(obs_hi)[0::2],
                                                 nibs(obs_hi)[1::2])],
            []))
        cands.append((m, want_hi))
    base, width, rows, stride = FONTS[which]
    b = ROM.read_bytes()
    src_base = (base - 0x08000000)
    print("库=%s 宽%d 高%d 步进%d" % (which, width, rows, stride))
    for k in range(0x2000):
        off = src_base + k * stride
        if off + stride > len(b):
            break
        for lo_off in (0, 1, 2, 3, 5):
            cell = cell_from_1bpp(b[off:off + stride], width, rows, lo_off)
            for m, want in cands:
                if cell[0:32] == want:
                    print("★ 命中 k=0x%03X line_off=%d 映射=%s" %
                          (k, lo_off, {("%X" % a): c for a, c in m.items()}))
                    # 顺便核 lo 砖
                    got_lo = cell[32:64]
                    ok = got_lo == bytes(sum(
                        [(m[x] | (m[y] << 4)) for x, y in
                         zip(nibs(obs_lo)[0::2], nibs(obs_lo)[1::2])], []))
                    print("    下半砖一致: %s" % ok)
                    return
    print("无命中")


if __name__ == "__main__":
    main()
