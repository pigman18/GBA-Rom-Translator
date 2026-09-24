# -*- coding: utf-8 -*-
"""tpl_capacity.py — 每条窗口模板的「真实可用槽数」静态核算。

依据（全部逐指令实证，见 docs/调研_20260921d）：
  · 定号公式 `0x08002D1C`：
        dst = tpl->tileData + (win[0x16] + win[0x18]) * 32
    ⇒ 号 = 位置（层内号），随窗口私有 TILE_BASE 走。
  · 引擎字模缓存（单例）：
        `0x08002950(tpl, tileBase=1)` 配置 `*0x03000328=tpl / *0x0300032C=1 / *0x0300032E=0`
        `0x080029E0()` 16 帧 × 16 槽 = 256 槽、每槽 2 砖 ⇒ 写 tileData + [1,513)
    ⇒ **同一时刻只有一个块被预取写**。

推论：
  我们的字模只要放在 `tileData + [513,1024)*32`（= 下一块，除头 1 号），
  就**永不**被引擎预取覆盖。剩下只需扣掉「同块静态美术」（可静态枚举）。

本脚本对 53 条模板逐条算：
  可用号段 = 层内 [513,1024)  →  物理块 = cb(charBase+1)
  可用槽数 = 512 - |该块静态美术 ∩ 该段|
"""
from __future__ import annotations

import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
TPL_LO, TPL_HI, TPL_STEP = 0x081BB3DC, 0x081BB8BC, 0x18
VRAM = 0x06000000


def load_static_blocks():
    """{cb_index: set(块内号)} —— 由 LZ77/RL + CpuSet 静态枚举得到。"""
    used = {c: set() for c in range(4)}
    p = os.path.join(ROOT, ".tmp", "lz_own_all.txt")
    for ln in open(p, encoding="utf-8", errors="replace"):
        m = re.search(r"size=(\S+)\s+tiles=(\S+)\s+dst=(0x[0-9a-fA-F]+)", ln)
        if not m:
            continue
        tiles, dst = m.group(2), m.group(3)
        if tiles == "-":
            continue
        d, n = int(dst, 16), int(tiles)
        if not (VRAM <= d < VRAM + 0x10000):
            continue
        for k in range(n):
            a = d + k * 32
            if a >= VRAM + 0x10000:
                break
            used[(a - VRAM) // 0x4000].add(((a - VRAM) % 0x4000) // 32)
    p = os.path.join(ROOT, ".tmp", "vram_cpu_assets_run.txt")
    for ln in open(p, encoding="utf-8", errors="replace"):
        m = re.match(r"0x([0-9a-f]{7})\s+(\d+)\s+(CpuSet|CpuFastSet)\s+\[(\d+)\]", ln)
        if not m:
            continue
        d, tile, words = int(m.group(1), 16), int(m.group(2)), int(m.group(4))
        if not (VRAM <= d < VRAM + 0x10000):
            continue
        for k in range(max(1, words * 4 // 32)):
            a = d + k * 32
            if a >= VRAM + 0x10000:
                break
            used[(a - VRAM) // 0x4000].add(((a - VRAM) % 0x4000) // 32)
    return used


def main() -> int:
    rom = open(ROM, "rb").read()
    static = load_static_blocks()

    rows = []
    for a in range(TPL_LO, TPL_HI + 1, TPL_STEP):
        o = a - 0x08000000
        # 字段偏移（见 .tmp/tplinv2.py）：+08=font  +09=textMode
        #                            +0C=tileData(u32)  +10=tilemap(u32)
        tm, font = rom[o + 9], rom[o + 8]
        td = struct.unpack_from("<I", rom, o + 0x0C)[0]
        mp = struct.unpack_from("<I", rom, o + 0x10)[0]
        if not (VRAM <= td <= VRAM + 0x18000):
            continue
        cb = (td - VRAM) // 0x4000
        rows.append((a, tm, font, cb, td, mp))

    print("=" * 84)
    print("53 条窗口模板 × 可用槽数（静态核算；号段 = 层内 [513,1024) ⇒ 物理块 cb(charBase+1)）")
    print("=" * 84)
    print("%-10s %-3s %-4s %-5s %-10s %-6s %-8s %s" %
          ("tpl", "tm", "font", "cb", "tileData", "下一块", "空闲砖", "空段（前 3，块内号）"))
    print("-" * 84)

    tot = {}
    for a, tm, font, cb, td, mp in rows:
        nxt = (cb + 1) % 4
        if cb == 4:
            nxt = 4            # OBJ
        free = [k for k in range(512) if k not in static.get(nxt, set())]
        # 连续段
        runs, s, p = [], None, None
        for k in free:
            if s is None:
                s = p = k
            elif k == p + 1:
                p = k
            else:
                runs.append((s, p))
                s = p = k
        if s is not None:
            runs.append((s, p))
        big = sorted(runs, key=lambda r: r[1] - r[0], reverse=True)[:3]
        txt = "  ".join("[%d,%d)%d" % (x, y + 1, y - x + 1) for x, y in big) or "（无）"
        print("%08X   %-3d %-4d %-5d %08X   cb%-4d %-8d %s"
              % (a, tm, font, cb, td, nxt, len(free), txt))
        tot.setdefault(nxt, []).append(len(free))

    print()
    print("=" * 84)
    print("汇总：按「下一块」分组的空闲砖数")
    print("=" * 84)
    for c in sorted(tot):
        v = tot[c]
        print("  下一块 cb%d：%2d 条模板，空闲 %d~%d 砖（中位 %d）" %
              (c, len(v), min(v), max(v), sorted(v)[len(v) // 2]))
    print()
    print("  单条模板的可用砖数 ⇒ 容量：")
    for c in sorted(tot):
        m = sorted(tot[c])[len(tot[c]) // 2]
        print("    cb%d 中位 %3d 砖 ⇒ 16px 步进 %2d 字 / 12px 跨字共享 %3d 字"
              % (c, m, m // 4, m // 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
