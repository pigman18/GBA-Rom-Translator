#!/usr/bin/env python3
"""调研⑧ 解剖火红最大的差异区（0x086D0000，335KB），判断是字模还是文本。

═══════════════════════════════════════════════════════════════════════════
【上一轮定位】
═══════════════════════════════════════════════════════════════════════════
汉化 vs 原版差异最大的连续区间：
    ROM 0x086D0000 起，87 个 4KB 块，**335,756 字节**，密度 94.2%

335KB 这个体量很关键：
  · 若是一个汉字 32 字节 → 可放 ~10,000 个字模
  · 若是 F7 三字节编码的文本 → 可放 ~100,000 字

两种都可能。本脚本用**数据形态**判定：

  位图字模的特征：
    · 按固定步长（16/24/32/48…）切分时，每块墨量分布集中
    · 相邻块之间没有明显的 0xFF 串

  文本的特征：
    · 大量 0xFF（字符串终止符）
    · 大量 F7（编码前缀）
    · 字节值集中在文本区（0x00-0x5A、0xA1-0xFF）

用法：python scripts/research/firered/08_dissect_region.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
START = 0x6D0000       # 文件偏移（ROM 0x086D0000 - 0x08000000）
SIZE = 0x58000         # 87 个 4KB 块


def main() -> int:
    rom = FR_ZH.read_bytes()
    seg = rom[START:START + SIZE]
    print(f"区间 文件 0x{START:08X} (ROM 0x{0x08000000+START:08X})"
          f"  {len(seg):,} B\n")

    # 1) 字节频次
    c = Counter(seg)
    total = len(seg)
    print("=== 最频繁的 12 个字节 ===")
    for b, n in c.most_common(12):
        print(f"  0x{b:02X}  {n:>8,}  {n/total*100:>5.1f}%")
    print(f"\n  0xFF 占比 {c.get(0xFF,0)/total*100:.1f}%"
          f"   0xF7 占比 {c.get(0xF7,0)/total*100:.1f}%")
    print(f"  0x00 占比 {c.get(0,0)/total*100:.1f}%")

    # 2) 按固定步长测墨量一致性（字模特征）
    print("\n=== 步长扫描：每块墨量集中度（变异系数越小越像字模）===")
    print(f"{'步长':>5} {'块数':>7} {'墨量均值':>9} {'变异系数':>9}")
    import statistics
    for step in (16, 24, 32, 48, 64, 96, 128):
        vals = []
        for o in range(0, len(seg) - step, step):
            blk = seg[o:o + step]
            vals.append(sum(1 for b in blk if b) / step)
        if not vals:
            continue
        mean = statistics.mean(vals)
        sd = statistics.pstdev(vals)
        cv = sd / mean if mean else 0
        print(f"{step:>5} {len(vals):>7,} {mean*100:>8.1f}% {cv:>9.3f}")

    # 3) 0xFF 串长度分布（文本特征）
    print("\n=== 0xFF 连续串长度分布（文本里 0xFF 是串结束符）===")
    runs = Counter()
    k = 0
    while k < len(seg):
        if seg[k] == 0xFF:
            j = k
            while j < len(seg) and seg[j] == 0xFF:
                j += 1
            runs[j - k] += 1
            k = j
        else:
            k += 1
    for ln, n in runs.most_common(8):
        print(f"  {ln:>3} 个连续 0xFF: {n:>7,} 次")

    # 4) 抽样打印
    print("\n=== 抽样：区间开头 3 段各 48 字节 ===")
    for off in (0, 0x2000, 0x20000):
        s = seg[off:off + 48]
        print(f"  +0x{off:06X}: " + " ".join(f"{b:02X}" for b in s))

    print("\n=== 判读 ===")
    ff = c.get(0xFF, 0) / total
    f7 = c.get(0xF7, 0) / total
    if ff > 0.15 or f7 > 0.10:
        print(f"  0xFF={ff*100:.0f}% / F7={f7*100:.0f}% 偏高 ⇒ **倾向文本区**")
    else:
        print(f"  0xFF={ff*100:.0f}% / F7={f7*100:.0f}% 都很低 ⇒ **倾向字模/位图区**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
