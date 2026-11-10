#!/usr/bin/env python3
"""调研㉚ 五类文本处理总账（numpy 向量化，快速版）+ 宝可梦名表定案。

═══════════════════════════════════════════════════════════════════════════
【已确证的前提】
═══════════════════════════════════════════════════════════════════════════
 P1 汉化只用 F7（`F7 hi lo` 3 字节）
 P2 中文全部放在原版 **100% FF 的空区**：0x6D0000（304KB）、0xAF5000、
    以及 0x87000000 段之外的 0x8B00000/0x8EC0000/0x8E3/0x8E5/0x8ED/
    0x8FE/0x8FF/0x874 —— 实测这些区原版 orig_FF=100%
 P3 有 u32 指针可达的文本：改指针指向中文区，原文保留成孤儿
 P4 原版日文文本 97.9% 原样保留
 P5 原版是 1 字节编码

═══════════════════════════════════════════════════════════════════════════
【本脚本回答用户 5 问】
═══════════════════════════════════════════════════════════════════════════
 Q1 常规文本：有指针改指针？无指针缩短译文？ → 统计中文段的指针可达率
 Q2 等长块：整块写新区 + 改整块指针？        → 找「等长连续段」+ 块首指针
 Q3 等距块：同上？                          → 找「段+FF+段+FF」紧密序列
 Q4 超短文本：怎么做的？                     → 专看 ≤6 字节段的指针情况
 Q5 宝可梦名：串档不乱？                     → 名字表结构比对（向量化）

用法：python scripts/research/firered/30_five_categories_fast.py
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
ZONES = [(0x6D0000, 0x722000, "主文本区"), (0xAF5000, 0xAFB000, "文本区3")]


def main() -> int:
    zh_b = FR_ZH.read_bytes()
    ja_b = FR_JA.read_bytes()
    n = min(len(zh_b), len(ja_b))
    m = n // 4 * 4

    print("=" * 78)
    print("五类文本处理总账（向量化版）")
    print("=" * 78)

    # ── 中文段收集 ─────────────────────────────────────────────────
    segs = []
    for lo, hi, nm in ZONES:
        seg = zh_b[lo:hi]
        pos = 0
        while pos < len(seg):
            e = seg.find(b"\xff", pos)
            if e < 0:
                break
            if e > pos and seg[pos:e].count(0xF7) >= 1:
                segs.append((lo + pos, e - pos))
            pos = e + 1
    print(f"\n中文段：{len(segs):,} 条")
    offs = np.array([s[0] for s in segs], dtype=np.int64)
    lens = np.array([s[1] for s in segs], dtype=np.int64)

    # ── 指针普查 ───────────────────────────────────────────────────
    pz = np.frombuffer(zh_b[:m], dtype=np.uint32).astype(np.uint64)
    pa = np.frombuffer(ja_b[:m], dtype=np.uint32).astype(np.uint64)
    ok = (pz >= BASE) & (pz < BASE + n)
    tgt = (pz[ok] - BASE).astype(np.int64)
    ptr_cnt = Counter(tgt.tolist())

    has_ptr = np.array([1 if o in ptr_cnt else 0 for o in offs.tolist()],
                       dtype=np.int64)
    print(f"段首被 u32 直指：{int(has_ptr.sum()):,}"
          f"（{has_ptr.mean()*100:.1f}%）")

    # ── 等长 / 等距 ────────────────────────────────────────────────
    order = np.argsort(offs)
    so, sl = offs[order], lens[order]

    same_len_run = np.zeros(len(so), dtype=np.int64)   # 所在等长块长度
    gap = np.full(len(so), -1, dtype=np.int64)         # 到下一段的间隔

    i = 0
    while i < len(so):
        j = i
        while (j + 1 < len(so) and sl[j + 1] == sl[i]
               and so[j + 1] - (so[j] + sl[j]) == 1):
            j += 1
        ln = j - i + 1
        if ln >= 3:
            same_len_run[i:j + 1] = ln
        i = j + 1
    gap[:-1] = so[1:] - (so[:-1] + sl[:-1])

    # ── 分类 ───────────────────────────────────────────────────────
    cat = Counter()
    cat_lens = defaultdict(list)
    cat_ptr = Counter()

    for k in range(len(so)):
        tags = []
        if has_ptr[order[k]]:
            tags.append("直指针")
        if same_len_run[k] >= 3:
            tags.append(f"等长块({same_len_run[k]})")
        if gap[k] == 0:
            tags.append("等距紧邻")
        if sl[k] <= 6:
            tags.append("超短")
        key = "+".join(tags) if tags else "无特征"
        # 把等长块的块长归并成一个类
        key = key.replace("等长块", "等长块")
        cat[key] += 1
        cat_lens[key].append(int(sl[k]))
        cat_ptr[key] += int(has_ptr[order[k]])

    print(f"\n{'容器分类':<34} {'段数':>6} {'占比':>7} {'均长':>6} {'有指针':>7}")
    print("-" * 74)
    for k, v in cat.most_common(30):
        av = np.mean(cat_lens[k])
        print(f"{k:<34} {v:>6,} {v/len(so)*100:>6.1f}% {av:>6.1f} "
              f"{cat_ptr[k]:>7,}")

    # ── Q4 超短 ────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("Q4 超短文本（≤6 字节）")
    print("=" * 78)
    sh = np.flatnonzero(sl <= 6)
    shp = int(has_ptr[order[sh]].sum())
    print(f"  {len(sh):,} 条（{len(sh)/len(so)*100:.1f}%）")
    print(f"  有指针 {shp:,}（{shp/max(1,len(sh))*100:.1f}%）")
    lc = Counter(sl[sh].tolist())
    print("  长度分布：" + ", ".join(f"L{L}:{c}"
                                for L, c in sorted(lc.items())))
    print("  抽样 8 条：")
    for k in sh[:8]:
        o = int(so[k])
        print(f"    0x{BASE+o:08X} L={sl[k]} 汉字{zh_b[o:o+sl[k]].count(0xF7)} "
              f"ptr×{ptr_cnt.get(o,0)}  {zh_b[o:o+sl[k]+1].hex(' ')}")

    # ── Q2/Q3 块首指针 —— 决定「整块一个指针」还是「每段一个指针」──
    print("\n" + "=" * 78)
    print("Q2/Q3 块级指针：等长块 / 等距块是「块首一个指针」还是「每段各一个」")
    print("=" * 78)
    # 找等长块
    blocks = []
    i = 0
    while i < len(so):
        j = i
        while (j + 1 < len(so) and sl[j + 1] == sl[i]
               and so[j + 1] - (so[j] + sl[j]) == 1):
            j += 1
        if j - i + 1 >= 3:
            blocks.append((int(so[i]), int(so[j] + sl[j]), j - i + 1,
                           int(sl[i]), i, j))
        i = j + 1
    blocks.sort(key=lambda x: -x[2])
    print(f"  等长块 {len(blocks)} 个（≥3 段）")
    print(f"  {'块首 ROM':>14} {'段数':>5} {'每段长':>6} {'块总字节':>8} "
          f"{'块首指针':>8} {'块内指针数':>9}")
    for s, e, cnt2, L, i0, j0 in blocks[:15]:
        head = ptr_cnt.get(s, 0)
        inner = sum(1 for k in range(i0, j0 + 1) if ptr_cnt.get(int(so[k]), 0))
        print(f"  0x{BASE+s:08X} {cnt2:>5} {L:>6} {e-s:>8} "
              f"{('×'+str(head)) if head else '无':>8} {inner:>9}")

    # 等距块（段后 FF 紧接，间隔 = 0）
    eq = []
    i = 0
    while i < len(so):
        j = i
        while j + 1 < len(so) and gap[j] == 0:
            j += 1
        if j - i + 1 >= 4:
            eq.append((int(so[i]), j - i + 1, i, j))
        i = j + 1
    eq.sort(key=lambda x: -x[1])
    print(f"\n  等距块（段尾 FF 紧接下一段，≥4 段）：{len(eq)} 个")
    print(f"  {'块首 ROM':>14} {'段数':>5} {'块首指针':>8} {'块内指针数':>9} "
          f"{'段长样本'}")
    for s, cnt2, i0, j0 in eq[:12]:
        head = ptr_cnt.get(s, 0)
        inner = sum(1 for k in range(i0, j0 + 1) if ptr_cnt.get(int(so[k]), 0))
        sample = sl[i0:min(j0 + 1, i0 + 6)].tolist()
        print(f"  0x{BASE+s:08X} {cnt2:>5} "
              f"{('×'+str(head)) if head else '无':>8} {inner:>9} {sample}")

    # ── Q5 宝可梦名（向量化）──────────────────────────────────────
    print("\n" + "=" * 78)
    print("Q5 宝可梦名表：结构比对（向量化）")
    print("=" * 78)
    SPECIES, REC = 412, 11

    def scan(rom: bytes) -> list[tuple[int, int]]:
        a = np.frombuffer(rom, dtype=np.uint8)
        ok = (a == 0xFF)
        hits = []
        limit = len(a) - SPECIES * REC
        # cand = 位置 o 满足 o+REC-1 是 FF
        cand = np.flatnonzero(ok[REC - 1:limit + REC - 1])
        for o in cand.tolist():
            cnt2 = 0
            for k in range(SPECIES):
                idx = o + k * REC + REC - 1
                if idx < len(a) and ok[idx]:
                    cnt2 += 1
                else:
                    break
            if cnt2 >= 200:
                hits.append((o, cnt2))
        return hits

    print("  扫描中（步长 11，连续 ≥200 项末字节 FF）…")
    hj = scan(ja_b)
    hz = scan(zh_b)
    print(f"  原版命中 {len(hj)} 处，汉化命中 {len(hz)} 处")
    for o, c in hj[:6]:
        print(f"    原版 0x{BASE+o:08X}  {c} 项")
    for o, c in hz[:6]:
        print(f"    汉化 0x{BASE+o:08X}  {c} 项")

    if hj:
        o = hj[0][0]
        a = ja_b[o:o + SPECIES * REC]
        b = zh_b[o:o + SPECIES * REC]
        diff = sum(1 for x, y in zip(a, b) if x != y)
        print(f"\n  两版 @0x{BASE+o:08X} 对比 {len(a):,} 字节："
              f"不同 {diff:,}（{diff/len(a)*100:.2f}%）")
        print(f"  汉化侧 F7 数：{b.count(0xF7)}")
        if diff == 0:
            print("  ⇒ **名字表完全未改**：存档仍是原版编码 ⇒ 串档不乱 ✓")
        else:
            print("  前 6 项：")
            for k in range(6):
                ra, rb = a[k*REC:(k+1)*REC], b[k*REC:(k+1)*REC]
                print(f"    [{k}] {'同' if ra==rb else '★异'} 原 {ra.hex(' ')}"
                      f"  汉 {rb.hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
