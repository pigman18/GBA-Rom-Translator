#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lz77_sites.py — 普查 `bl LZ77UnCompVram` / `bl LZ77UnCompWram` 的调用面。

为什么：v19 把总闸架在 BIOS 蹦床上，只有当「谁在调」足够集中才成立。
`fieldmap.c: CopyTilesetToVram` 会 `LZ77UnCompVram(tileset->tiles, BG_VRAM)`
⇒ 地图 tileset 也走这里 ⇒ 需要看清 dst 分布，才能判断总闸会不会误伤地图。

做法：对每个 `bl` 站，向前回扫最多 LOOKBACK 字节，找最近的
  `ldr r0,[pc,#imm]`（= src，LZ77 源）与 `ldr r1,[pc,#imm]`（= dst）。
Thumb: `ldr Rd,[pc,#imm8*4]` 编码 0x4800|Rd<<8|imm8，字面量 = ((pc+4)&~3)+imm8*4。

用法：python scripts/lz77_sites.py [ROM]
"""
from __future__ import annotations

import io
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = (sys.argv[1] if len(sys.argv) > 1 else
       os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"))
LZ_VRAM = 0x081B1298
LZ_WRAM = 0x081B129C
LOOKBACK = 80


def blx_targets(rom: bytes):
    """返回 [(site, target, is_blx)]。ROM 直映射：文件偏移 = addr - 0x08000000。"""
    out = []
    for i in range(0, len(rom) - 3, 2):
        h1 = rom[i] | (rom[i + 1] << 8)
        h2 = rom[i + 2] | (rom[i + 3] << 8)
        if (h1 & 0xF800) == 0xF000 and (h2 & 0xD000) == 0xD000:
            S = (h1 >> 10) & 1
            imm10 = h1 & 0x3FF
            J1 = (h2 >> 13) & 1
            J2 = (h2 >> 11) & 1
            imm11 = h2 & 0x7FF
            I1 = (~(J1 ^ S)) & 1
            I2 = (~(J2 ^ S)) & 1
            o = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
            if o & 0x01000000:
                o -= 0x02000000
            site = 0x08000000 + i
            out.append((site, (site + 4 + o) & 0xFFFFFFFF, (h2 & 0x4000) == 0))
    return out


def main() -> int:
    rom = io.open(ROM, "rb").read()
    sites = [(s, is_blx) for s, t, is_blx in blx_targets(rom)
             if t in (LZ_VRAM, LZ_WRAM)]
    print("ROM %s" % os.path.basename(ROM))
    print("bl LZ77UnCompVram == %d ; bl LZ77UnCompWram == %d"
          % (sum(1 for s, b in sites if _t(rom, s) == LZ_VRAM),
             sum(1 for s, b in sites if _t(rom, s) == LZ_WRAM)))
    print()
    print("%-12s %-6s %-12s %-12s" % ("site", "which", "src", "dst"))
    hist = {}
    unresolved = 0
    for site, _ in sites:
        which = "Vram" if _t(rom, site) == LZ_VRAM else "Wram"
        src, dst = _args(rom, site)
        if src is None and dst is None:
            unresolved += 1
        print("%08X  %-5s  0x%08X   0x%08X%s"
              % (site, which, src or 0, dst or 0,
                 "" if (src and dst) else "   <部分未解>"))
        if dst is not None:
            hist[dst] = hist.get(dst, 0) + 1
    print()
    print("== dst 分布（解出的 %d 处）==" % sum(hist.values()))
    for d, c in sorted(hist.items()):
        tag = ""
        if 0x06000000 <= d < 0x06018000:
            tag = "  [VRAM +0x%X]" % (d - 0x06000000)
        print("  0x%08X  ×%-3d%s" % (d, c, tag))
    print()
    print("(完全未解出参数: %d / %d)" % (unresolved, len(sites)))
    return 0


def _t(rom: bytes, site: int) -> int:
    i = site - 0x08000000
    h1 = rom[i] | (rom[i + 1] << 8)
    h2 = rom[i + 2] | (rom[i + 3] << 8)
    S = (h1 >> 10) & 1
    imm10 = h1 & 0x3FF
    J1 = (h2 >> 13) & 1
    J2 = (h2 >> 11) & 1
    imm11 = h2 & 0x7FF
    I1 = (~(J1 ^ S)) & 1
    I2 = (~(J2 ^ S)) & 1
    o = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
    if o & 0x01000000:
        o -= 0x02000000
    return (site + 4 + o) & 0xFFFFFFFF


def _args(rom: bytes, site: int):
    """回扫找最近一次 `ldr r0,[pc,#imm]`（src）与 `ldr r1,[pc,#imm]`（dst）。"""
    src = dst = None
    for k in range(2, LOOKBACK, 2):
        a = site - k
        i = a - 0x08000000
        if i < 0:
            break
        hw = rom[i] | (rom[i + 1] << 8)
        if (hw & 0xF800) != 0x4800:
            continue
        rd = (hw >> 8) & 7
        imm = (hw & 0xFF) * 4
        lit = (((a + 4) & ~3) + imm)
        j = lit - 0x08000000
        if j < 0 or j + 4 > len(rom):
            continue
        val = struct.unpack_from("<I", rom, j)[0]
        if rd == 0 and src is None:
            src = val
        elif rd == 1 and dst is None:
            dst = val
        if src is not None and dst is not None:
            break
    return src, dst


if __name__ == "__main__":
    raise SystemExit(main())
