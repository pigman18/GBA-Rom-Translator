#!/usr/bin/env python3
"""调研㊿ 直接看字节序列 —— 用肉眼定 F7 的真实宽度。

═══════════════════════════════════════════════════════════════════════════
【为什么必须看原始字节】
═══════════════════════════════════════════════════════════════════════════
㊾ 的结果矛盾：
  · 「F7 hi」2 字节解码：6,471/6,473 成功（100%）
  · 「F7 hi lo」3 字节解码：6,473/6,473 成功（100%）
  · 「F7 x F7」只占 0.3%（若 2 字节编码，应该很高）

两种解码都 100% 成功，说明我的「能否解到末尾」判据**没有区分力**
（因为解码器遇到未知字节就 i+=1，总能走到末尾）。

⇒ 放弃自动判据，**直接打印原始字节序列**，肉眼定结构。

用法：python scripts/research/firered/50_raw_bytes.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"


def main() -> int:
    zh = FR_ZH.read_bytes()

    print("=" * 78)
    print("① 主文本区里 F7 起的连续字节（前 30 个 F7 位置）")
    print("=" * 78)
    seg = zh[0x6D0000:0x722000]
    pos = []
    k = seg.find(b"\xf7")
    while k >= 0:
        pos.append(k)
        k = seg.find(b"\xf7", k + 1)
    print(f"  区间内 F7 总数：{len(pos):,}")
    print()
    for k in pos[:30]:
        blob = seg[k:k + 10]
        print(f"  +0x{k:05X}: {blob.hex(' ')}")

    print("\n" + "=" * 78)
    print("② 相邻 F7 间距分布（决定宽度）")
    print("=" * 78)
    d = np.diff(np.array(pos))
    c = Counter(d.tolist())
    for v in range(0, 13):
        cnt = c.get(v, 0)
        bar = "#" * int(cnt / max(1, max(c.values())) * 50)
        print(f"  间距 {v:>2}: {cnt:>7,}  {bar}")
    print(f"\n  大于 12 的间距：{sum(v for k2, v in c.items() if k2 > 12):,}")

    print("\n" + "=" * 78)
    print("③ 若把整个文本区按「已确认的段」切开，看段首段尾")
    print("=" * 78)
    # 取前 20 段
    pos2 = 0
    shown = 0
    while pos2 < len(seg) and shown < 20:
        e = seg.find(b"\xff", pos2)
        if e < 0:
            break
        body = seg[pos2:e]
        if body.count(0xF7) >= 1:
            print(f"  段[{shown:>2}] +0x{pos2:05X} 长{len(body):>3}  "
                  f"{body[:44].hex(' ')}")
            shown += 1
        pos2 = e + 1

    print("\n" + "=" * 78)
    print("④ 关键：一个段里 F7 的个数 vs 段长")
    print("=" * 78)
    pairs = []
    pos2 = 0
    while pos2 < len(seg):
        e = seg.find(b"\xff", pos2)
        if e < 0:
            break
        body = seg[pos2:e]
        if len(body) >= 4:
            nf = body.count(0xF7)
            if nf >= 1:
                pairs.append((len(body), nf))
        pos2 = e + 1
    print(f"  统计 {len(pairs):,} 段")
    # 段长 / F7 个数的比值分布
    ratios = Counter()
    for L, nf in pairs:
        if nf >= 2:
            ratios[round(L / nf)] += 1
    print(f"  段长 / F7 数 的比值（取整）top10：")
    tot = sum(ratios.values())
    for r, cnt in ratios.most_common(10):
        print(f"    比值 {r:>2}: {cnt:>6,}（{cnt/tot*100:>5.1f}%）")
    print(f"\n  ⇒ 若比值集中在 2 ⇒ 每字 2 字节；集中在 3 ⇒ 每字 3 字节")

    # 更精确：只统计「整段全是 F7 三字节/两字节组」的段
    print("\n  只看「F7 占比极高」的段（不含其他内容）：")
    pure = [(L, nf) for L, nf in pairs if nf * 2 >= L]
    print(f"    共 {len(pure):,} 段")
    if pure:
        r2 = Counter()
        for L, nf in pure:
            for w in (2, 3):
                if L == nf * w:
                    r2[w] += 1
        print(f"    段长正好 = F7数 × 2：{r2.get(2,0):,} 段")
        print(f"    段长正好 = F7数 × 3：{r2.get(3,0):,} 段")
        # 打印样本
        print(f"    样本：")
        pos2 = 0
        shown = 0
        while pos2 < len(seg) and shown < 12:
            e = seg.find(b"\xff", pos2)
            if e < 0:
                break
            body = seg[pos2:e]
            nf = body.count(0xF7)
            if nf >= 2 and body.count(0xF7) * 2 >= len(body):
                print(f"      L={len(body):<3} F7×{nf:<3} "
                      f"L/nf={len(body)/nf:.2f}  {body[:40].hex(' ')}")
                shown += 1
            pos2 = e + 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
