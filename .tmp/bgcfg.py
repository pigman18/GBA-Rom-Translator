# -*- coding: utf-8 -*-
"""打印每页 BG0..BG3 的 charBase / screenBase / 8bpp / 尺寸，并算出各层占用的 charBlock。
判据仅读 dump 的 IO 段（drive_<tag>_io.bin, 0x04000000..0x04000060）。
"""
import glob, os, re, struct, sys

IO_BASE = 0x04000000


def read_io(tag):
    p = ".tmp/drive_%s_io.bin" % tag
    if not os.path.exists(p):
        return None
    return open(p, "rb").read()


def cnt(io, bg):
    o = 0x08 + 2 * bg          # dump 起点就是 IO_BASE
    return struct.unpack_from("<H", io, o)[0]


def main():
    tags = []
    for p in sorted(glob.glob(".tmp/drive_*_io.bin")):
        t = os.path.basename(p)[6:-7]
        tags.append(t)
    if len(sys.argv) > 1:
        tags = [t for t in tags if any(a in t for a in sys.argv[1:])]
    print("tag             " + "".join("BG%d cb/sb/disp " % b for b in range(4)) + "  用到的 charBlock")
    for t in tags:
        io = read_io(t)
        if io is None or len(io) < 0x10:
            continue
        row = []
        used = set()
        for b in range(4):
            c = cnt(io, b)
            cb = (c >> 2) & 3
            sb = (c >> 8) & 0x1F
            p8 = (c >> 7) & 1
            disp = c & 1
            row.append("%d/%2d/%d " % (cb, sb, disp))
            if disp:
                used.add(cb)
                # 8bpp 时 map 项也可能是砖号 + 调色板，仍属同一块
        print("%-15s " % t + "  ".join(row) + "  {" + ",".join(str(x) for x in sorted(used)) + "}")


main()
