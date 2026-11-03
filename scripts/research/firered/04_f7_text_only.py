#!/usr/bin/env python3
"""调研④ 校验上一轮的「11735 个码位」是不是被非文本数据污染了。

═══════════════════════════════════════════════════════════════════════════
【为什么怀疑】
═══════════════════════════════════════════════════════════════════════════
上一轮统计火红 F7 的 (hi,lo) 组合得到 **11,735 个码位**，
这个数字可疑：

1. 火红汉化 2.2 的译文汉字数不可能有 11000+ 个不重复字
   （常用汉字 3500，GB2312 全表 6763）
2. hi 用到全部 256 种值、且 0x00–0x08 每页都「满 256」
   —— 真实文本不会这么均匀

⇒ 说明 ROM 里有**非文本数据**恰好含 F7，被当成了编码前缀。典型来源：
   · 压缩图形（LZ77 流里任意字节都可能出现）
   · 音频采样
   · 字库本身（位图数据）

═══════════════════════════════════════════════════════════════════════════
【方法：只统计「像文本」的区域】
═══════════════════════════════════════════════════════════════════════════
GBA 文本段有特征：
  · 周围有大量 0xFF（字符串结束符）或 0x00
  · F7 前后是密集的文本字节，而不是随机数据

判据：取 F7 附近 ±16 字节，统计「文本字节」（0x00-0x5A 的字符集区、
0xF7 编码、0xFE/0xFF 控制）的占比。占比高的才算文本。

用法：python scripts/research/firered/04_f7_text_only.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"

# 文本常见字节：0x00-0x5A（拉丁/数字/假名区）、0xA1-0xFE（扩展）、0xF7 编码、0xFF 结束
def is_textish(b: int) -> bool:
    return (b <= 0x5A) or (0xA1 <= b <= 0xFF)


def main() -> int:
    zh = FR_ZH.read_bytes()
    total = 0
    kept = Counter()
    kept_n = 0
    dropped_area = Counter()

    i = zh.find(b"\xf7")
    while i >= 0 and i + 2 < len(zh):
        total += 1
        lo, hi = max(0, i - 16), min(len(zh), i + 19)
        seg = zh[lo:hi]
        n_text = sum(1 for b in seg if is_textish(b))
        ratio = n_text / len(seg)
        if ratio >= 0.85:
            kept[(zh[i + 1], zh[i + 2])] += 1
            kept_n += 1
        else:
            # 记录被丢掉的区域，便于确认「确实是压缩/图形数据」
            dropped_area[i // 0x10000] += 1
        i = zh.find(b"\xf7", i + 1)

    print(f"F7 总数 {total:,}")
    print(f"判为文本的 {kept_n:,}（{kept_n/total*100:.1f}%）")
    print(f"**文本里实际用到的码位：{len(kept):,}**")

    his = sorted({h for h, l in kept})
    print(f"\n文本中 hi 用到 {len(his)} 种，范围 0x{min(his):02X}–0x{max(his):02X}")
    by_hi = Counter()
    for (h, l), c in kept.items():
        by_hi[h] += 1
    print("前 12 页：")
    for h in sorted(by_hi)[:12]:
        print(f"  hi=0x{h:02X}  用到 {by_hi[h]:>3}/256")

    print("\n被丢弃的 F7 分布（按 64KB 段，说明它们集中在非文本区）:")
    for seg, n in dropped_area.most_common(8):
        print(f"  0x{seg*0x10000:08X} 段  丢弃 {n:,} 个")

    print("\n=== 结论 ===")
    n = len(kept)
    if n <= 256:
        print(f"  {n} 个码位 ⇒ 8 位够")
    elif n <= 4096:
        print(f"  {n} 个码位 ⇒ **12 位够 ⇒ 可压成 2 字节**（4位页+8位偏移）")
    else:
        print(f"  {n} 个码位 ⇒ 超 12 位，2 字节不安全")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
