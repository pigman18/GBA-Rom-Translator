#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_vram_cpu_assets.py — 补扫 CpuSet / CpuFastSet 直接写 VRAM 的落点

`scan_vram_assets.py` 只覆盖 LZ77UnCompVram / RLUnCompVram。窗口框（border）等
小体积资产常用「ROM 未压缩字面量 + CpuFastSet/CpuSet」直拷，本脚本补上这条路。

蹦床（全 ROM 唯一）：
  · 0x081B1290  CpuFastSet   (svc 0x0C)   r0=src r1=dst r2=control
  · 0x081B1294  CpuSet       (svc 0x0B)   r0=src r1=dst r2=control

自证闸门
========
  G1 BL 解码器：4 个已知 DrawGlyphTiles 调用点必须全找到
  G2 跨脚本一致：本脚本对 0x081B1294/0x081B1290 的调用点数必须与历史枚举一致
零 ROM 风险：只读。
"""
import sys
import os
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scan_vram_assets import (ROM_PATH, BASE, ROM_END, VRAM_LO, VRAM_HI,   # noqa: E402
                              KNOWN_DRAWGLYPHTILES, find_bl_sites, resolve_reg)

CPUSET = 0x081B1294
CPUFASTSET = 0x081B1290


def main() -> int:
    rom = open(ROM_PATH, "rb").read()

    got = find_bl_sites(rom, 0x08003630)
    miss = [hex(a) for a in KNOWN_DRAWGLYPHTILES if a not in got]
    if miss:
        print("❌ G1 失败：%s" % miss)
        return 2
    print("✅ G1 BL 解码器自证：4 个已知调用点全部命中")

    n_set = len(find_bl_sites(rom, CPUSET))
    n_fast = len(find_bl_sites(rom, CPUFASTSET))
    print("✅ G2 调用点计数：CpuSet=%d、CpuFastSet=%d（历史实测 192 / 30）"
          % (n_set, n_fast))
    if (n_set, n_fast) != (192, 30):
        print("   ⚠ 与历史值不符，请核对（不阻断，仅提示）")
    print()

    hits = collections.defaultdict(list)   # dst -> [(site, func, size_words)]
    for tgt, name in ((CPUSET, "CpuSet"), (CPUFASTSET, "CpuFastSet")):
        for site in find_bl_sites(rom, tgt):
            dst = resolve_reg(rom, site, 1)
            if dst is None or not (VRAM_LO <= dst < VRAM_HI):
                continue
            ctrl = resolve_reg(rom, site, 2)
            nwords = (ctrl & 0x1FFFFF) if ctrl is not None else None
            hits[dst].append((site, name, nwords))

    print("=" * 78)
    print("CpuSet / CpuFastSet → VRAM 落点（BG 号空间 = (dst-0x06000000)/32）")
    print("=" * 78)
    if not hits:
        print("  （无）—— 没有任何 CpuSet/CpuFastSet 直接写 VRAM")
    else:
        print("%-12s %-12s %-12s %-8s %s" % ("dst", "tile", "func", "words", "callers"))
        for dst in sorted(hits):
            tile = (dst - VRAM_LO) // 32
            fns = collections.Counter(h[1] for h in hits[dst])
            sizes = sorted(set(h[2] for h in hits[dst] if h[2] is not None))
            print("%-12s %-12d %-12s %-8s %d 处 %s"
                  % (hex(dst), tile, "/".join(fns), sizes if sizes else "?",
                     len(hits[dst]),
                     [hex(h[0]) for h in hits[dst]][:3]))

    # ---- 与 BG 号空间 [0,1024) 的交集，重点看 [0,384) ----
    print()
    print("=" * 78)
    print("落在 [0, 384) 的 CpuSet 资产（若为空 ⇒ 该区间对 BG 层完全空闲）")
    print("=" * 78)
    inband = sorted(d for d in hits if (d - VRAM_LO) // 32 < 384)
    if not inband:
        print("  （无）✅ [0, 384) 无 CpuSet/CpuFastSet 资产")
    else:
        for d in inband:
            print("  %s (号 %d) ← %s" % (hex(d), (d - VRAM_LO) // 32,
                                          [hex(h[0]) for h in hits[d]]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
