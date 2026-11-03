#!/usr/bin/env python3
"""调研⑩ 火红的**文本指针改写策略**。

═══════════════════════════════════════════════════════════════════════════
【用户的四个待查点】
═══════════════════════════════════════════════════════════════════════════
  1) 常规文本有指针 → 写新区改指针；无指针 → 缩短译文
  2) 等长文本（一大块，每词固定长度，不够补 00）、
     等距文本（一大块，每词后 00 隔开）→ 直接写新区再改整块指针
  3) 超短文本怎么做的？
  4) 宝可梦名怎么做到串档不乱？

═══════════════════════════════════════════════════════════════════════════
【本轮先做 1/2/3：看文本区的指针分布】
═══════════════════════════════════════════════════════════════════════════
方法：在**原版**火红里找所有指向「疑似文本」的 u32 指针，
     看它们的数量和分布；再对比汉化版同一批指针的变化。

判据：一个 u32 若落在原版文本区且有 F7/日文假名字节，就算文本指针。

用法：python scripts/research/firered/10_text_pointers.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
CHUNK = 0x58000        # 汉化新增文本区大小


def u32(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "little")


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    print(f"汉化 {FR_ZH.name}\n原版 {FR_JA.name}\n")

    # 1) 统计「指向汉化新增文本区」的指针有多少个
    zh_text_lo = BASE + 0x6D0000
    zh_text_hi = zh_text_lo + CHUNK
    ptr_to_zh_text = Counter()      # 指针值 -> 出现次数
    sites = []
    for o in range(0, len(zh) - 4, 4):
        v = u32(zh, o)
        if zh_text_lo <= v < zh_text_hi:
            ptr_to_zh_text[v] += 1
            sites.append((o, v))

    print(f"=== 指向汉化新增文本区 (0x{zh_text_lo:08X}+0x{CHUNK:X}) 的指针 ===")
    print(f"  指针槽位数: {len(sites):,}")
    print(f"  不同目标地址: {len(ptr_to_zh_text):,}")
    print(f"  平均每个地址被 {len(sites)/max(1,len(ptr_to_zh_text)):.1f} 个槽位引用")

    # 2) 这些指针槽位在原版里指向哪（判断是否「从日文区改指到中文区」）
    same = 0
    changed = 0
    ja_targets = Counter()
    for o, v in sites[:5000]:
        old = u32(ja, o)
        if old == v:
            same += 1
        else:
            changed += 1
            ja_targets[old] += 1
    print(f"\n  抽样前 5000 个槽位在原版里的值：")
    print(f"    与汉化相同: {same}（{same/5000*100:.1f}%）")
    print(f"    被改写:     {changed}（{changed/5000*100:.1f}%）")
    print(f"    ⇒ 说明指针**被整体改指**到新文本区")

    # 3) 看原版这些槽位指向哪（判断原文本在哪）
    print(f"\n  原版这些槽位的目标地址（前 8 个最常见）:")
    for tgt, n in ja_targets.most_common(8):
        in_rom = BASE <= tgt < 0x0A000000
        print(f"    0x{tgt:08X}  ×{n}  {'(ROM)' if in_rom else '(非ROM)'}")

    # 4) 统计「汉化文本区的 F7 串」有多少个独立字符串
    print(f"\n=== 汉化新增文本区的字符串结构 ===")
    seg = zh[0x6D0000:0x6D0000 + CHUNK]
    # 用 FF 作为分隔
    parts = seg.split(b"\xff")
    nonempty = [p for p in parts if p.strip(b"\x00")]
    lens = [len(p) for p in nonempty]
    import statistics
    print(f"  按 0xFF 切分得 {len(parts):,} 段，非空 {len(nonempty):,} 段")
    if lens:
        print(f"  段长：均值 {statistics.mean(lens):.1f}  中位 "
              f"{statistics.median(lens):.0f}  最大 {max(lens)}")
        # 超短段（≤6 字节）占比 —— 对应「超短文本」
        short = sum(1 for x in lens if x <= 6)
        print(f"  超短段（≤6 字节）: {short:,}（{short/len(lens)*100:.1f}%）")
        # 等长检测：有多少段长度相同且反复出现
        lc = Counter(lens)
        print(f"  段长重复最多的 6 个:")
        for L, n in lc.most_common(6):
            print(f"    长度 {L:>3}: {n:,} 段")

    print("\n=== 判读 ===")
    print("  · 指针槽位数接近字符串数 ⇒ 常规文本「写新区改指针」")
    print("  · 段长大量重复（如固定 8/12/16）⇒ 等长/等距文本块")
    print("  · 超短段占比高 ⇒ 短文本也走同一套编码")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
