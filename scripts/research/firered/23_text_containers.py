#!/usr/bin/env python3
"""调研㉓ 把火红「有哪些文本容器」全部摸清 —— 指针 / 无指针 / 等长 / 等距 / 超短。

═══════════════════════════════════════════════════════════════════════════
【㉑ 暴露的关键缺口】
═══════════════════════════════════════════════════════════════════════════
  原版日文文本起点：304,428 个
  原版里「指向日文文本起点」的 u32 槽位：只有 6,607 个

⇒ **绝大多数日文文本不是被 u32 指针直接引用的**。
  这直接对应你问的第 2 类「无指针文本怎么处理」。

本脚本穷举火红文本的**所有容器形态**，每种都要找到证据：

  A) 单指针容器：u32 → 串（覆盖了多少串）
  B) 指针数组容器：连续 N 个 u32 都指向串（脚本表/名字表）
  C) 无指针·等长块：连续等长串，整块被**一个**指针引用（块首）
  D) 无指针·等距块：`str\0str\0str\0`，整块一个指针
  E) 无指针·纯裸串：既无单指针也无块指针 ⇒ 只能靠「改代码里的地址计算」
  F) 超短文本：长度 ≤6 的串，它们属于哪类容器

关键判据：对每条原版日文串，回看它在汉化版是否被改写；
再按「它属于哪个容器」分类，就能算出每类的改写率 ——
某类改写率高说明汉化确实处理了它；接近 0 说明是原生保留。

用法：python scripts/research/firered/23_text_containers.py
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

BASE = 0x08000000
NEW_TEXT = [(0x6D0000, 0x722000), (0xAF5000, 0xAFB000)]


def in_text(off: int) -> bool:
    return any(lo <= off < hi for lo, hi in NEW_TEXT)


def main() -> int:
    zh = np.frombuffer(FR_ZH.read_bytes(), dtype=np.uint8)
    ja = np.frombuffer(FR_JA.read_bytes(), dtype=np.uint8)
    n = min(len(zh), len(ja))
    print("=" * 78)
    print("火红文本容器穷举")
    print("=" * 78)

    # ── 原版日文串切分（用 FF 作为结束符）────────────────────────────
    jp = (ja >= 0x01) & (ja <= 0xDF)
    # 串起点：自己是可打印，前一个不是（或前一个是 FF/00）
    prev_ok = np.zeros(n, dtype=bool)
    prev_ok[1:] = jp[:-1]
    starts = jp & ~prev_ok
    # 要求长度 ≥2，且确实以 FF 收尾（在 8..120 范围内）
    est = np.zeros(n, dtype=bool)
    idx = np.flatnonzero(starts)
    print(f"候选串起点 {len(idx):,} 个，逐个校验长度与 FF 结尾 …")

    # 用 numpy 找每个起点的长度：先算「从该点起的 jp 连续长度」
    # 简化：只处理起点列表，用 python 循环（30 万次可接受）
    ja_b = FR_JA.read_bytes()
    zh_b = FR_ZH.read_bytes()

    def seg_of(b: bytes, o: int, maxlen: int = 200) -> int:
        e = b.find(b"\xff", o, o + maxlen)
        return -1 if e < 0 else e - o

    texts = []           # (offset, length)
    for o in idx.tolist():
        L = seg_of(ja_b, o)
        if L < 2:
            continue
        texts.append((o, L))
    print(f"  合法日文串：{len(texts):,} 条")

    tl = np.array([t[1] for t in texts])
    to = np.array([t[0] for t in texts])
    print(f"  长度：均值 {tl.mean():.1f} 中位 {np.median(tl):.0f} "
          f"最大 {tl.max()}  ≤6 的 {int((tl<=6).sum()):,} 条"
          f"（{(tl<=6).mean()*100:.1f}%）")

    # ── 建指针索引 ──────────────────────────────────────────────────
    m = n // 4 * 4
    pa = ja[:m].view(np.uint32).astype(np.uint64)
    pz = zh[:m].view(np.uint32).astype(np.uint64)
    is_rom = (pa >= BASE) & (pa < BASE + n)
    ptr_slots = np.flatnonzero(is_rom)
    ptr_vals = (pa[ptr_slots] - BASE).astype(np.int64)
    # 只保留指向日文串起点的
    start_pos = {o: i for i, o in enumerate(to.tolist())}
    hit_slots, hit_vals = [], []
    for s, v in zip(ptr_slots.tolist(), ptr_vals.tolist()):
        if v in start_pos:
            hit_slots.append(s)
            hit_vals.append(v)
    print(f"\n  指向日文串起点的 u32 槽位：{len(hit_slots):,}")

    covered = set(hit_vals)
    print(f"  这些槽位直接覆盖了 {len(covered):,} 条串"
          f"（占全部 {len(covered)/len(texts)*100:.1f}%）")

    # ── B) 指针数组容器 ─────────────────────────────────────────────
    print("\n" + "-" * 78)
    print("B) 指针数组容器（连续 u32 都指向串）")
    print("-" * 78)
    sl = sorted(hit_slots)
    arrays = []
    i = 0
    while i < len(sl):
        j = i
        while j + 1 < len(sl) and sl[j + 1] == sl[j] + 4:
            j += 1
        if j - i + 1 >= 4:
            arrays.append((sl[i], j - i + 1))
        i = j + 1
    arrays.sort(key=lambda x: -x[1])
    print(f"  找到 {len(arrays)} 个指针数组（≥4 项）")
    tot_items = sum(a[1] for a in arrays)
    print(f"  覆盖 {tot_items:,} 个槽位（占 {tot_items/len(hit_slots)*100:.1f}%）")
    for s, cnt in arrays[:10]:
        print(f"    0x{BASE+s:08X}  {cnt:>5} 项  "
              f"首项→0x{BASE+int(pa[s]-BASE):08X}")

    # ── C/D/E) 无指针串 ─────────────────────────────────────────────
    print("\n" + "-" * 78)
    print("C/D/E) 无单指针的串，按物理邻接形态分类")
    print("-" * 78)
    # 建 offset -> 索引
    order = np.argsort(to)
    ts = to[order]
    tlen = tl[order]
    pos_map = {int(o): k for k, o in enumerate(ts.tolist())}

    cat = Counter()
    examples = defaultdict(list)

    arr_slot_set = set()
    for s, cnt in arrays:
        for k in range(cnt):
            arr_slot_set.add(s + k * 4)

    for k, o in enumerate(ts.tolist()):
        L = int(tlen[k])
        has_ptr = o in covered
        if has_ptr:
            cat["A 单指针直指"] += 1
            continue
        # 找物理上一个串
        prevk = pos_map.get(o - 1)
        if prevk is not None:
            # 上一串 + 它的 FF 正好接到本串 ⇒ 等长/等距块成员
            gap = o - (ts[prevk] + tlen[prevk])
            if gap == 1:
                cat["D 等距块成员(FF紧邻)"] += 1
                if len(examples["D"]) < 4:
                    examples["D"].append((o, L, int(ts[prevk])))
            elif gap == 2 and ja_b[o - 1] == 0x00:
                cat["E2 00补齐块成员"] += 1
            elif gap == 0:
                cat["E3 紧邻无分隔"] += 1
            else:
                cat["F 孤立无指针"] += 1
                if len(examples["F"]) < 4:
                    examples["F"].append((o, L, int(ts[prevk])))
        else:
            cat["F 孤立无指针"] += 1
            if len(examples["F"]) < 4:
                examples["F"].append((o, L, -1))

    for c, v in sorted(cat.items()):
        print(f"    {c:<22} {v:>7,}（{v/len(ts)*100:>5.1f}%）")
    for c, exs in examples.items():
        print(f"\n  {c} 示例：")
        for o, L, pk in exs:
            print(f"    0x{BASE+o:08X} L={L}  前串@"
                  f"{('0x%08X' % (BASE+pk)) if pk>=0 else '—'}")
            print(f"      {ja_b[o:o+min(L+4,48)].hex(' ')}")

    # ── 关键：每类在汉化版被改写的比例 ───────────────────────────────
    print("\n" + "-" * 78)
    print("★ 每类容器在汉化版里的改写率（回答「怎么处理的」）")
    print("-" * 78)
    rate = defaultdict(lambda: [0, 0])
    for k, o in enumerate(ts.tolist()):
        L = int(tlen[k])
        # 重新判类（与上面同逻辑，抽成函数太重，直接复算）
        a = ja_b[o:o + L]
        b = zh_b[o:o + L]
        changed = a != b
        # 该串在汉化是否变成中文
        is_cn = zh_b[o:o + 2] == b"\xf7\x00" or zh_b[o] == 0xF7

        key = None
        if o in covered:
            key = "A 单指针直指"
        else:
            prevk = pos_map.get(o - 1)
            if prevk is not None and o - (ts[prevk] + tlen[prevk]) == 1:
                key = "D 等距块成员"
            elif prevk is not None:
                key = "F 其他无指针"
            else:
                key = "F 其他无指针"
        rate[key][0] += int(bool(changed.any()))
        rate[key][1] += 1

    print(f"    {'类别':<20} {'总数':>8} {'被改动':>8} {'改写率':>7}")
    for k in sorted(rate):
        ch, tot = rate[k]
        print(f"    {k:<20} {tot:>8,} {ch:>8,} {ch/tot*100:>6.1f}%")

    print("\n" + "=" * 78)
    print("判读")
    print("=" * 78)
    print("  · A 类改写率高 ⇒ 「写新区改指针」覆盖了指针可达的文本")
    print("  · D/F 类改写率接近 0 ⇒ 这些串在汉化里**没被替换**")
    print("  · 若 D/F 占比大且改写率为 0 ⇒ 火红并未处理「无指针/等长块」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
