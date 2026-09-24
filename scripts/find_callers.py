#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""静态找函数的全部 BL 调用点（Thumb BL/BLX 解码，不依赖符号表）。

用法：
    python scripts/find_callers.py 0x0808FD5C 0x0808DB54 0x08070A4C
选项：
    --rom axvj|axve        默认 axvj（日版）
    --depth N              递归向上找 N 层调用者（默认 0 = 只直接调用者）
"""
import os
import sys
import struct

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROMS = {
    "axvj": "roms/origin/POKEMON_RUBY_AXVJ00.gba",
    "axve": "roms/origin/Pokemon Ruby Version(US).gba",
}
BASE = 0x08000000


def rd16(raw, off):
    if 0 <= off and off + 2 <= len(raw):
        return struct.unpack_from("<H", raw, off)[0]
    return None


def find_func_start(raw, vma):
    off = (vma - BASE) & ~1
    lo = max(0, off - 0x2000)
    for o in range(off, lo, -2):
        h = rd16(raw, o)
        if h is None:
            break
        if (h & 0xFE00) == 0xB400 and (h & 0x0100):
            prev = rd16(raw, o - 2)
            if prev is not None and (prev & 0xFE00) == 0xB400:
                continue
            return BASE + o
    return None


def build_bl_index(raw):
    """返回 dict: 目标地址 -> [调用点 VMA, ...]（同时收录 BL 与 BLX）。"""
    u16 = np.frombuffer(raw, dtype="<u2").astype(np.uint32)
    n = u16.size
    hi = u16[:-1]
    lo = u16[1:]
    is_bl = (hi & 0xF800) == 0xF000
    second = (lo & 0xF800) == 0xF800
    sel = np.nonzero(is_bl & second)[0]
    idx = {}
    for i in sel:
        h1 = int(hi[i]); h2 = int(lo[i]); addr = int(i) * 2
        S = (h1 >> 10) & 1
        J1 = (h2 >> 13) & 1
        J2 = (h2 >> 11) & 1
        # ARMv4T: I1 = NOT(J1 EOR S), I2 = NOT(J2 EOR S), imm10 = h1[9:0]
        I1 = 0 if (J1 ^ S) else 1
        I2 = 0 if (J2 ^ S) else 1
        imm11 = h2 & 0x7FF
        imm10 = h1 & 0x3FF
        raw_off = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
        if raw_off & (1 << 24):
            raw_off -= 1 << 25
        target = BASE + addr + 4 + raw_off
        # BLX（h2 bit12=0）目标对齐到 4
        if not (h2 & 0x1000):
            target &= ~3
        idx.setdefault(target, []).append(BASE + addr)
    return idx


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rom = "axvj"
    if "--rom" in sys.argv:
        rom = sys.argv[sys.argv.index("--rom") + 1]
    depth = 0
    if "--depth" in sys.argv:
        depth = int(sys.argv[sys.argv.index("--depth") + 1])

    raw = open(os.path.join(ROOT, ROMS[rom]), "rb").read()
    print("# BL 索引构建中 (%s) ..." % rom)
    idx = build_bl_index(raw)
    print("# 总 BL/BLX 数: %d\n" % sum(len(v) for v in idx.values()))

    targets = [int(a, 16) for a in args]
    seen = set()
    frontier = [(t, 0) for t in targets]
    while frontier:
        t, d = frontier.pop(0)
        if t in seen:
            continue
        seen.add(t)
        callers = idx.get(t) or idx.get(t | 1) or []
        print("## 0x%08X  <- 直接调用点 %d 个" % (t, len(callers)))
        for c in sorted(callers):
            fn = find_func_start(raw, c)
            print("     %08X  (所在函数 %s)" % (c, ("0x%08X" % fn) if fn else "?"))
            if depth > d:
                frontier.append((fn, d + 1))
        print()


if __name__ == "__main__":
    main()
