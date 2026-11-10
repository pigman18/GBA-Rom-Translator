#!/usr/bin/env python3
"""调研㉛ 收口：修掉㉚的两个错误，把剩下三个未决问题一次查清。

═══════════════════════════════════════════════════════════════════════════
【㉚ 的两个错误】
═══════════════════════════════════════════════════════════════════════════
 错 1「等距块 = 0 个」：我算 gap = next_start - (cur_start+cur_len)。
      串在 cur_start+cur_len 处就是 0xFF，下一串在 +1，所以**紧邻的 gap 是 1**，
      不是 0。判据写错，导致「等距块」恒为 0。
 错 2「名字表」：判据只要求「每 11 字节末位是 FF」，而 0x086C7D2E 附近
      本来就是整片 0xFF 填充 ⇒ 700 万处假命中。
      必须加「每项内容非空且字节多样」才有意义。

═══════════════════════════════════════════════════════════════════════════
【本脚本收口三个未决问题】
═══════════════════════════════════════════════════════════════════════════
 U1 「无指针」的 27% 中文段，究竟有没有指针 —— 只是不指向段首？
    做法：检查是否有 u32 落在 [段首, 段尾] 区间内（段内任意位置）
 U2 等长块到底是「块首一个基址 + 固定步长」，还是「每个元素各自一个指针」？
    做法：对每个等长块，统计 stride=L+1，检查是否存在 u32 == 块首，
          以及块内指针命中数 / 段数的比例
 U3 等距块（串后紧跟下一串）真实数量与指针情况（修正 gap==1）
 U4 宝可梦名表：用「内容非空 + 多样」的严格判据重找

用法：python scripts/research/firered/31_finalize.py
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
    print("收口：修正判据后重算")
    print("=" * 78)

    # ── 中文段 ─────────────────────────────────────────────────────
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
    segs.sort()
    print(f"\n中文段 {len(segs):,} 条")

    pz = np.frombuffer(zh_b[:m], dtype=np.uint32).astype(np.uint64)
    ok = (pz >= BASE) & (pz < BASE + n)
    tgt = (pz[ok] - BASE).astype(np.int64)
    ptr_cnt = Counter(tgt.tolist())

    offs = np.array([s[0] for s in segs], dtype=np.int64)
    lens = np.array([s[1] for s in segs], dtype=np.int64)

    # ── U1：段内任意位置有没有指针 ─────────────────────────────────
    print("\n" + "=" * 78)
    print("U1 「无段首指针」的段，是否有指针落在段内其他位置")
    print("=" * 78)
    # 建「目标地址 -> 是否被引用」的前缀和数组（按段区间查询）
    covered = np.zeros(n + 1, dtype=np.int64)
    for v in ptr_cnt:
        if 0 <= v < n:
            covered[v + 1] = 1
    prefix = np.cumsum(covered)

    head_hit = 0
    inner_hit = 0
    none_hit = 0
    inner_examples = []
    for o, L in segs:
        h = ptr_cnt.get(o, 0)
        if h:
            head_hit += 1
            continue
        # 段内 [o+1, o+L-1] 是否有指针
        cnt2 = prefix[o + L] - prefix[o + 1]
        if cnt2 > 0:
            inner_hit += 1
            if len(inner_examples) < 6:
                inner_examples.append((o, L, int(cnt2)))
        else:
            none_hit += 1

    tot = len(segs)
    print(f"  段首有指针：        {head_hit:>6,}（{head_hit/tot*100:>5.1f}%）")
    print(f"  段首无、段内有指针：{inner_hit:>6,}（{inner_hit/tot*100:>5.1f}%）")
    print(f"  段内也没有指针：    {none_hit:>6,}（{none_hit/tot*100:>5.1f}%）")
    print(f"\n  ⇒ 指针可达率（段首或段内）: "
          f"{(head_hit+inner_hit)/tot*100:.1f}%")
    print(f"  ⇒ 完全无指针的段落（只能靠偏移计算/结构内访问）: "
          f"{none_hit/tot*100:.1f}%")
    for o, L, c in inner_examples:
        print(f"    段内指针示例 0x{BASE+o:08X} L={L} 段内{c}个指针  "
              f"{zh_b[o:o+min(L+1,28)].hex(' ')}")

    # ── U2 等长块 ──────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("U2 等长块：块首基址 vs 每元素各自指针")
    print("=" * 78)
    blocks = []
    i = 0
    while i < len(offs):
        j = i
        while (j + 1 < len(offs) and lens[j + 1] == lens[i]
               and offs[j + 1] - (offs[j] + lens[j]) == 1):
            j += 1
        if j - i + 1 >= 3:
            blocks.append((int(offs[i]), j - i + 1, int(lens[i])))
        i = j + 1
    print(f"  等长块 {len(blocks)} 个")
    print(f"  {'块首':>14} {'段数':>5} {'步长':>5} {'块首被引用':>9} "
          f"{'元素被引用':>9} {'元素引用率':>9}")
    base_hit = 0
    ratio_sum = 0
    for s, cnt2, L in blocks[:18]:
        b = ptr_cnt.get(s, 0)
        elems = [s + k * (L + 1) for k in range(cnt2)]
        e_hit = sum(1 for x in elems if ptr_cnt.get(x, 0))
        print(f"  0x{BASE+s:08X} {cnt2:>5} {L+1:>5} "
              f"{('×'+str(b)) if b else '无':>9} {e_hit:>9} "
              f"{e_hit/cnt2*100:>8.0f}%")
        if b:
            base_hit += 1
        ratio_sum += e_hit / cnt2
    print(f"\n  块首被引用的块：{base_hit}/{len(blocks)}"
          f"（{base_hit/max(1,len(blocks))*100:.0f}%）")
    print(f"  平均「元素被引用率」：{ratio_sum/max(1,min(len(blocks),18))*100:.0f}%")
    print("  ⇒ 若块首几乎不被引用、而元素引用率高 ⇒ 是**每个元素各自指针**")
    print("  ⇒ 若是固定步长数组，块首应有基址指针、元素都不被引用")

    # ── U3 等距块（修正：紧邻 gap == 1）────────────────────────────
    print("\n" + "=" * 78)
    print("U3 等距块（串后紧跟下一串，gap==1）—— 修正判据")
    print("=" * 78)
    gap = np.full(len(offs), -1, dtype=np.int64)
    gap[:-1] = offs[1:] - (offs[:-1] + lens[:-1])
    print(f"  gap 分布（前 6 名）：")
    gc = Counter(gap.tolist())
    for g, c in gc.most_common(6):
        print(f"    gap={g} × {c}")

    eq_blocks = []
    i = 0
    while i < len(offs):
        j = i
        while j + 1 < len(offs) and gap[j] == 1:
            j += 1
        if j - i + 1 >= 4:
            eq_blocks.append((int(offs[i]), j - i + 1))
        i = j + 1
    eq_blocks.sort(key=lambda x: -x[1])
    print(f"\n  等距块（≥4 段紧邻）：{len(eq_blocks)} 个")
    print(f"  {'块首':>14} {'段数':>5} {'块首被引用':>9} {'元素被引用':>9} "
          f"{'段长样本'}")
    for s, cnt2 in eq_blocks[:12]:
        elems = [offs[k] for k in range(len(offs))
                 if s <= offs[k] <= s + 4000][:cnt2]
        b = ptr_cnt.get(s, 0)
        e_hit = sum(1 for x in elems if ptr_cnt.get(int(x), 0))
        sample = [int(lens[k]) for k in range(len(offs))
                  if s <= offs[k] <= s + 4000][:6]
        print(f"  0x{BASE+s:08X} {cnt2:>5} "
              f"{('×'+str(b)) if b else '无':>9} {e_hit:>9} {sample}")

    # ── U4 宝可梦名表（严格判据）───────────────────────────────────
    print("\n" + "=" * 78)
    print("U4 宝可梦名表：严格判据（每项末字节 FF + 内容非空 + 字节多样）")
    print("=" * 78)
    SPECIES, REC = 412, 11

    def find_tables(rom: bytes) -> list[tuple[int, int, int]]:
        a = np.frombuffer(rom, dtype=np.uint8)
        okff = (a == 0xFF)
        out = []
        limit = len(a) - SPECIES * REC
        # 候选：o+REC-1 是 FF，且 o 处不是 FF（内容非空起点）
        cand = np.flatnonzero(okff[REC - 1:limit + REC - 1] & (a[:limit] != 0xFF))
        for o in cand.tolist():
            good = 0
            nonempty = 0
            for k in range(SPECIES):
                base = o + k * REC
                if not okff[base + REC - 1]:
                    break
                good += 1
                if a[base] != 0xFF:
                    nonempty += 1
            if good >= SPECIES - 5 and nonempty >= SPECIES * 0.85:
                out.append((o, good, nonempty))
        return out

    print("  扫描原版…")
    tj = find_tables(ja_b)
    print(f"  原版严格命中 {len(tj)} 处")
    for o, g, ne in tj[:8]:
        print(f"    0x{BASE+o:08X}  连续{g}项 非空{ne}项")
    if tj:
        o = tj[0][0]
        a = ja_b[o:o + SPECIES * REC]
        b = zh_b[o:o + SPECIES * REC]
        diff = sum(1 for x, y in zip(a, b) if x != y)
        print(f"\n  两版 @0x{BASE+o:08X}（{len(a):,} 字节）不同 {diff:,}"
              f"（{diff/len(a)*100:.2f}%）  汉化侧 F7 数 {b.count(0xF7)}")
        print("  前 10 项（原版 / 汉化）：")
        for k in range(10):
            ra = a[k * REC:(k + 1) * REC]
            rb = b[k * REC:(k + 1) * REC]
            print(f"    [{k:>3}] {'同' if ra == rb else '★异'}  "
                  f"原 {ra.hex(' ')}   汉 {rb.hex(' ')}")
        if diff == 0:
            print("\n  ⇒ 名字表逐字节相同 ⇒ 存档里仍是原版编码 ⇒ 串档不乱 ✓")
        else:
            print("\n  ⇒ 名字表有改动，需要看改了什么")
    else:
        print("  **没找到严格符合的表** —— 说明火红的物种名表不在此布局，需换判据")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
