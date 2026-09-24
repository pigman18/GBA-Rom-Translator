# -*- coding: utf-8 -*-
"""mapgrid.py <tag> <bg_idx> -- 打印某 BG 层 tilemap 的号网格（按行列）。

用途：看引擎自己「每个字符占几个号」「边框/底纹铺在哪」。
io 寄存器优先取 drive_<tag>_io.bin，没有就从 drive_<tag>.log 的 [io] 行解析。
"""
import re
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")


def main(tag, bi):
    vram = (T / f"drive_{tag}_vram.bin").read_bytes()
    p = T / f"drive_{tag}_io.bin"
    if p.exists():
        io = struct.unpack_from("<H", p.read_bytes(), 0)[0]
        cnts = [struct.unpack_from("<H", p.read_bytes(), 0x08 + 2 * i)[0] for i in range(4)]
    else:
        txt = (T / f"drive_{tag}.log").read_text(encoding="utf-8", errors="replace")
        d = {m.group(1): int(m.group(2), 16)
             for m in re.finditer(r"\[io\] IO (\w+) 0x[0-9a-fA-F]+:\s*(0x[0-9a-fA-F]+)", txt)}
        io = d.get("DISPCNT", 0)
        cnts = [d.get("BG%dCNT" % i, 0) for i in range(4)]
    bi = int(bi)
    cnt = cnts[bi]
    en = (io >> (8 + bi)) & 1
    cb, sb, size = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
    w, h = {0: (32, 32), 1: (64, 32), 2: (32, 64), 3: (64, 64)}[size]
    print("%s BG%d ON=%d cb%d sb%d sz%d map=%dx%d base=%08X DISPCNT=%04X"
          % (tag, bi, en, cb, sb, size, w, h, 0x06000000 + sb * 0x800, io))
    off = sb * 0x800
    for y in range(min(h, 20)):
        row = []
        for x in range(min(w, 30)):
            e = struct.unpack_from("<H", vram, off + (y * w + x) * 2)[0]
            n = e & 0x3FF
            row.append("%4d" % n)
        print("r%02d " % y + "".join(row))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
