#!/usr/bin/env python3
"""调研⑥ 直接找火红的**中文点阵字模区**，再反推码位表。

═══════════════════════════════════════════════════════════════════════════
【思路转变】
═══════════════════════════════════════════════════════════════════════════
前两轮失败原因：
  · 统计 F7 的 (hi,lo) → 被非文本数据污染，得到不可信的 8000+ 码位
  · 找指针数组表 → 火红不用指针数组做字库索引

**换一个必定成立的锚点：点阵字模本身。**

汉字点阵（比如 12×12 或 12×16）在 ROM 里是**成片重复的位图**，
特征非常明显：
  · 每个字模固定字节数（12×12 1bpp = 24 字节；12×16 = 32 字节；
    8×12 4bpp = 48 字节 …）
  · 字模之间**墨量（非零字节数）分布集中**（汉字墨量相近）
  · 连续几百个字的墨量呈相似分布，而随机数据墨量分布完全不同

方法：滑动扫描，把 ROM 切成固定步长的块，统计每块的「非零字节比例」，
找连续 N 块（N≥2000）的墨量分布都在合理区间的区域。
那个区域的起点就是字模表起点，步长就是字模大小。

用法：python scripts/research/firered/06_find_glyph_bitmap.py
"""
from __future__ import annotations

import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"


def ink_ratio(seg: bytes) -> float:
    """非零字节占比（粗略墨量）。"""
    if not seg:
        return 0.0
    return sum(1 for b in seg if b) / len(seg)


def scan(rom: bytes, step: int, min_run: int = 1500) -> list:
    """找连续 min_run 个块、每块墨量都在 0.05..0.6 的区段。"""
    out = []
    start = None
    run = 0
    for o in range(0, len(rom) - step, step):
        r = ink_ratio(rom[o:o + step])
        ok = 0.05 <= r <= 0.60
        if ok:
            if start is None:
                start, run = o, 1
            else:
                run += 1
        else:
            if run >= min_run:
                out.append((run, start, step))
            start, run = None, 0
    if run >= min_run:
        out.append((run, start, step))
    return out


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    print(f"汉化 {FR_ZH.name}\n原版 {FR_JA.name}\n")

    print("=== 按不同步长找「大片规律位图」===")
    print(f"{'步长':>5} {'连续块数':>9} {'ROM 地址':>12} {'总字节':>10}")
    found = []
    for step in (16, 24, 32, 48, 64):
        for run, start, st in scan(zh, step):
            total = run * step
            if total < 20000:
                continue
            found.append((step, run, start, total))
            print(f"{step:>5} {run:>9,} 0x{0x08000000 + start:08X} {total:>10,}")

    if not found:
        print("  没找到")
        return 0

    # 对最大的那几段，看原版同区域是什么（应该是空的/不同的）
    found.sort(key=lambda x: -x[3])
    print("\n=== 最大几段在原版里的对照 ===")
    for step, run, start, total in found[:4]:
        seg_zh = zh[start:start + min(total, 0x2000)]
        seg_ja = ja[start:start + min(total, 0x2000)]
        same = seg_zh == seg_ja
        print(f"  步长{step} @0x{0x08000000+start:08X} 共{total:,}B  "
              f"原版同区相同={same}")
        if not same:
            # 差异比例
            n = min(len(seg_zh), len(seg_ja))
            diff = sum(1 for i in range(n) if seg_zh[i] != seg_ja[i])
            print(f"      前{n}B 差异 {diff} ({diff/n*100:.0f}%)")

    print("\n=== 判读 ===")
    print("  若某步长下找到几十 KB 的连续区、且原版同区差异很大 ⇒")
    print("  那就是汉化新增的中文字模区，步长即**每字模字节数**。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
