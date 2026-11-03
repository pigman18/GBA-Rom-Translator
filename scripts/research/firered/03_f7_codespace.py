#!/usr/bin/env python3
"""调研③ 火红 F7 编码的**有效码位数量** —— 能不能压成 2 字节？

═══════════════════════════════════════════════════════════════════════════
【已确认】
═══════════════════════════════════════════════════════════════════════════
火红用 **3 字节编码 `F7 hi lo`**（实测相邻 F7 间距 100,711 次都是 3）。

用户原本的希望是「火红只用 f7，能减少 1 位编码」——
如果真是 2 字节，每字能省 1 字节。但实测是 3 字节，**和我们的 F9 一样**。

不过还有个关键问题没答：**火红的码位空间是多少？**
  · 如果是 16 位（hi,lo 各 1 字节，共 65536 个码位）→ 和 F9 00 相同
  · 如果 hi 只用低 4 位（16 × 256 = 4096）→ 更紧凑

这决定「能不能改造成 2 字节」。

═══════════════════════════════════════════════════════════════════════════
【方法】
═══════════════════════════════════════════════════════════════════════════
统计 F7 后面**两个字节的实际取值范围**：
  · hi 用到多少种值？最大值？
  · lo 用到多少种值？
  · 实际出现过的 (hi,lo) 组合数 = 真正用到的码位数

如果实际码位数 ≤ 4096，那 12 位就够（可以压进 2 字节：4 位页 + 8 位偏移，
配合现有的单字节字符集）。

用法：python scripts/research/firered/03_f7_codespace.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"


def main() -> int:
    zh = FR_ZH.read_bytes()
    pairs = Counter()          # (hi, lo) -> 次数
    i = zh.find(b"\xf7")
    n = 0
    while i >= 0 and i + 2 < len(zh):
        pairs[(zh[i + 1], zh[i + 2])] += 1
        n += 1
        i = zh.find(b"\xf7", i + 1)

    his = sorted({h for h, l in pairs})
    los = sorted({l for h, l in pairs})
    print(f"F7 序列总数 {n:,}")
    print(f"\nhi 字节用到 {len(his)} 种: "
          f"{' '.join(f'{b:02X}' for b in his[:24])}"
          f"{' …' if len(his) > 24 else ''}")
    print(f"  范围 0x{min(his):02X} – 0x{max(his):02X}")
    print(f"lo 字节用到 {len(los)} 种: "
          f"{' '.join(f'{b:02X}' for b in los[:24])}"
          f"{' …' if len(los) > 24 else ''}")
    print(f"  范围 0x{min(los):02X} – 0x{max(los):02X}")

    print(f"\n**实际用到的 (hi,lo) 组合数：{len(pairs):,}**")
    print(f"理论空间（hi 种类 × lo 种类）：{len(his) * len(los):,}")

    # 按 hi 分组，看每页用了多少
    print("\n按 hi 分页的使用情况（每页 256 个 lo 位）:")
    by_hi = Counter()
    for (h, l), c in pairs.items():
        by_hi[h] += 1
    for h in sorted(by_hi)[:20]:
        used = by_hi[h]
        desc = "满" if used > 250 else ("半" if used > 128 else "稀疏")
        print(f"  hi=0x{h:02X}  用到 {used:>3}/256 个 lo 值  ({desc})")
    if len(by_hi) > 20:
        print(f"  … 另有 {len(by_hi) - 20} 个 hi 值")

    print("\n=== 结论 ===")
    total = len(pairs)
    if total <= 256:
        print(f"  只用到 {total} 个码位 ⇒ 理论上 8 位就够（但需避开控制码）")
    elif total <= 4096:
        print(f"  用到 {total} 个码位 ⇒ 12 位够用 ⇒ **可以压成 2 字节**"
              f"（4 位页 + 8 位偏移）")
    else:
        print(f"  用到 {total} 个码位 ⇒ 超过 12 位，压成 2 字节不安全")
    print("\n注：压缩到 2 字节还需满足「前缀字节不能与现有单字节字符集冲突」。")
    print("    火红用的是 0xF7，若我们要用 2 字节方案，需要找一个空闲前缀，")
    print("    并且让 lo 字节承载 8 位页号或偏移 —— 这一步要看单字节字符集分布。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
