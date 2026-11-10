#!/usr/bin/env python3
"""调研㊶ 编码宽度定案：原版火红到底是 1 字节还是 2 字节编码。

═══════════════════════════════════════════════════════════════════════════
【要解决的疑问】
═══════════════════════════════════════════════════════════════════════════
㉘ 在 0x083DD000 看到：
    01 00 | 1c 10 | 1d 10 | 1e 10 | 1f 10 | ...
按 u16 读是 0x0001 0x101c 0x101d 0x101e 0x101f —— 四个连续码位，
令人怀疑原版是 2 字节编码。若成立，前面所有「日文 1 字节串」切分全废，
渲染调研的地基也是错的。

═══════════════════════════════════════════════════════════════════════════
【三个判据，任一即可定案】
═══════════════════════════════════════════════════════════════════════════
 A) **高字节多样性**（最硬的反证）
    2 字节编码的码位空间必然很小。Gen3 全套字模不过 3~5000 个，
    若是 2 字节，高位字节只可能有十几种取值。
    实测若出现 200+ 种高字节 ⇒ **直接否掉 2 字节**。

 B) **0x00 的角色**
    1 字节编码里 0x00 = 空格（词间分隔）；
    2 字节里 0x00 只可能是码位的半个字节，不会密集出现在词间。

 C) **已知明文对齐**
    物种名是公开的日文名（フシギダネ / フシギソウ / フシギバナ …），
    拿它当已知明文逐字节对齐，能 100% 确定宽度和字符集。

锚点来源：㉕ 用「汉化改过的指针」反推出的 3,613 个真实原版日文文本地址。

用法：python scripts/research/firered/41_encoding_verdict.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
CN_ZONES = [(0x6D0000, 0x722000), (0xAF5000, 0xAFB000)]


def in_cn(o: int) -> bool:
    return any(lo <= o < hi for lo, hi in CN_ZONES)


def anchors(zh: bytes, ja: bytes, n: int, m: int) -> np.ndarray:
    pz = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)
    pa = np.frombuffer(ja[:m], dtype=np.uint32).astype(np.uint64)
    is_rom = (pa >= BASE) & (pa < BASE + n) & (pz >= BASE) & (pz < BASE + n)
    old_off = (pa - BASE).astype(np.int64)
    new_off = (pz - BASE).astype(np.int64)
    new_in_cn = np.array([in_cn(int(x)) for x in new_off])
    old_in_cn = np.array([in_cn(int(x)) for x in old_off])
    sel = np.flatnonzero((pa != pz) & is_rom & new_in_cn & ~old_in_cn)
    return np.sort(old_off[sel])


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))
    m = n // 4 * 4
    olds = anchors(zh, ja, n, m)

    print("=" * 78)
    print(f"锚点：{len(olds):,} 个真实原版日文文本地址")
    print("=" * 78)

    # ── A) 高字节多样性 ────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("A) 高字节多样性 —— 2 字节编码的否证")
    print("=" * 78)
    hb = Counter()
    n16_total = 0
    segs = []
    for o in olds.tolist():
        e = ja.find(b"\xff", o, o + 300)
        if e < 0:
            continue
        seg = ja[o:e]
        if len(seg) < 2:
            continue
        segs.append(seg)
        u16 = np.frombuffer(seg[:len(seg) // 2 * 2], dtype="<u2")
        if len(u16):
            hb.update(((u16 >> 8) & 0xFF).tolist())
            n16_total += len(u16)

    print(f"  锚点串数 {len(segs):,}，按 u16 读共 {n16_total:,} 个码位")
    print(f"  **高字节不同取值：{len(hb)} 种 / 256**")
    print(f"  高字节 top 12: "
          + ", ".join(f"0x{k:02X}:{v/n16_total*100:.1f}%"
                      for k, v in hb.most_common(12)))
    if len(hb) > 100:
        print(f"\n  ⇒ 高字节有 {len(hb)} 种取值，**2 字节编码被否证**")
        print(f"     （2 字节编码的码位空间再大，高字节也不会铺满 256）")
    else:
        print(f"\n  ⇒ 高字节只有 {len(hb)} 种，2 字节编码**有可能**，需继续查")

    # ── B) 0x00 的角色 ─────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("B) 0x00 的角色：1 字节下的空格 vs 2 字节下的码位半字节")
    print("=" * 78)
    zeros = sum(s.count(0) for s in segs)
    total_bytes = sum(len(s) for s in segs)
    print(f"  锚点串共 {total_bytes:,} 字节，其中 0x00 有 {zeros:,}"
          f"（{zeros/total_bytes*100:.1f}%）")
    # 1 字节下：0x00 应出现在「字的边界」；2 字节下应只在偶/奇一种偏移
    even0 = stat_odd = 0
    pos_c = Counter()
    for s in segs:
        for i, b in enumerate(s):
            if b == 0:
                pos_c[i % 4] += 1
    print(f"  0x00 出现在字节偏移 mod 4 的分布：{dict(sorted(pos_c.items()))}")
    if len(pos_c) >= 3:
        print("  ⇒ 0x00 在 4 种偏移上都出现 ⇒ 不是固定对齐的码位半字节")
        print("     ⇒ 是 1 字节编码里的**空格**")

    # ── C) 已知明文：物种名 ────────────────────────────────────────
    print("\n" + "=" * 78)
    print("C) 已知明文对齐：原版物种名指针指向哪里")
    print("=" * 78)
    # ㊲ 发现 0x08419E38.. 是「原指向 0x08204xxx，汉化改指 0x0871F5xx」的指针表
    pz = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)
    pa = np.frombuffer(ja[:m], dtype=np.uint32).astype(np.uint64)
    tbl = 0x419E38
    print(f"  指针表 @0x{BASE+tbl:08X}，前 16 项：")
    print(f"    {'序号':>4} {'原版指向':>12} {'汉化指向':>12}  原版内容（到 FF）")
    for k in range(16):
        o = tbl + k * 8
        po = int(pa[o // 4]) - BASE
        pn = int(pz[o // 4]) - BASE
        if not (0 <= po < n):
            continue
        e = ja.find(b"\xff", po, po + 40)
        content = ja[po:e] if e > 0 else ja[po:po + 12]
        print(f"    {k:>4} 0x{BASE+po:08X} 0x{BASE+pn:08X}  "
              f"{content.hex(' ')}")

    # 目标是否集中在 0x08204xxx
    tg = []
    for k in range(200):
        o = tbl + k * 8
        if o // 4 >= len(pa):
            break
        po = int(pa[o // 4]) - BASE
        if 0 <= po < n:
            tg.append(po)
    print(f"\n  前 {len(tg)} 项原版目标范围："
          f"0x{BASE+min(tg):08X}..0x{BASE+max(tg):08X}")
    c = Counter(x // 0x1000 for x in tg)
    print(f"  按 4KB 分布：{dict(sorted(c.items()))}")

    print("\n  这些目标处的串，长度分布：")
    lens = []
    for po in tg:
        e = ja.find(b"\xff", po, po + 60)
        if e > 0:
            lens.append(e - po)
    if lens:
        a = np.array(lens)
        print(f"    均值 {a.mean():.1f} 中位 {np.median(a):.0f} "
              f"最小 {a.min()} 最大 {a.max()}")
        print(f"    ⇒ 若 5~12 字节，符合「日文物种名长度」")

    print("\n  前 12 个目标处的内容（hex + 长度）：")
    for po in tg[:12]:
        e = ja.find(b"\xff", po, po + 60)
        content = ja[po:e] if e > 0 else ja[po:po + 12]
        print(f"    0x{BASE+po:08X} L={len(content):<3} {content.hex(' ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
