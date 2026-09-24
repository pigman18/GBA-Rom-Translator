# -*- coding: utf-8 -*-
"""func_blocks.py — 把静态 VRAM 资产按「加载它的函数（= 页面）」分组，输出每页占哪些块。

为什么必须按页面分组：
  `tpl_capacity.py` 用的是**所有页面资产的并集**求补集 —— 极度保守，会把
  「图鉴页的图集」也算成「对话框页被占」，得出 cb1=0 砖这种结论。
  真实情况：每个页面只加载自己那批资产。按函数分组后，空档会大得多。

数据源：.tmp/lz_own_all.txt（`scripts/lz77_own.py --all` 的输出，已按函数归组）
"""
from __future__ import annotations

import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VRAM = 0x06000000


def main() -> int:
    pages = defaultdict(list)
    site = "?"
    for ln in open(os.path.join(ROOT, ".tmp", "lz_own_all.txt"),
                   encoding="utf-8", errors="replace"):
        m = re.match(r"FUNC\s+(\S+)", ln)
        if m:
            site = m.group(1)
            continue
        m = re.search(r"size=(\S+)\s+tiles=(\S+)\s+dst=(0x[0-9a-fA-F]+)", ln)
        if not m or m.group(2) == "-":
            continue
        d, n = int(m.group(3), 16), int(m.group(2))
        if not (VRAM <= d < VRAM + 0x10000):
            continue
        pages[site].append((d, n))

    print("=" * 92)
    print("静态 VRAM 资产 × 页面（函数）分组 —— 每页占哪些 char block")
    print("=" * 92)
    print("%-12s %-42s %s" % ("函数(=页面)", "各块占用砖数 cb0/cb1/cb2/cb3", "资产数"))
    print("-" * 92)

    blkpages = defaultdict(list)
    for fn in sorted(pages):
        cnt = [0, 0, 0, 0]
        for d, n in pages[fn]:
            for k in range(n):
                a = d + k * 32
                if a < VRAM + 0x10000:
                    cnt[(a - VRAM) // 0x4000] += 1
        s = "  ".join("%4d" % c for c in cnt)
        hit = "".join(str(i) for i, c in enumerate(cnt) if c)
        print("%-12s %-42s %d   块%s" % (fn, s, len(pages[fn]), hit))
        for i, c in enumerate(cnt):
            if c:
                blkpages[i].append(fn)

    print()
    print("=" * 92)
    print("反向：每个块被哪些页面占用")
    print("=" * 92)
    for b in range(4):
        fs = blkpages[b]
        print("  cb%d：%2d 个页面" % (b, len(fs)))
        print("       " + "  ".join(fs[:14]))
        if len(fs) > 14:
            print("       ...（还有 %d 个）" % (len(fs) - 14))

    print()
    print("=" * 92)
    print("关键问句：有没有页面完全不碰 cb3？")
    print("=" * 92)
    no3 = [fn for fn in sorted(pages)
           if all(not (VRAM + 0xC000 <= d < VRAM + 0x10000) for d, _ in pages[fn])]
    print("  完全不写 cb3 的页面：%d / %d" % (len(no3), len(pages)))
    print("  " + "  ".join(no3[:20]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
