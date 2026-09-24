#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""静态盘点：窗口模板表（只读原盘，不改任何文件）。

目的：不跑 gdb、不采样，直接从 ROM 得到
  · 每个模板的 tileData 落在哪个 charBlock（= 该窗口所在 BG 层的层基址）
  · 模板 +0x08/+0x09/+0x0A/+0x0B 的取值分布（判断是否存在「静态可分的 textMode」）
先 dump 已知模板 0x081BB874 的字节用于定步长，再全表扫描。
"""
import struct
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"C:\code\GBA-Rom-Translator"
ROM_PATH = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
BASE = 0x08000000
VRAM_LO, VRAM_HI = 0x06000000, 0x06018000
TILE = 32

KNOWN = 0x081BB874


def blk(addr):
    if not (VRAM_LO <= addr < VRAM_HI):
        return "-"
    n = (addr - VRAM_LO) // 0x4000
    name = {0: "cb0", 1: "cb1", 2: "cb2", 3: "cb3", 4: "cb4/OBJ", 5: "cb5/OBJ"}.get(n, "?")
    return "%s@%06X" % (name, addr - VRAM_LO - n * 0x4000)


def main():
    rom = open(ROM_PATH, "rb").read()
    print("ROM %s  %d B" % (os.path.basename(ROM_PATH), len(rom)))

    off = KNOWN - BASE
    print("\n=== 已知模板 0x%08X 附近 0x60 字节 ===" % KNOWN)
    for row in range(0, 0x60, 0x10):
        a = KNOWN + row
        b = rom[off + row: off + row + 0x10]
        print("  %08X  %s   +%02X=%02X +%02X=%02X +%02X=%02X +%02X=%02X"
              % (a, " ".join("%02X" % x for x in b),
                 row, b[0], row + 1, b[1], row + 2, b[2], row + 3, b[3]))

    # 用「同一个 tileData 每 0x?? 重复」推断条目步长
    print("\n=== 候选步长探测：+0x0C 为 VRAM 对齐值的地址（0x081BB000..0x081BC000，步 4）===")
    hits = []
    for a in range(0x081BB000, 0x081BC000, 4):
        o = a - BASE
        td = struct.unpack_from("<I", rom, o + 0x0C)[0]
        if VRAM_LO <= td < VRAM_HI and td % TILE == 0:
            hits.append(a)
    print("  命中 %d 个地址" % len(hits))
    if hits:
        print("  首 24 个：%s" % " ".join("%X" % a for a in hits[:24]))
        # 差分统计
        from collections import Counter
        diffs = Counter(b - a for a, b in zip(hits, hits[1:]))
        print("  相邻差分分布：%s" % diffs.most_common(8))

    # 按推测步长汇总字段分布
    print("\n=== 字段分布（按上面命中的地址，各偏移取值计数）===")
    for ofs, name in ((0x01, "charBase?"), (0x08, "+08"), (0x09, "+09/TPL_TEXTMODE"),
                      (0x0A, "+0A/WIN_TEXTMODE?"), (0x0B, "+0B")):
        c = Counter(rom[a - BASE + ofs] for a in hits)
        print("  %-22s %s" % (name, sorted(c.items(), key=lambda kv: -kv[1])[:10]))

    print("\n=== 逐条明细（tileData / tilemap 落块）===")
    from collections import Counter as C2
    blkc = C2()
    for a in hits:
        o = a - BASE
        td = struct.unpack_from("<I", rom, o + 0x0C)[0]
        tm = struct.unpack_from("<I", rom, o + 0x10)[0]
        b = blk(td)
        blkc[b.split("@")[0]] += 1
        print("  tpl=%08X  tm(+09)=%02X  +0A=%02X  +0B=%02X  tileData=%08X %-12s tilemap=%08X %s"
              % (a, rom[o + 9], rom[o + 10], rom[o + 11], td, b, tm, blk(tm)))
    print("\n  tileData 落块统计：%s" % blkc.most_common())


if __name__ == "__main__":
    main()
