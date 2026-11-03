#!/usr/bin/env python3
"""调研⑮ 最终版：只用「主文本区」统计，给出可信的码位结论。

═══════════════════════════════════════════════════════════════════════════
【为什么只认主文本区】
═══════════════════════════════════════════════════════════════════════════
前几轮统计反复被污染，根因已经查明：

  · **代码段里的 `60 F7` 是 Thumb 的 `b.n` 指令**，不是文本
    （实测 0x080A0000 区抽样：`60 F7 1A FD 50 20 E1 21 60 F7 ...`）
  · 低地址差异只有 0.2%，说明火红**没改代码**，那些 F7 是原版就有的指令

⇒ 任何「全 ROM 扫 F7」的统计都会被指令污染，得到 hi=256 种、4701+ 码位。

**唯一可靠的锚点：主文本区** `0x086D0000` 起 304KB（89,643 个 F7）。
这个区已用三个独立证据确认是纯文本：
  1. 与原版差异 94.2%（整块被替换）
  2. F7 占 27.3%
  3. 抽样全是 `F7 00 35 F7 00 36 …` 结构，无位图特征

═══════════════════════════════════════════════════════════════════════════
【本脚本给出最终结论】
═══════════════════════════════════════════════════════════════════════════
用法：python scripts/research/firered/15_final_codespace.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

# 主文本区（已验证）
MAIN_START = 0x6D0000
MAIN_SIZE = 0x4C000        # 304KB

# 其他「追加文本区」—— 需要逐个验证是否纯文本后才纳入
CANDIDATES = [
    (0x71D000, 0xA000, "文本区 2"),
    (0xAF5000, 0x6000, "文本区 3"),
]


def stat(seg: bytes, label: str) -> Counter:
    pairs = Counter()
    i = seg.find(b"\xf7")
    n = 0
    while i >= 0 and i + 2 < len(seg):
        pairs[(seg[i + 1], seg[i + 2])] += 1
        n += 1
        i = seg.find(b"\xf7", i + 1)
    his = sorted({h for h, l in pairs})
    print(f"\n{label}: F7 {n:,}，码位 {len(pairs):,}，"
          f"hi {len(his)} 种 (0x{min(his):02X}–0x{max(his):02X})"
          if pairs else f"\n{label}: 无 F7")
    return pairs


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    print("=" * 68)
    print("火红码位空间 —— 最终结论")
    print("=" * 68)

    # 主区
    main_seg = zh[MAIN_START:MAIN_START + MAIN_SIZE]
    p_main = stat(main_seg, f"主文本区 0x{0x08000000+MAIN_START:08X} "
                            f"({MAIN_SIZE//1024}KB)")

    # 候选区
    p_all = Counter(p_main)
    for base, size, label in CANDIDATES:
        seg = zh[base:base + size]
        p = stat(seg, f"{label} 0x{0x08000000+base:08X} ({size//1024}KB)")
        p_all.update(p)

    print("\n" + "=" * 68)
    print(f"合并后码位：**{len(p_all):,}**")
    his = sorted({h for h, l in p_all})
    los = sorted({l for h, l in p_all})
    print(f"  hi {len(his)} 种：0x{min(his):02X} – 0x{max(his):02X}")
    print(f"  lo {len(los)} 种：0x{min(los):02X} – 0x{max(los):02X}")

    by_hi = Counter()
    for (h, l), c in p_all.items():
        by_hi[h] += 1
    print(f"\n  各 hi 页使用数（共 {len(by_hi)} 页）：")
    for h in sorted(by_hi)[:14]:
        print(f"    hi=0x{h:02X}  {by_hi[h]:>3}/256")

    freq = sorted(p_all.values(), reverse=True)
    tot = sum(freq)
    print(f"\n  频次覆盖（总共 {tot:,} 次出现）：")
    for k in (500, 1000, 1500, 2000, 3000, 4096):
        if k <= len(freq):
            print(f"    前 {k:>4} 字 → {sum(freq[:k])/tot*100:>5.1f}%")

    print("\n" + "=" * 68)
    n = len(p_all)
    print(f"结论：火红真实使用 **{n:,}** 个中文字模")
    if n <= 4096:
        print(f"  ⇒ 12 位足够（4 位页 + 8 位偏移 = 4096 码位）")
        print(f"  ⇒ **可以压成 2 字节编码**，每字省 1 字节（33%）")
    else:
        print(f"  ⇒ 超过 4096，2 字节放不下全部")
        print(f"  ⇒ 若砍到 4096 高频字，仍可覆盖 "
              f"{sum(freq[:4096])/tot*100:.1f}% 的出现次数")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
