#!/usr/bin/env python3
"""调研㉗ 彻底定案：0x083C0000..0x08410000 这片到底是什么。

═══════════════════════════════════════════════════════════════════════════
【㉖ 暴露的问题】
═══════════════════════════════════════════════════════════════════════════
0x083DD000 的原始字节：
    01 00 | 1c 10 | 1d 10 | 1e 10 | 1f 10 | 10 5e | 10 5f | 60 7f | 70 10 | 71 10 | ...
                  └────── 每 2 字节一个 0x10xx 值 ──────┘

这**非常像 16 位压缩字模**（0x10xx = 高字节 0x10 表示「这个像素行只有第 4 位」），
但㉕ 又有 1,163 个**被改指针的旧值**落在这个区，说明它被当文本引用。

两者不能同时成立。必须分清：
   · 是不是我算错了锚点（旧值其实是「中间地址」而非串起点）
   · 或者这个区确实存**两种东西**（前半字模，后半文本）

═══════════════════════════════════════════════════════════════════════════
【判别方法（不靠猜）】
═══════════════════════════════════════════════════════════════════════════
  ① 把锚点旧值的低 2 位拿出来看：若大多是 0，可能是 u32 对齐的结构指针
  ② 直接看每个锚点后面 64 字节，判断「像字模」还是「像文本」
     字模特征：大量奇偶配对 (b, 0x10) 或 (0x10, b)、行数 = 8/12/16 的倍数
     文本特征：0xFF 在 1..40 字节内出现
  ③ 统计该区 0xFF 的密度 —— 字模区几乎不该有 0xFF
  ④ 用「FF 间隔」把该区切成串，看切出来的串起点与锚点是否吻合

用法：python scripts/research/firered/27_region_identity.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

BASE = 0x08000000
NEW_TEXT = [(0x6D0000, 0x722000), (0xAF5000, 0xAFB000)]

REGIONS = [(0x3C2000, 0x3C4000, "0x083C2000"),
           (0x3DD000, 0x3E2000, "0x083DD000"),
           (0x19B000, 0x1AA000, "0x0819B000"),
           (0x409000, 0x40E000, "0x08409000"),
           (0x175000, 0x193000, "0x08175000")]


def in_new_text(off: int) -> bool:
    return any(lo <= off < hi for lo, hi in NEW_TEXT)


def main() -> int:
    zh_b = FR_ZH.read_bytes()
    ja_b = FR_JA.read_bytes()
    n = min(len(zh_b), len(ja_b))
    m = n // 4 * 4

    pa = np.frombuffer(ja_b[:m], dtype=np.uint32).astype(np.uint64)
    pz = np.frombuffer(zh_b[:m], dtype=np.uint32).astype(np.uint64)
    is_rom = (pa >= BASE) & (pa < BASE + n) & (pz >= BASE) & (pz < BASE + n)
    old_off = (pa - BASE).astype(np.int64)
    new_off = (pz - BASE).astype(np.int64)
    new_in_cn = np.array([in_new_text(int(x)) for x in new_off])
    old_in_cn = np.array([in_new_text(int(x)) for x in old_off])
    sel = np.flatnonzero((pa != pz) & is_rom & new_in_cn & ~old_in_cn)
    olds = np.sort(old_off[sel])

    # ── ① 锚点旧值的对齐 ────────────────────────────────────────────
    print("=" * 78)
    print("① 锚点旧值的 mod 4 对齐（u32 指针应全 0，串指针应随机）")
    print("=" * 78)
    c = Counter((olds % 4).tolist())
    tot = len(olds)
    for k in sorted(c):
        print(f"  mod 4 == {k}: {c[k]:>5,}（{c[k]/tot*100:>5.1f}%）")
    aligned = c[0] / tot
    print(f"  ⇒ {'全部 4 字节对齐，是指针数组/结构体内的指针' if aligned > 0.9 else '不对齐，是散落的串指针'}")

    # ── ② 每个锚点的内容形态 ────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 锚点处的字节形态：像文本还是像字模")
    print("=" * 78)

    def classify(o: int) -> str:
        seg = ja_b[o:o + 64]
        if not seg:
            return "空"
        ff = seg.find(b"\xff")
        # 文本特征：40 字节内有 FF
        has_ff_soon = 2 <= ff <= 40
        # 字模特征：高字节 0x10 重复（每 2 字节一个）
        pairs = [(seg[i], seg[i + 1]) for i in range(0, min(len(seg) - 1, 62), 2)]
        hi10 = sum(1 for a, b in pairs if a == 0x10 or b == 0x10)
        hi_ratio = hi10 / max(1, len(pairs))
        if has_ff_soon and hi_ratio < 0.4:
            return "文本"
        if hi_ratio >= 0.5:
            return "字模"
        if has_ff_soon:
            return "文本(弱)"
        return "无法判定"

    cnt = Counter()
    samples = {}
    for o in olds.tolist():
        k = classify(o)
        cnt[k] += 1
        if k not in samples:
            samples[k] = o
    for k, v in cnt.most_common():
        print(f"  {k:<10} {v:>5,}（{v/tot*100:>5.1f}%）")
    for k, o in samples.items():
        print(f"\n  【{k}】示例 0x{BASE+o:08X}")
        print(f"    {ja_b[o:o+64].hex(' ')}")

    # ── ③ 各区的 FF 密度与 0x10 密度 ────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 各锚点区的字节统计（判字模 vs 文本）")
    print("=" * 78)
    print(f"  {'区':>14} {'大小':>8} {'FF密度':>8} {'0x10密度':>9} "
          f"{'锚点数':>7} {'判定'}")
    for lo, hi, nm in REGIONS:
        seg = np.frombuffer(ja_b[lo:hi], dtype=np.uint8)
        ff = (seg == 0xFF).mean()
        t10 = (seg == 0x10).mean()
        na = int(((olds >= lo) & (olds < hi)).sum())
        if ff > 0.02:
            kind = "含文本（FF>2%）"
        elif t10 > 0.2:
            kind = "字模/位图"
        else:
            kind = "其他数据"
        print(f"  {nm:>14} {hi-lo:>7,}B {ff:>7.1%} {t10:>8.1%} "
              f"{na:>7} {kind}")

    # ── ④ 按 FF 切串，与锚点对照 ────────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 逐区按 FF 切串，串起点与锚点的吻合度")
    print("=" * 78)
    for lo, hi, nm in REGIONS:
        seg = ja_b[lo:hi]
        starts = set()
        pos = 0
        nseg = 0
        while pos < len(seg):
            e = seg.find(b"\xff", pos)
            if e < 0:
                break
            if e > pos:
                starts.add(lo + pos)
                nseg += 1
            pos = e + 1
        anchors_here = olds[(olds >= lo) & (olds < hi)]
        if len(anchors_here):
            hit = sum(1 for a in anchors_here.tolist() if a in starts)
            print(f"  {nm}: 切出 {nseg:,} 串，锚点 {len(anchors_here):,} 个，"
                  f"其中 {hit:,} 个正好是串起点（{hit/len(anchors_here)*100:.1f}%）")
        else:
            print(f"  {nm}: 切出 {nseg:,} 串，无锚点")

    # ── ⑤ 主文本区逐句读出（如果真是文本，应该能看出结构）────────
    print("\n" + "=" * 78)
    print("⑤ 0x083DD000 起，按 FF 切出的前 25 个串（假设是文本）")
    print("=" * 78)
    off = 0x3DD000
    seg = ja_b[off:off + 0x800]
    pos = 0
    k = 0
    while k < 25:
        e = seg.find(b"\xff", pos)
        if e < 0:
            print(f"  (在 +0x{pos:X} 处 0x800 字节内找不到 FF，说明不是文本串流)")
            break
        s = seg[pos:e]
        print(f"  [{k:>2}] +0x{pos:04X} L={len(s):<3} {s[:40].hex(' ')}")
        pos = e + 1
        k += 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
