# -*- coding: utf-8 -*-
"""vramdiff.py <tag_a> <tag_b> -- 两帧 VRAM 逐砖(32B)对比，按 charBlock 归类。

用法: python .tmp/vramdiff.py o_info t_info
"""
import struct
import sys
from collections import Counter
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")


def vram(tag):
    return (T / f"drive_{tag}_vram.bin").read_bytes()


def io(tag):
    return (T / f"drive_{tag}_io.bin").read_bytes()


def bgs(io_b):
    disp = struct.unpack_from("<H", io_b, 0)[0]
    out = []
    for i in range(4):
        c = struct.unpack_from("<H", io_b, 0x08 + 2 * i)[0]
        en = (disp >> (8 + i)) & 1
        cb, sb, size = (c >> 2) & 3, (c >> 8) & 0x1F, (c >> 14) & 3
        out.append((i, en, c, cb, sb, size))
    return disp, out


def main(a, b):
    va, vb = vram(a), vram(b)
    da, dbb = io(a), io(b)
    da, la = bgs(da)
    dbb, lb = bgs(dbb)
    print("A[%s] DISPCNT=%04X  B[%s] DISPCNT=%04X" % (a, da, b, dbb))
    for x, y in zip(la, lb):
        print("  BG%d  A:%s cb%d sb%d sz%d   B:%s cb%d sb%d sz%d"
              % (x[0], "ON " if x[1] else "off", x[3], x[4], x[5],
                 "ON " if y[1] else "off", y[3], y[4], y[5]))
    if len(va) != len(vb):
        print("!! len差 %d vs %d" % (len(va), len(vb)))
    n = min(len(va), len(vb))
    per_blk = Counter()
    first = {}
    for off in range(0, n, 32):
        if va[off:off + 32] != vb[off:off + 32]:
            blk = off // 0x4000
            tile = (off % 0x4000) // 32
            per_blk[blk] += 1
            first.setdefault(blk, []).append(tile)
    print("== 差异砖统计（A -> B） ==")
    for blk in sorted(per_blk):
        ts = first[blk]
        print("  cb%d : %4d 砖  号范围 %d..%d" % (blk, per_blk[blk], ts[0], ts[-1]))
        # 连续段
        runs = []
        s = ts[0]
        p = ts[0]
        for t in ts[1:]:
            if t == p + 1:
                p = t
                continue
            runs.append((s, p))
            s = p = t
        runs.append((s, p))
        print("        号区间: %s" % ", ".join("%d-%d" % r if r[0] != r[1] else str(r[0])
                                              for r in runs[:40]))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
