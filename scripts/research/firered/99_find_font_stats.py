#!/usr/bin/env python3
"""调研(99) 精确找出字库：用「汉字图形的统计特征」筛候选区。

═══════════════════════════════════════════════════════════════════════════
【(98) 为什么全是噪声】
═══════════════════════════════════════════════════════════════════════════
我把 `0xFF` 当空白去画，但 1bpp 里 `1` = 有墨，`0xFF` = **全黑**。
而且起点没对齐，切出来的都是错位的噪声。

【正确的筛选判据：汉字位图有很独特的统计特征】
  · 每个字块的墨量占比稳定在 **25%~45%**（汉字不会太满也不会太空）
  · 相邻字块之间**墨量方差小**（都是字，不会忽空忽满）
  · 字块内**行墨量呈钟形**（顶部/底部留白，中间密）
  · 字块间**互不相同**（不同字）

噪声/压缩数据的墨量占比会乱跳，行分布也不会呈钟形。

【做法】
 ① 扫全 ROM 所有 32KB 块，对每块试「每字 N 字节」的切法（N=22/24/32）
 ② 对每种切法，算上述四个指标
 ③ 得分最高的区 = 字库
 ④ 把该区按最优参数画出来

用法：python scripts/research/firered/99_find_font_stats.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
BASE = 0x08000000


def popcount_bytes(blob: bytes) -> int:
    return sum(bin(b).count("1") for b in blob)


def score_zone(rom: bytes, off: int, per: int, count: int = 200) -> tuple:
    """对 off 起、每字 per 字节的切法打分。

    返回 (墨量均值, 墨量标准差, 块间重复数, 钟形得分)
    """
    cap = per * 8
    inks = []
    blocks = []
    for k in range(count):
        blob = rom[off + k * per: off + (k + 1) * per]
        if len(blob) < per:
            break
        inks.append(popcount_bytes(blob))
        blocks.append(blob)
    if len(inks) < 50:
        return (0, 999, 999, 0)

    inks = np.array(inks, dtype=float)
    fill = inks / cap
    mean_fill = float(fill.mean())
    # 只认「填充率在 15%~70%」的区（汉字特征）
    if not (0.15 <= mean_fill <= 0.70):
        return (mean_fill, 999, 999, 0)

    std_fill = float(fill.std())
    # 块间重复（字库不该大量重复）
    uniq = len(set(blocks))
    dup = len(blocks) - uniq

    # 钟形：把每块按行切开，看行墨量
    row_bytes = per // 11 if per >= 11 else per // 8
    return (mean_fill, std_fill, dup, 0)


def main() -> int:
    zh = FR_ZH.read_bytes()
    n = len(zh)

    print("=" * 78)
    print("① 扫全 ROM：找「每字 N 字节、填充率像汉字」的区")
    print("=" * 78)
    best = []
    for per in (22, 24, 32):
        for base in range(0, n - 0x8000, 0x4000):
            mf, sf, dup, _ = score_zone(zh, base, per, 200)
            if sf > 998:
                continue
            if 0.20 <= mf <= 0.55 and sf < 0.12:
                best.append((sf, mf, dup, per, base))

    best.sort()
    print(f"  候选 {len(best)} 个（按填充率标准差升序，越小越整齐）")
    print(f"  {'区':>14} {'每字字节':>8} {'填充率':>7} {'标准差':>7} {'重复':>5}")
    seen = set()
    shown = 0
    for sf, mf, dup, per, base in best:
        key = (per, base // 0x8000)
        if key in seen:
            continue
        seen.add(key)
        print(f"  0x{BASE+base:08X} {per:>8} {mf:>6.1%} {sf:>7.3f} {dup:>5}")
        shown += 1
        if shown >= 15:
            break

    # ── ② 对最佳候选画出来 ────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 画最佳候选")
    print("=" * 78)
    if not best:
        print("  没有候选")
        return 0

    for sf, mf, dup, per, base in best[:3]:
        print(f"\n  ==== 0x{BASE+base:08X}  每字 {per} 字节  "
              f"填充 {mf:.1%} 标准差 {sf:.3f} ====")
        # 试两种行宽
        for rb, h in ((per // 11, 11), (per // 12, 12),
                      (per // 8, 8)):
            if rb * h > per:
                continue
            print(f"\n    --- 按 {rb} 字节/行 × {h} 行 ---")
            for k in range(3):
                blob = zh[base + k * per: base + (k + 1) * per]
                print(f"    第{k}字:")
                for y in range(h):
                    row = blob[y * rb:(y + 1) * rb]
                    if len(row) < rb:
                        break
                    bits = int.from_bytes(row, "big")
                    total = rb * 8
                    line = "".join(
                        "#" if (bits >> (total - 1 - x)) & 1 else "."
                        for x in range(total))
                    print(f"      {line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
