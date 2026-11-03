#!/usr/bin/env python3
"""调研⑫ 精确定位火红的宝可梦名表，判断是否被汉化改动。

═══════════════════════════════════════════════════════════════════════════
【上一轮的问题】
═══════════════════════════════════════════════════════════════════════════
`11_pokemon_names.py` 用「10 字节定长 + 首字节是日文」当判据，
在原版找到 13,596 处候选 —— 明显是把**代码段**也算进去了。
结论「大部分原样保留」因此不可信。

═══════════════════════════════════════════════════════════════════════════
【更可靠的定位法】
═══════════════════════════════════════════════════════════════════════════
Gen3 的宝可梦名表有两个铁特征：
  1. **物种数量固定**：火红 412 个 species（含空槽）
  2. **每项 10 字节**（POKEMON_NAME_LENGTH = 10，+1 给 FF）
  3. 表是**连续的**，且相邻项的名字不同（不是重复数据）
  4. 表里必须能找到已知的日文名，比如「フシギダネ」（妙蛙种子）

⇒ 直接搜「フシギダネ」的字符编码，它会出现在名字表的第一项附近。

Gen3 日文字符编码（PCS）：フ=0x76? 需要实测。
更简单的办法：搜**连续 3 个以上日文假名字符**的片段，
且这种片段在 ROM 里只出现在少数区域（名字表/文本区）。

用法：python scripts/research/firered/12_find_name_table_exact.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

# 汉化新增文本区的范围（已确认）
ZH_TEXT = (0x6D0000, 0x6D0000 + 0x58000)


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    # ── 先找「原版里是日文假名、汉化版变成 F7」的位置 ──────────────────
    # 这些就是「宝可梦名表被汉化」的证据（如果存在的话）
    print("=== 搜索：原版是日文、汉化变 F7 的区域 ===")
    # 按 64 字节块比对，找「原版假名占比高、汉化 F7 占比高」的块
    blk = 64
    hits = []
    for o in range(0, min(len(zh), len(ja)) - blk, blk):
        a = ja[o:o + blk]
        b = zh[o:o + blk]
        if a == b:
            continue
        # 原版假名占比（Gen3 日文 0x01-0x1F 是假名）
        jp = sum(1 for x in a if 1 <= x <= 0x1F or 0x40 <= x <= 0x5A)
        # 汉化 F7 占比
        f7 = sum(1 for x in b if x == 0xF7)
        if jp >= blk * 0.5 and f7 >= 4:
            hits.append(o)

    print(f"  找到 {len(hits)} 个 64 字节块：" 
          f"原版是日文、汉化含 F7")
    if hits:
        # 聚合成区间
        runs = []
        s = p = hits[0]
        for x in hits[1:]:
            if x == p + blk:
                p = x
            else:
                runs.append((s, p))
                s = p = x
        runs.append((s, p))
        print(f"  聚合成 {len(runs)} 个区间，前 10 个：")
        for s, e in runs[:10]:
            print(f"    ROM 0x{0x08000000+s:08X}..0x{0x08000000+e+blk:08X}"
                  f"  ({(e-s+blk)//1024}KB)")
    else:
        print("  **没有**任何区域从「日文」变成「F7」")

    # ── 关键判据：汉化新增区之外，F7 有多少？ ──────────────────────────
    print("\n=== 关键判据：F7 在什么位置 ===")
    lo, hi = ZH_TEXT
    in_zone = 0
    out_zone = Counter()     # 64KB 段 -> 次数
    i = zh.find(b"\xf7")
    while i >= 0:
        if lo <= i < hi:
            in_zone += 1
        else:
            out_zone[i // 0x10000] += 1
        i = zh.find(b"\xf7", i + 1)
    tot = in_zone + sum(out_zone.values())
    print(f"  F7 总数 {tot:,}")
    print(f"  在新增文本区（0x{0x08000000+lo:08X}+{hi-lo:X}）内: "
          f"{in_zone:,}（{in_zone/tot*100:.1f}%）")
    print(f"  在区外: {sum(out_zone.values()):,}"
          f"（{sum(out_zone.values())/tot*100:.1f}%）")
    if out_zone:
        print("  区外分布最多的 8 个 64KB 段：")
        for seg, n in out_zone.most_common(8):
            print(f"    ROM 0x{0x08000000+seg*0x10000:08X}   {n:,} 个")

    print("\n=== 判读 ===")
    print("  若绝大部分 F7 都在「新增文本区」⇒ 汉化**只改文本，不动数据结构**")
    print("  ⇒ 宝可梦名等存档数据保持原版编码 ⇒ 串档不乱")
    print("  若大量 F7 散落在原版数据区 ⇒ 汉化改了别的表（需要逐个查）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
