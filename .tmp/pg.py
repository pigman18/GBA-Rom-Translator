# -*- coding: utf-8 -*-
"""pg.py — 打印某 BG 层某几行的 map 值 + 每格引用的 16x16（上下两砖）ASCII 点阵。

用法:
    python .tmp/pg.py <tag> <bgN> <r0> <r1> [c0] [c1]

判据来源：mgba_drive 的 vram / pal / io dump + drive_<tag>.log 的 BGxCNT。
"""
import re
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
GBA = 0x06000000


def read_cnt(tag, bg):
    txt = (T / ("drive_%s.log" % tag)).read_text(encoding="utf-8",
                                                 errors="replace")
    for m in re.finditer(r"IO (BG\dCNT) 0x[0-9a-f]+:\s*(0x[0-9a-fA-F]+)", txt):
        if m.group(1) == "BG%dCNT" % bg:
            return int(m.group(2), 16)
    raise SystemExit("no BG%dCNT in log" % bg)


def main():
    tag = sys.argv[1]
    a = sys.argv[2].lower()
    bg = int(a[2]) if a.startswith("bg") else int(a)
    r0, r1 = int(sys.argv[3]), int(sys.argv[4])
    c0 = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    c1 = int(sys.argv[6]) if len(sys.argv) > 6 else 30

    cnt = read_cnt(tag, bg)
    cb = ((cnt >> 2) & 3) * 0x4000
    sb = ((cnt >> 8) & 0x1F) * 0x800
    p8 = (cnt >> 7) & 1
    vr = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
    print("%s BG%d CNT=0x%04X charBase=0x%05X screenBase=0x%05X 8bpp=%d"
          % (tag, bg, cnt, cb, sb, p8))

    def tile_px(n):
        """返回 8x8 的色号矩阵。"""
        o = cb + n * (64 if p8 else 32)
        out = []
        for y in range(8):
            row = []
            for x in range(8):
                if p8:
                    row.append(vr[o + y * 8 + x])
                else:
                    b = vr[o + y * 4 + x // 2]
                    row.append((b >> 4) if (x & 1) else (b & 0xF))
            out.append(row)
        return out

    dots = "--dots" in sys.argv
    if "--grid" in sys.argv:
        # v35 三人口段表（与 PrintNextChar_hook.c 的 chs_p?_seg_* 保持一致）
        POOLS = {0: [(384, 32), (946, 22)],
                 1: [(47, 2), (57, 2), (151, 2), (213, 2), (219, 5), (237, 3),
                     (247, 3), (255, 5), (267, 4), (287, 6), (339, 5), (351, 6),
                     (365, 3), (375, 10), (404, 10), (481, 15), (526, 38),
                     (612, 78)],
                 2: [(192, 32), (320, 32)]}
        # 本层 charBase 决定「号」按哪个入口径解释
        dom = {0x4000: 0, 0x8000: 1, 0x0000: 2}.get(cb)

        def mark(n):
            for b, k in POOLS.get(dom, []):
                if b == n:
                    return "="          # 槽头（上半砖）
                if b < n < b + k * 2:
                    return "+"          # 槽尾（下半砖）
            return "."                  # 不在我方池内（引擎自用 / 静态美术）
        print("      " + "".join("%-5d" % c for c in range(c0, c1 + 1)))
        for r in range(r0, r1 + 1):
            cells = []
            for c in range(c0, c1 + 1):
                n = struct.unpack_from(
                    "<H", vr, sb + (r * 32 + c) * 2)[0] & 0x3FF
                cells.append((mark(n) + "%d" % n).ljust(5))
            print("r%-4d " % r + "".join(cells))
        return
    for r in range(r0, r1 + 1):
        if dots:
            # 把该行 c0..c1 每格画成上/下两块 8x8（下半 = 下一行 map 的砖）
            for half in (0, 1):
                for y in range(8):
                    line = []
                    for cc in range(c0, c1 + 1):
                        n = struct.unpack_from(
                            "<H", vr, sb + ((r + half) * 32 + cc) * 2)[0] & 0x3FF
                        px = tile_px(n)
                        line.append("".join("%X" % v for v in px[y]))
                    print("".join(line))
                print("   ^^ r%d%s" % (r, "/下" if half else "/上"))
            continue
        for c in range(c0, c1 + 1):
            o = sb + (r * 32 + c) * 2
            n = struct.unpack_from("<H", vr, o)[0] & 0x3FF
            hf = struct.unpack_from("<H", vr, o)[0] & 0x400
            print("  r%-3d c%-3d hw=%d n=%-5d  0x%05X" % (r, c, 1 if hf else 0,
                                                          n, GBA + cb + n * 32))
        print()


if __name__ == "__main__":
    main()
