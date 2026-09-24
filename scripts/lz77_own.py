#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lz77_own.py — 把 `bl LZ77UnCompVram/Wram` 的站点按**所属函数**归组。

为什么必须按函数而不是按 src/dst：
  · 按 dst 分不出 UI 与地图 —— 信息页美术与野外 primary tileset 都写 0x06000000。
  · 按 src 更不行 —— 运行时的 src 是 `tileset->tiles`（动态），静态解出的只是默认值。
    `080077DE`(CopyPrimaryTilesetToVram) 静态看起来 src=0x081BBE94(48砖)，
    和 `08008660` 同一个「假 src」；真值运行时才定。⇒ 只有**函数归属**是稳定判据。

函数入口扫描：从 site 向前逐 2 字节，找最近的 `push {.., lr}`（0xB5xx 且 bit8=1），
并要求它**像函数头**：前一条是 `pop {.., pc}`(0xBDxx) / `bx lr`(0x4770) /
对齐填充(0x0000) / 32bit 指令尾 —— 否则继续向前。

用法：
    python scripts/lz77_own.py            # 按函数归组打印全部 dst 落 VRAM 的站点
    python scripts/lz77_own.py --all      # 含 dst 不落 VRAM 的
"""
from __future__ import annotations

import io
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lz77_args import blx_targets, walk, lz_size, LZ_VRAM, LZ_WRAM  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL = "--all" in sys.argv
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
ROM = (ARGS[0] if ARGS else
       os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"))
VRAM_LO, VRAM_HI = 0x06000000, 0x06018000
BACK = 0x600


def hw_at(rom: bytes, a: int) -> int:
    j = a - 0x08000000
    if j < 0 or j + 1 >= len(rom):
        return -1
    return rom[j] | (rom[j + 1] << 8)


def is_push_lr(hw: int) -> bool:
    return hw >= 0 and (hw & 0xFF00) == 0xB500 and (hw & 0x0100) != 0


def looks_like_boundary(rom: bytes, a: int) -> bool:
    """a = push 指令地址；看它前面的 2 字节是否是函数收尾。"""
    prev = hw_at(rom, a - 2)
    if prev < 0:
        return False
    if (prev & 0xFF00) == 0xBD00:          # pop {.., pc}
        return True
    if prev == 0x4770:                     # bx lr
        return True
    if prev == 0x0000:                     # 对齐填充
        return True
    if prev == 0x46C0:                     # mov r8, r8（对齐全 NOP）
        return True
    if (prev & 0xF800) == 0xF000:          # 32bit 指令尾（bl/blx 结尾）
        return True
    return False


def func_start(rom: bytes, site: int) -> int:
    a = site
    lim = site - BACK
    while a > lim:
        a -= 2
        hw = hw_at(rom, a)
        if is_push_lr(hw) and looks_like_boundary(rom, a):
            return a
    # 退而求其次：最近的 push {.., lr}
    a = site
    while a > lim:
        a -= 2
        if is_push_lr(hw_at(rom, a)):
            return a
    return 0


def main() -> int:
    rom = io.open(ROM, "rb").read()
    sites = [(s, t) for s, t, _ in blx_targets(rom) if t in (LZ_VRAM, LZ_WRAM)]
    rows = []
    for site, tgt in sites:
        reg = walk(rom, site - 64, site)
        src = reg[0] if isinstance(reg[0], int) else None
        dst = reg[1] if isinstance(reg[1], int) else None
        size = lz_size(rom, src) if src else None
        rows.append((site, "Vram" if tgt == LZ_VRAM else "Wram",
                     src, size, dst, func_start(rom, site)))

    print("ROM %s  |  bl Vram %d / bl Wram %d"
          % (os.path.basename(ROM),
             sum(1 for r in rows if r[1] == "Vram"),
             sum(1 for r in rows if r[1] == "Wram")))
    print()

    groups = {}
    for r in rows:
        groups.setdefault(r[5], []).append(r)

    n_show = 0
    for fn in sorted(groups):
        rs = sorted(groups[fn])
        # 只看含 dst 落 VRAM 的组
        invram = [r for r in rs
                  if isinstance(r[4], int) and VRAM_LO <= r[4] < VRAM_HI]
        if not (ALL or invram):
            continue
        n_show += 1
        print("=" * 76)
        print("FUNC 0x%08X   %d 站点（其中 dst 落 VRAM %d）"
              % (fn, len(rs), len(invram)))
        for site, which, src, size, dst, _ in rs:
            mark = ""
            if isinstance(dst, int) and VRAM_LO <= dst < VRAM_HI:
                mark = " VRAM"
            sz = ("0x%X" % size) if size else "-"
            tiles = ("%d" % (size // 32)) if size else "-"
            print("   %08X %-5s src=%-10s size=%-8s tiles=%-5s dst=%s%s"
                  % (site, which,
                     ("0x%08X" % src) if src else "?",
                     sz, tiles,
                     ("0x%08X" % dst) if dst else "?", mark))
    print()
    print("（含 VRAM 站点的函数组: %d）" % n_show)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
