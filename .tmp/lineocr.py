# -*- coding: utf-8 -*-
"""lineocr.py <tag> <bg> <ymap> -- 按 tilemap 的「上下行对」重建一整行文字的位图，
再滑窗 OCR（大字库 11x11，1bpp 16B/槽）出槽号序列 → 可读出这一行到底画了什么。

（map 奇数行 = 上半砖，其 +1 行 = 下半砖；每格 8x16，拼成宽 = 格子数*8 的长条。）
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
ROOT = Path(r"C:/code/GBA-Rom-Translator")
ROM = (ROOT / "roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
BIG = 0x09500000 - 0x08000000


def fontmask(s):
    b = ROM[BIG + s * 16: BIG + (s + 1) * 16]
    return tuple((b[(r * 11 + x) >> 3] >> (7 - ((r * 11 + x) & 7))) & 1
                 for r in range(11) for x in range(11))


LIB = [fontmask(s) for s in range(0x2000)]


def main(tag, bg, y):
    v = (T / f"drive_{tag}_vram.bin").read_bytes()
    io = struct.unpack_from("<H", (T / f"drive_{tag}_io.bin").read_bytes(), 0x08 + 2 * bg)[0]
    disp = struct.unpack_from("<H", (T / f"drive_{tag}_io.bin").read_bytes(), 0)[0]
    cb, sb, size = (io >> 2) & 3, (io >> 8) & 0x1F, (io >> 14) & 3
    W = 32 if size in (0, 2) else 64
    cbase = cb * 0x4000
    moff = sb * 0x800

    def tile_at(row, col):
        return struct.unpack_from("<H", v, moff + (row * W + col) * 2)[0] & 0x3FF

    up = [tile_at(y, c) for c in range(W)]
    lo = [tile_at(y + 1, c) for c in range(W)]

    # 找有效格范围（跳过 0 与边框 512..520 与 516 fill 连续段）—— 全打出来即可
    band = [[0] * (W * 8) for _ in range(16)]
    for c in range(W):
        for half, t in ((0, up[c]), (1, lo[c])):
            o = cbase + t * 32
            for yy in range(8):
                for xx in range(8):
                    b = v[o + yy * 4 + xx // 2]
                    px = (b & 0xF) if xx % 2 == 0 else (b >> 4)
                    band[half * 8 + yy][c * 8 + xx] = px

    print("BG%d cb%d sb%d  上砖:" % (bg, cb, sb))
    print("   " + " ".join("%4d" % t for t in up[:30]))
    print("下砖:")
    print("   " + " ".join("%4d" % t for t in lo[:30]))
    print()

    # 逐格列出（只要不是 0/512..520）
    for c in range(W):
        u, l = up[c], lo[c]
        if u == 0 and l == 0:
            continue
        tag2 = ""
        if u >= 521 or l >= 521:
            tag2 = "  <-- 池"
        if u in (515, 516, 517) or (512 <= u <= 520 and u != 516):
            tag2 = "  (边框)"
        print("  c%-2d 上=%4d 下=%4d%s" % (c, u, l, tag2))

    # OCR：在 4bpp 里找 ink（值 1 或 8）的 11x11 窗口
    for inkv in (1, 8):
        res = []
        x = 0
        while x <= W * 8 - 11:
            obs = tuple(1 if band[2 + r][x + c] == inkv else 0
                        for r in range(11) for c in range(11))
            nz = sum(obs)
            if nz >= 8:
                d, s = min((sum(1 for a, b in zip(obs, lib) if a != b), i)
                           for i, lib in enumerate(LIB))
                if d <= 2:
                    res.append((x, s, nz))
                    x += 10
                    continue
            x += 1
        if res:
            print("\n== ink=%d ==" % inkv)
            for (px, s, nz) in res:
                print("   x=%3d (格%-2d) 槽%04X 墨%d" % (px, px // 8, s, nz))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
