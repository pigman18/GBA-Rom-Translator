#!/usr/bin/env python3
"""调研㉙ 五类文本处理「总账」—— 逐类给出证据，不留推断。

═══════════════════════════════════════════════════════════════════════════
【已确证的前提（前面脚本实证）】
═══════════════════════════════════════════════════════════════════════════
 P1. 汉化只用 F7，形式 `F7 hi lo`（间距 3 占绝对多数）
 P2. 中文全部写在原版**全 FF 的空区**：0x6D0000 起（原版该区 100% FF，1 种字节值）
       + 0xAF5000（文本区3）
 P3. 有指针可改的文本：改指针不改原文（3,613 个槽位旧值→中文区）
 P4. 原版日文文本 97.9% 原样保留（不删不覆盖）
 P5. 原版是 1 字节编码，F7 是 3 字节前缀

═══════════════════════════════════════════════════════════════════════════
【本脚本对 6,822 段中文逐个定性，回答用户 5 个问题】
═══════════════════════════════════════════════════════════════════════════
 Q1 常规文本：有指针→写新区改指针？无指针→缩短译文？
 Q2 等长块：整块写新区 + 改整块指针？
 Q3 等距块：同上？
 Q4 超短文本：怎么做的？
 Q5 宝可梦名：怎么保证串档不乱？

判定逻辑（对每一段中文）：
   · 段首是否有 u32 指针直接指向 → 「直指」
   · 同长度段是否成连续串（等长块）→ 「等长块成员」
   · 段与段之间是否只隔 1 个 FF（等距）→ 「等距块成员」
   · 段长 ≤6 → 「超短」
   · 其余 → 「其他」

然后对每种容器，看**同容器里的一条**在原版对应位置是否也被改了。

用法：python scripts/research/firered/29_five_categories.py
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

BASE = 0x08000000
ZONES = [(0x6D0000, 0x722000, "主文本区"),
         (0xAF5000, 0xAFB000, "文本区3")]


def main() -> int:
    zh_b = FR_ZH.read_bytes()
    ja_b = FR_JA.read_bytes()
    n = min(len(zh_b), len(ja_b))
    m = n // 4 * 4

    print("=" * 78)
    print("五类文本处理总账")
    print("=" * 78)

    # ── 收集全部中文段 ──────────────────────────────────────────────
    segs = []          # (off, len)
    for lo, hi, nm in ZONES:
        seg = zh_b[lo:hi]
        pos = 0
        while pos < len(seg):
            e = seg.find(b"\xff", pos)
            if e < 0:
                break
            if e > pos:
                body = seg[pos:e]
                if body.count(0xF7) >= 1:
                    segs.append((lo + pos, len(body)))
            pos = e + 1
    print(f"\n中文段总数：{len(segs):,}")

    # ── 指针普查：哪些段首被 u32 直指 ──────────────────────────────
    pa = np.frombuffer(ja_b[:m], dtype=np.uint32).astype(np.uint64)
    pz = np.frombuffer(zh_b[:m], dtype=np.uint32).astype(np.uint64)
    ptr_ok = (pz >= BASE) & (pz < BASE + n)
    tgt = (pz - BASE).astype(np.int64)
    ptr_count = Counter()
    for v in tgt[ptr_ok].tolist():
        ptr_count[v] += 1

    seg_off = {o for o, L in segs}

    # ── 对齐 / 等长 / 等距分析 ──────────────────────────────────────
    by_zone = defaultdict(list)
    for o, L in segs:
        z = next(nm for lo, hi, nm in ZONES if lo <= o < hi)
        by_zone[z].append((o, L))
    for z in by_zone:
        by_zone[z].sort()

    # 段间间隔 & 等长串
    gap_kind = {}
    runs_same_len = {}
    for z, lst in by_zone.items():
        i = 0
        while i < len(lst):
            o, L = lst[i]
            # 下一个紧邻段
            if i + 1 < len(lst):
                no, nL = lst[i + 1]
                gap = no - (o + L)      # 中间夹的字节数（含 FF）
                gap_kind[o] = gap
            else:
                gap_kind[o] = -1
            # 等长连续
            j = i
            while (j + 1 < len(lst) and lst[j + 1][1] == L
                   and lst[j + 1][0] - (lst[j][0] + lst[j][1]) == 1):
                j += 1
            if j - i + 1 >= 3:
                for k in range(i, j + 1):
                    runs_same_len[lst[k][0]] = (j - i + 1, L)
            i = j + 1 if j > i else i + 1

    # ── 分类 ────────────────────────────────────────────────────────
    cat = Counter()
    cat_len = defaultdict(list)
    cat_has_ptr = Counter()
    detail = defaultdict(list)

    for o, L in segs:
        tags = []
        if o in ptr_count:
            tags.append("直指针")
        if o in runs_same_len:
            tags.append("等长块")
        g = gap_kind.get(o, -1)
        if g == 0:
            tags.append("等距紧邻")     # 段尾 FF 后直接下一段
        if L <= 6:
            tags.append("超短")
        key = "+".join(sorted(tags)) if tags else "无特征"
        cat[key] += 1
        cat_len[key].append(L)
        cat_has_ptr[key] += (1 if o in ptr_count else 0)
        if len(detail[key]) < 3:
            detail[key].append((o, L))

    print(f"\n{'分类':<26} {'段数':>6} {'占比':>7} {'平均长':>7} "
          f"{'段首有指针':>10}")
    print("-" * 70)
    for k, v in cat.most_common(24):
        avgl = np.mean(cat_len[k]) if cat_len[k] else 0
        print(f"{k:<26} {v:>6,} {v/len(segs)*100:>6.1f}% "
              f"{avgl:>7.1f} {cat_has_ptr[k]:>10,}")

    # ── Q4 超短文本专项 ────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("Q4 超短文本（≤6 字节 = 1~2 个汉字）专项")
    print("=" * 78)
    short = [(o, L) for o, L in segs if L <= 6]
    print(f"  段数 {len(short):,}（占 {len(short)/len(segs)*100:.1f}%）")
    withp = sum(1 for o, L in short if o in ptr_count)
    print(f"  段首被指针直指：{withp:,}（{withp/max(1,len(short))*100:.1f}%）")
    print(f"  长度分布：", end="")
    lc = Counter(L for o, L in short)
    print(", ".join(f"L{L}:{c}" for L, c in sorted(lc.items())))
    print(f"\n  抽样 10 条：")
    for o, L in short[:10]:
        txt = zh_b[o:o + L]
        nch = txt.count(0xF7)
        p = ptr_count.get(o, 0)
        print(f"    0x{BASE+o:08X} L={L} 汉字{nch} ptr×{p}  {txt.hex(' ')}")

    # ── Q5 宝可梦名专项 ────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("Q5 宝可梦名：存档结构有没有被改成 F7？")
    print("=" * 78)
    # 用结构判据找名字表：步长 11、连续项末字节为 0xFF
    def find_name_table(rom: bytes, species=412, rec=11):
        need = 300
        cands = []
        a = np.frombuffer(rom, dtype=np.uint8)
        last = np.zeros(len(a), dtype=bool)
        for k in range(species):
            idx = np.arange(k * rec + rec - 1, len(a))
            last[:len(a) - (k * rec + rec - 1)] &= (a[idx] == 0xFF)[:len(a) - (k * rec + rec - 1)]
        return None

    # 直接检查：两版在「原版名字表已知位置」是否一致
    # 用已知日版火红名字表偏移做验证（0x08245F00 附近是 species name 常见位置）
    # 改为：找「连续 200 个 11 字节记录、每条末字节 FF」的位置
    def scan(rom: bytes, rec=11, need=200, species=412):
        a = np.frombuffer(rom, dtype=np.uint8)
        ok = (a == 0xFF)
        hits = []
        limit = len(a) - species * rec
        for o in range(0, limit, 1):
            if not ok[o + rec - 1]:
                continue
            cnt = 0
            for k in range(species):
                if ok[o + k * rec + rec - 1]:
                    cnt += 1
                else:
                    break
            if cnt >= need:
                hits.append((o, cnt))
        return hits

    print("  扫描「步长 11、连续 ≥200 项末字节 FF」的位置（名字表结构特征）…")
    hz = scan(zh_b)
    hj = scan(ja_b)
    print(f"  汉化：{len(hz)} 处  原版：{len(hj)} 处")
    for o, c in hz[:5]:
        print(f"    汉化 0x{BASE+o:08X}  匹配 {c} 项")
    for o, c in hj[:5]:
        print(f"    原版 0x{BASE+o:08X}  匹配 {c} 项")
    if hj:
        o = hj[0][0]
        a = ja_b[o:o + 412 * 11]
        b = zh_b[o:o + 412 * 11]
        diff = sum(1 for x, y in zip(a, b) if x != y)
        print(f"\n  两版在 0x{BASE+o:08X} 的 {len(a):,} 字节对比："
              f"不同 {diff:,}（{diff/len(a)*100:.2f}%）")
        print(f"  汉化侧 F7 数量：{b.count(0xF7)}")
        if diff == 0:
            print("  ⇒ **名字表完全未改** ⇒ 存档里仍是原版编码 ⇒ 串档不乱")
        else:
            print("  ⇒ 有改动，逐项看前 8 项：")
            for k in range(8):
                ra = a[k * 11:(k + 1) * 11]
                rb = b[k * 11:(k + 1) * 11]
                mark = "同" if ra == rb else "★异"
                print(f"    [{k}] {mark} 原 {ra.hex(' ')}  汉 {rb.hex(' ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
