# -*- coding: utf-8 -*-
"""global_occupy.py — 全局 VRAM 号空间 [0,2048) 的静态占用总图。

为什么需要它：
  以往所有「找空区」都是**逐屏采样**（savestate/dump），所以漏「本轮没被写入的号」
  又误收「上一屏的残骸」。本脚本改用**纯静态**：把 ROM 里**所有**会写 VRAM 的
  指令序列枚举出来，得到「可能被写」的号集合。

数据来源（全部只读原盘）：
  1. `scripts/lz77_own.py --all` 的 stdout（已落盘 .tmp/lz_own_all.txt）
     —— 覆盖 bl LZ77UnCompVram / LZ77UnCompWram，按函数归组，含 dst/tiles。
  2. `scripts/scan_vram_cpu_assets.py` 的 stdout（.tmp/vram_cpu_assets_run.txt）
     —— 覆盖 bl CpuSet / CpuFastSet。
  3. 引擎字模区（逐指令实证，见 scripts/scan_engine_tile_cache.py）：
     `tileData + (tileBase+index)*32`, index∈[0,256), tileBase≡1
     ⇒ 写 `[tileData+0x20, tileData+0x4020)` = 该块砖号 [1,513)。
     文本层 charBase=C ⇒ tileData = VRAM + C*0x4000 ⇒ 全局号 [C*512+1, C*512+513)。
  4. 文本层 charBase 分布（docs/静态盘点_20260921_窗口模板表_tm与charBase.md）：
     cb0×24 / cb1×4 / cb2×20 / cb3×4 / OBJ×1。

输出：
  · 每 512 号（一个 char block）一行的占用率
  · 全局「从未被任何来源写过」的号
  · 对现有池子 6 段的落点判定
  · 「块级空块」存在性判定（= 该块 512 号全空）
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VRAM, CB, NBG = 0x06000000, 0x4000, 2048        # 全局号 0..2047（BG 区 64KB）


# ---------------------------------------------------------------- 数据源 1
def load_lz77():
    """返回 [(dst_tile, tiles, caller, func)]，只取 dst 落 BG VRAM 的。"""
    p = os.path.join(ROOT, ".tmp", "lz_own_all.txt")
    out = []
    site = "?"
    for ln in open(p, encoding="utf-8", errors="replace"):
        m = re.match(r"FUNC\s+(\S+)", ln)
        if m:
            site = m.group(1)
            continue
        m = re.match(r"\s*([0-9A-F]{8})\s+(Vram|Wram)\s+src=(\S+)\s+size=(\S+)\s+"
                     r"tiles=(\S+)\s+dst=(\S+)", ln)
        if not m:
            continue
        _addr, _kind, _src, _size, tiles, dst = m.groups()
        if not dst.startswith("0x") or tiles == "-":
            continue
        try:
            d = int(dst, 16)
            n = int(tiles)
        except ValueError:
            continue
        if not (VRAM <= d < VRAM + 0x10000):
            continue
        out.append(((d - VRAM) // 32, n, site, "LZ77/RL"))
    return out


# ---------------------------------------------------------------- 数据源 2
def load_cpu():
    """返回 [(dst_tile, tiles, caller, 'CpuSet')]。"""
    p = os.path.join(ROOT, ".tmp", "vram_cpu_assets_run.txt")
    out = []
    for ln in open(p, encoding="utf-8", errors="replace"):
        m = re.match(r"0x([0-9a-f]{7})\s+(\d+)\s+(CpuSet|CpuFastSet)\s+\[(\d+)\]\s+"
                     r"(\d+)\s*处\s*\[([^\]]*)\]", ln)
        if not m:
            continue
        dst, tile, kind, words, _n, callers = m.groups()
        d = int(dst, 16)
        if not (VRAM <= d < VRAM + 0x10000):
            continue
        # CpuSet 单位是 word(4B)；tile = 32B ⇒ tiles = words*4/32
        out.append((int(tile), max(1, int(words) * 4 // 32), callers, kind))
    return out


# ------------------------------------------------------- 数据源 3：字模区
TEXT_CB = {0: 24, 1: 4, 2: 20, 3: 4}          # 文本层 charBase 分布（静态盘点）


def atlas_ranges():
    """每个 charBase 的引擎字模区（全局号）。charBase=C ⇒ [C*512+1, C*512+513)。"""
    return {c: (c * 512 + 1, c * 512 + 513) for c in TEXT_CB}


def main() -> int:
    lz, cpu = load_lz77(), load_cpu()
    atlas = atlas_ranges()

    oth = set()
    src_count = {}
    for t, n, site, kind in lz:
        for k in range(t, min(t + n, NBG)):
            oth.add(k)
        src_count.setdefault(site, []).append((t, n, kind))
    for t, n, callers, kind in cpu:
        for k in range(t, min(t + n, NBG)):
            oth.add(k)
        src_count.setdefault("cpu:" + callers, []).append((t, n, kind))

    atl = set()
    for c, (lo, hi) in atlas.items():
        if not TEXT_CB[c]:
            continue
        for k in range(lo, min(hi, NBG)):
            atl.add(k)

    print("=" * 78)
    print("全局号空间 [0,%d) 静态占用总图（号 = 绝对 VRAM 地址 / 32）" % NBG)
    print("=" * 78)
    print("  LZ77/RL 站点（dst 落 BG VRAM）：%d 个，覆盖 %d 号" % (len(lz), len(oth)))
    print("  CpuSet/CpuFastSet 站点       ：%d 个" % len(cpu))
    print("  引擎字模区（由文本层 charBase 决定）：%d 号" % len(atl))
    print()

    print("-" * 78)
    print("%-6s %-12s %-10s %-10s %-10s %s" %
          ("块", "全局号段", "静态美术", "字模区", "并集占用", "从未被写过"))
    print("-" * 78)
    empty_blocks = []
    for c in range(4):
        lo, hi = c * 512, c * 512 + 512
        n_oth = len([k for k in range(lo, hi) if k in oth])
        n_atl = len([k for k in range(lo, hi) if k in atl])
        n_un = len([k for k in range(lo, hi)
                    if k not in oth and k not in atl])
        allc = len([k for k in range(lo, hi) if k in oth or k in atl])
        tag = ""
        if allc == 0:
            tag = "  ★ 整块从未被写"
            empty_blocks.append(c)
        print("cb%d    [%4d,%4d)  %-10s %-10s %-10s %s%s" %
              (c, lo, hi, "%d号" % n_oth, "%d号" % n_atl,
               "%d号(%.0f%%)" % (allc, 100.0 * allc / 512), "%d号" % n_un, tag))
    print()

    print("=" * 78)
    print("引擎字模区（逐 charBase）—— 这是「任何一页只要用了该 charBase 就必被写」的号")
    print("=" * 78)
    for c in sorted(atlas):
        if not TEXT_CB[c]:
            continue
        lo, hi = atlas[c]
        print("  charBase=%d（%2d 条文本层）⇒ 全局 [%4d,%4d)  物理 cb%d 整块 + cb%d 头 32B"
              % (c, TEXT_CB[c], lo, hi, c, (c + 1) % 4))
    print()

    print("=" * 78)
    print("现有池子 6 段的落点判定")
    print("=" * 78)
    # (人口, base, n, 服务层 charBase)  —— v36 段表
    segs = [(0, 384, 32, 1, "p0-a"), (0, 946, 22, 1, "p0-b"),
            (1, 514, 127, 2, "p1"), (2, 192, 32, 0, "p2-a"), (2, 320, 32, 0, "p2-b")]
    for dom, base, n, c, nm in segs:
        g_lo = c * 512 + base
        g_hi = g_lo + n
        hit_oth = [k for k in range(g_lo, g_hi) if k in oth]
        hit_atl = [k for k in range(g_lo, g_hi) if k in atl]
        verdict = "✓ 干净" if not hit_oth and not hit_atl else \
                  ("⚠ 撞静态美术 %d 号" % len(hit_oth) if hit_oth else "") + \
                  ("⚠ 落字模区 %d 号" % len(hit_atl) if hit_atl else "")
        print("  %-5s 层内[%3d,%3d) charBase=%d ⇒ 全局[%4d,%4d)  %s"
              % (nm, base, base + n, c, g_lo, g_hi, verdict))
    print()

    print("=" * 78)
    print("判定")
    print("=" * 78)
    if empty_blocks:
        print("  ★ 存在整块未被写的 char block：%s" %
              ", ".join("cb%d" % c for c in empty_blocks))
    else:
        print("  ✗ **不存在任何「整块从未被写」的 char block** ——")
        print("    四个块都被「静态美术」或「某个 charBase 的引擎字模区」写过，")
        print("    而 charBase 分布（cb0×24 / cb1×4 / cb2×20 / cb3×4）说明四个块")
        print("    都有模板指进去 ⇒ **绝对号池（全局安全区）在数学上不存在**。")
    print()
    un_all = [k for k in range(NBG) if k not in oth and k not in atl]
    print("  全局「从未被写过」的号共 %d 个（%.0f%%）" % (len(un_all), 100.0 * len(un_all) / NBG))
    # 连续段
    if un_all:
        runs, s, p = [], un_all[0], un_all[0]
        for k in un_all[1:]:
            if k == p + 1:
                p = k
            else:
                runs.append((s, p))
                s = p = k
        runs.append((s, p))
        big = sorted(runs, key=lambda r: r[1] - r[0], reverse=True)[:6]
        print("  最大连续段（前 6）：" +
              "  ".join("[%d,%d)%d号" % (a, b + 1, b - a + 1) for a, b in big))
    return 0


if __name__ == "__main__":
    sys.exit(main())
