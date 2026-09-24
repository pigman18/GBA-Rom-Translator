#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lz77_args.py — 把 `bl LZ77UnCompVram/Wram` 的全部站点解成 (src, size, dst)。

为什么不用「回扫找 ldr r0/r1」：参数常常是 `movs r1,#0xC0; lsls r1,r1,#19`
（= 0x06000000，地图 primary tileset 就是这么写的）⇒ 回扫法整个漏掉它。

做法：从 site 往前 LOOKBACK 字节，**按 Thumb 顺序解码**，维护 r0..r7 的已知值：
  · `ldr Rd,[pc,#imm]`        → 字面量
  · `movs Rd,#imm8`           → 立即数
  · `lsls/lsrs Rd,Rs,#imm5`   → 移位
  · `mov Rd,Rs`               → 传播
  · `adds Rd,Rs,#imm3`        → 传播（imm3==0）/ 加偏
  · `adds Rd,#imm8`           → 加偏
  · `bl`(32bit) / 不认识的写操作 → r0..r3 作废（调用者保存，语义上也该作废）
然后取 site 处的 r0/r1。再从 r0 指向的 blob 读 LZ77 头（byte0=0x10，byte1..3=解压大小）。

用法：python scripts/lz77_args.py [ROM] [--all]
      默认只打印 dst 落在 VRAM 的站点；--all 全打。
"""
from __future__ import annotations

import io
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
ALL = "--all" in sys.argv
ROM = (ARGS[0] if ARGS else
       os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"))
LZ_VRAM, LZ_WRAM = 0x081B1298, 0x081B129C
LOOKBACK = 64
VRAM_LO, VRAM_HI = 0x06000000, 0x06018000
UNK = object()


def blx_targets(rom: bytes):
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


def walk(rom: bytes, start: int, end: int):
    """顺序解码 [start,end)，返回 site 处的 r0..r7。"""
    reg = [UNK] * 8
    a = start
    while a < end:
        i = a - 0x08000000
        if i < 0 or i + 1 >= len(rom):
            break
        hw = rom[i] | (rom[i + 1] << 8)
        w = 2
        if (hw & 0xF800) == 0xF000 and i + 3 < len(rom):        # 32bit
            hw2 = rom[i + 2] | (rom[i + 3] << 8)
            if (hw2 & 0xD000) == 0xD000:                         # BL / BLX
                reg[0] = reg[1] = reg[2] = reg[3] = UNK          # 调用者保存
                w = 4
            else:
                reg[0] = reg[1] = reg[2] = reg[3] = UNK          # 其它 32bit：保守
                w = 4
        elif (hw & 0xF800) == 0x4800:                            # ldr Rd,[pc,#imm]
            rd = (hw >> 8) & 7
            imm = (hw & 0xFF) * 4
            lit = ((a + 4) & ~3) + imm
            j = lit - 0x08000000
            if 0 <= j and j + 4 <= len(rom):
                reg[rd] = struct.unpack_from("<I", rom, j)[0]
            else:
                reg[rd] = UNK
        elif (hw & 0xF800) == 0x2000:                            # movs Rd,#imm8
            reg[(hw >> 8) & 7] = hw & 0xFF
        elif (hw & 0xF800) == 0x3000:                            # adds Rd,#imm8
            rd = (hw >> 8) & 7
            if isinstance(reg[rd], int):
                reg[rd] = (reg[rd] + (hw & 0xFF)) & 0xFFFFFFFF
        elif (hw & 0xFE00) == 0x3800:                            # subs Rd,#imm8
            rd = (hw >> 8) & 7
            if isinstance(reg[rd], int):
                reg[rd] = (reg[rd] - (hw & 0xFF)) & 0xFFFFFFFF
        elif (hw & 0xF800) == 0x0000:                            # lsls/lsrs/asrs Rd,Rs,#imm5
            imm5 = (hw >> 6) & 0x1F
            rs = (hw >> 3) & 7
            rd = hw & 7
            op = (hw >> 11) & 3
            if rs != rd:
                reg[rd] = UNK
            elif isinstance(reg[rs], int):
                if op == 0:
                    reg[rd] = (reg[rs] << imm5) & 0xFFFFFFFF
                elif op == 1:
                    reg[rd] = (reg[rs] >> imm5) & 0xFFFFFFFF
                else:
                    reg[rd] = UNK
            else:
                reg[rd] = UNK
        elif (hw & 0xFFC0) == 0x1C00:                            # adds Rd,Rs,#imm3
            imm3 = (hw >> 6) & 7
            rs = (hw >> 3) & 7
            rd = hw & 7
            v = reg[rs]
            reg[rd] = (v + imm3) & 0xFFFFFFFF if isinstance(v, int) else UNK
        elif (hw & 0xFF00) == 0x4600:                            # mov Rd,Rs（含高寄存器）
            rd = (hw & 7) | ((hw >> 4) & 8)
            rs = (hw >> 3) & 0xF
            if rd < 8:
                reg[rd] = reg[rs] if rs < 8 else UNK
        else:
            # 不认识的 16bit 几乎都写某个 r0..r7 —— 保守起见清掉低寄存器
            for k in range(4):
                reg[k] = UNK
        a += w
    return reg


def lz_size(rom: bytes, src: int):
    j = src - 0x08000000
    if j < 0 or j + 4 > len(rom):
        return None
    if rom[j] != 0x10:
        return None
    return rom[j + 1] | (rom[j + 2] << 8) | (rom[j + 3] << 16)


def main() -> int:
    rom = io.open(ROM, "rb").read()
    sites = [(s, t) for s, t, _ in blx_targets(rom) if t in (LZ_VRAM, LZ_WRAM)]
    rows = []
    for site, tgt in sites:
        reg = walk(rom, site - LOOKBACK, site)
        src = reg[0] if isinstance(reg[0], int) else None
        dst = reg[1] if isinstance(reg[1], int) else None
        size = lz_size(rom, src) if src else None
        rows.append((site, "Vram" if tgt == LZ_VRAM else "Wram", src, size, dst))

    print("ROM %s  |  bl Vram %d / bl Wram %d"
          % (os.path.basename(ROM),
             sum(1 for r in rows if r[1] == "Vram"),
             sum(1 for r in rows if r[1] == "Wram")))
    print()
    print("%-10s %-5s %-10s %-9s %-8s %s"
          % ("site", "which", "src", "size", "tiles", "dst"))
    n_in = 0
    for site, which, src, size, dst in rows:
        invram = isinstance(dst, int) and VRAM_LO <= dst < VRAM_HI
        if not (ALL or invram):
            continue
        n_in += 1
        tiles = ("%d" % (size // 32)) if size else "-"
        print("%08X  %-5s 0x%08X %-9s %-8s 0x%08X%s"
              % (site, which, src or 0,
                 ("0x%X" % size) if size else "-", tiles, dst or 0,
                 "" if invram else "  [非VRAM]"))
    print()
    print("(dst 落 VRAM 的站点: %d / %d)" % (n_in, len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
