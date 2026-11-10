#!/usr/bin/env python3
"""调研⑳ 火红文本的**存放布局**：原地改写 vs 写新区改指针，各自占多少。

═══════════════════════════════════════════════════════════════════════════
【为什么必须做这一步】
═══════════════════════════════════════════════════════════════════════════
用户描述的两条策略：
   · 常规文本「有指针 → 写新区改指针」「无指针 → 缩短译文」
   · 等长/等距块「整块写新区 + 改整块指针」

⑩ 只统计了「指向新增区」的指针（7,711 槽 / 99.5% 被改指），
那只能证明**有指针的那部分**。真正没答的是：

   **「无指针」的文本（就地改写的）有多少？它怎么处理长度？**

本脚本用「同偏移比对」直接回答：
   · 原版该位置是日文文本，汉化该位置是 F7 文本 ⇒ **原地改写**
   · 原版该位置是日文文本，汉化该位置是 00 填充 ⇒ 原文被搬走，坑被清空
   · 原版是文本，汉化是别的 ⇒ 需要单独看

并对**原地改写**的每一段，比较「原日文串长」与「新中文串长」：
   · 新串更短 ⇒ 后面必须补 00（这就是「缩短译文」的实证）
   · 新串等长 ⇒ 最省事
   · 新串更长 ⇒ 不可能原地，说明是别的机制

═══════════════════════════════════════════════════════════════════════════
【Gen3 日文文本判据】
═══════════════════════════════════════════════════════════════════════════
日版字符集大致：
   0x00        空格/占位
   0x01–0x1F   假名（部分）
   0x40–0x5A   更多假名/符号
   0xA1–0xDF   假名（国际版位置）
   0xF7 等     控制/扩展前缀
   0xFF        串尾

判据用「≥70% 字节落在 0x01–0xDF 区间、且以 0xFF 结尾、长度 3–200」，
足够把「日文文本」和「代码/位图」分开（代码段 0x00–0x1F 虽多但不会以 FF 结尾成串）。

用法：python scripts/research/firered/20_text_layout.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

BASE = 0x08000000
SEG_MIN, SEG_MAX = 3, 220


def is_ja_text(b: bytes) -> bool:
    """判断一段（不含 0xFF 结尾）是不是日文文本。"""
    if not (SEG_MIN <= len(b) <= SEG_MAX):
        return False
    if not b:
        return False
    ok = sum(1 for x in b if 0x01 <= x <= 0xDF)
    return ok >= len(b) * 0.70


def is_zh_text(b: bytes) -> bool:
    """判断一段是不是火红中文（F7 hi lo 三元组为主）。"""
    if not b:
        return False
    n_f7 = b.count(0xF7)
    return n_f7 >= 2 and n_f7 * 3 >= len(b) * 0.5


def read_seg(rom: bytes, o: int, limit: int = SEG_MAX + 2) -> bytes:
    """从 o 读到 0xFF（不含），最多 limit 字节。返回 None 表示没找到 FF。"""
    e = rom.find(b"\xff", o, o + limit)
    if e < 0:
        return b""
    return rom[o:e]


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("一、F7 在整个 ROM 的分布（按 64KB 段）—— 看清汉化把中文放在哪")
    print("=" * 78)
    fr = [0] * (n // 0x10000 + 1)
    i = zh.find(b"\xf7")
    while i >= 0:
        fr[i // 0x10000] += 1
        i = zh.find(b"\xf7", i + 1)
    tot = sum(fr)
    print(f"F7 总数 {tot:,}")
    print(f"  {'段起始 ROM':>14} {'F7 数':>8} {'占比':>7}")
    cum = 0
    for s, c in enumerate(fr):
        if c < 100:
            continue
        cum += c
        print(f"  0x{BASE+s*0x10000:08X}  {c:>8,}  {c/tot*100:>6.2f}%")
    print(f"  （只列 ≥100 的段，累计 {cum/tot*100:.2f}%）")

    print("\n" + "=" * 78)
    print("二、同偏移比对：汉化在新文本区之外，还在哪里放了中文")
    print("=" * 78)

    # 新文本区（已确认）
    NEW_ZONES = [(0x6D0000, 0x722000), (0xAF5000, 0xAFB000)]

    def in_new(o: int) -> bool:
        return any(lo <= o < hi for lo, hi in NEW_ZONES)

    # 找出所有「汉化有中文串」的起点（不在新文本区）
    print("\n扫描：汉化侧存在 F7 中文串、且不在新文本区的起点")
    starts = []
    i = 0
    while i < n - 4:
        if zh[i] == 0xF7:
            seg = read_seg(zh, i)
            if seg and is_zh_text(seg) and not in_new(i):
                starts.append(i)
                i += max(1, len(seg))
                continue
        i += 1
    print(f"  找到 {len(starts):,} 处「区外中文串」")
    if starts:
        by_seg = Counter(s // 0x10000 for s in starts)
        print(f"  分布（按 64KB）：")
        for s, c in by_seg.most_common(15):
            print(f"    0x{BASE+s*0x10000:08X}  {c:>5} 处")
        print(f"  采样 20 处：")
        print(f"    {'ROM':>14} {'新串长':>6} {'原串长':>6} {'原串是不是日文':>14} {'状态'}")
        same_len = shorter = longer = noja = 0
        for o in starts[:2000]:
            zs = read_seg(zh, o)
            js = read_seg(ja, o)
            if not js or not is_ja_text(js):
                noja += 1
                state = "原地无日文(新增/改写)"
            else:
                if len(zs) == len(js):
                    same_len += 1
                    state = "等长"
                elif len(zs) < len(js):
                    shorter += 1
                    state = "新串更短(需补00)"
                else:
                    longer += 1
                    state = "新串更长(!)"
            if len(starts[:20]) and o in starts[:20]:
                print(f"    0x{BASE+o:08X} {len(zs):>6} {len(js) if js else 0:>6} "
                      f"{'是' if js and is_ja_text(js) else '否':>14}  {state}")
        print(f"\n  前 2000 处统计：等长 {same_len}  更短 {shorter}  "
              f"更长 {longer}  原地原本非日文 {noja}")

    print("\n" + "=" * 78)
    print("三、原日文文本的「坑」现在是什么（被清空 / 被复用）")
    print("=" * 78)
    # 在原版里找日文串起点：用「前一字节是 FF」当边界
    ja_texts = []
    o = 0
    while o < 0x6D0000:      # 只看原版主数据区（0x6D0000 之后是新增区）
        if ja[o] not in (0xFF, 0x00):
            seg = read_seg(ja, o)
            if seg and is_ja_text(seg):
                ja_texts.append((o, len(seg)))
                o += len(seg) + 1
                continue
        o += 1
    print(f"原版主数据区（0..0x6D0000）里的日文串：{len(ja_texts):,} 处")

    state = Counter()
    for o, L in ja_texts:
        zs = read_seg(zh, o, limit=L + 4)
        if zh[o:o + L].strip(b"\x00") == b"":
            state["整段清成 00"] += 1
        elif zs and is_zh_text(zs):
            state["原地换成中文"] += 1
        elif zh[o:o + L] == ja[o:o + L]:
            state["原样保留"] += 1
        else:
            state["其他"] += 1
    print(f"  这些坑在汉化版里的状态：")
    for k, v in state.most_common():
        print(f"    {k:<16} {v:>6,}  ({v/len(ja_texts)*100:>5.1f}%)")

    print("\n" + "=" * 78)
    print("四、结论要素")
    print("=" * 78)
    print("  · 若「整段清成 00」占多数 ⇒ 原文全部搬走，指针全部改指（纯「写新区」）")
    print("  · 若「原地换成中文」占多数 ⇒ 大量就地改写（这才需要「缩短译文」）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
