#!/usr/bin/env python3
"""调研㉜ 专查 Q5：火红的宝可梦名，究竟怎么做到串档不乱。

═══════════════════════════════════════════════════════════════════════════
【前情】
═══════════════════════════════════════════════════════════════════════════
 ㉚ 的「名字表逐字节相同」**是误报**：扫到 0x086C7D2E，那是整片 0xFF 填充，
    任何 11 字节步长的末字节都天然是 FF ⇒ 700 万处假命中。
 ㉛ 加严格判据（每项末字节 FF + 非空 + 多样）后，**原版命中 0 处**。

⇒ 结论：**日版火红没有 412×11 的连续物种名表**（或布局不同）。
   Q5 仍未答，本脚本换四个互不依赖的判据。

═══════════════════════════════════════════════════════════════════════════
【四个判据】
═══════════════════════════════════════════════════════════════════════════
 J1 指针数组法（最可能）：找连续 ≥300 个 u32 全指向中文文本区的数组。
    若汉化用「物种ID → 中文名指针」表做显示映射，这张表必然存在。
 J2 定长表法（放宽）：找 11 字节步长、≥300 项、且**每项至少 2 个非 FF 字节**。
 J3 存档结构法：直接看**已知的存档/队伍结构**里名字字段。
    若名字字段宽度仍是 10 字节（原版），则存档不受影响。
    做法：在 ROM 静态数据里找「结构体内 10 字节名字 + 属性」的模板。
 J4 交叉验证：看 0x0871F446 那个「356 段零指针」的大表到底是什么
    （㉛ U3 发现：356 段、段长 9~21 不定、无任何指针）。

用法：python scripts/research/firered/32_species_names_verdict.py
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


def main() -> int:
    zh_b = FR_ZH.read_bytes()
    ja_b = FR_JA.read_bytes()
    n = min(len(zh_b), len(ja_b))
    m = n // 4 * 4

    print("=" * 78)
    print("J1 指针数组法：连续 ≥300 个 u32 全指向中文区")
    print("=" * 78)
    pz = np.frombuffer(zh_b[:m], dtype=np.uint32).astype(np.uint64)
    is_rom = (pz >= BASE) & (pz < BASE + n)
    tgt = (pz - BASE).astype(np.int64)
    hit = np.zeros(len(pz), dtype=bool)
    for lo, hi in CN_ZONES:
        hit |= (is_rom & (tgt >= lo) & (tgt < hi))

    # 找连续 True 的 run
    runs = []
    i = 0
    while i < len(hit):
        if hit[i]:
            j = i
            while j + 1 < len(hit) and hit[j + 1]:
                j += 1
            runs.append((i * 4, j - i + 1))
            i = j + 1
        else:
            i += 1
    runs.sort(key=lambda x: -x[1])
    print(f"  指向中文区的连续 u32 run：{len(runs)} 个，最长的 12 个：")
    for off, cnt2 in runs[:12]:
        print(f"    0x{BASE+off:08X}  {cnt2:>5} 个连续指针")
    big = [r for r in runs if r[1] >= 300]
    print(f"  ⇒ 长度 ≥300 的数组：{len(big)} 个")
    for off, cnt2 in big[:5]:
        print(f"    ★ 0x{BASE+off:08X}  {cnt2} 项")

    # 若找到 300-450 的，看看里面指向的中文串
    for off, cnt2 in big[:3]:
        if 300 <= cnt2 <= 460:
            print(f"\n  检查 0x{BASE+off:08X}（{cnt2} 项）的内容：")
            for k in range(6):
                v = int(np.frombuffer(zh_b, dtype=np.uint32,
                                      count=1, offset=off + k * 4)[0]) - BASE
                e = zh_b.find(b"\xff", v, v + 80)
                txt = zh_b[v:e] if e > 0 else zh_b[v:v + 20]
                print(f"    [{k:>3}] → 0x{BASE+v:08X}  "
                      f"中文{zh_b[v:e].count(0xF7) if e>0 else 0}字  "
                      f"{txt[:24].hex(' ')}")

    # ── J2 定长表法（放宽）────────────────────────────────────────
    print("\n" + "=" * 78)
    print("J2 定长表法：11 字节步长、≥300 项、每项 ≥2 个非 FF 字节")
    print("=" * 78)
    SPECIES, REC = 412, 11

    def scan_relaxed(rom: bytes, min_items: int = 300):
        a = np.frombuffer(rom, dtype=np.uint8)
        # 每项「至少 2 个非 FF 字节」：用滑动窗口统计
        nonff = (a != 0xFF).astype(np.int32)
        csum = np.concatenate(([0], np.cumsum(nonff)))
        out = []
        limit = len(a) - SPECIES * REC
        # 只从「看起来像表头」的位置试：前 11 字节内有 ≥2 非 FF
        cand = np.flatnonzero(csum[REC:limit + REC] - csum[:limit] >= 2)
        for o in cand.tolist()[::7]:        # 抽样加速
            good = 0
            for k in range(SPECIES):
                b0 = o + k * REC
                if csum[b0 + REC] - csum[b0] >= 2:
                    good += 1
                else:
                    break
            if good >= min_items:
                out.append((o, good))
        return out

    tj = scan_relaxed(ja_b)
    tz = scan_relaxed(zh_b)
    print(f"  原版命中 {len(tj)} 处，汉化命中 {len(tz)} 处")
    for o, g in tj[:6]:
        print(f"    原版 0x{BASE+o:08X}  {g} 项")
    for o, g in tz[:6]:
        print(f"    汉化 0x{BASE+o:08X}  {g} 项")

    if tj:
        o = tj[0][0]
        a = ja_b[o:o + SPECIES * REC]
        b = zh_b[o:o + SPECIES * REC]
        diff = sum(1 for x, y in zip(a, b) if x != y)
        print(f"\n  两版 @0x{BASE+o:08X} 不同 {diff:,} 字节"
              f"（{diff/len(a)*100:.2f}%） 汉化 F7 {b.count(0xF7)}")
        for k in range(8):
            ra, rb = a[k*REC:(k+1)*REC], b[k*REC:(k+1)*REC]
            print(f"    [{k}] {'同' if ra==rb else '★异'} 原 {ra.hex(' ')}"
                  f"  汉 {rb.hex(' ')}")

    # ── J4 0x0871F446 是什么 ──────────────────────────────────────
    print("\n" + "=" * 78)
    print("J4 0x0871F446 那个「356 段、零指针」的大表是什么")
    print("=" * 78)
    off = 0x71F446
    seg = zh_b[off:off + 0x2000]
    pos = 0
    k = 0
    print("  前 20 段：")
    while k < 20:
        e = seg.find(b"\xff", pos)
        if e < 0:
            break
        s = seg[pos:e]
        print(f"    [{k:>3}] +0x{pos:04X} L={len(s):<3} 汉字{s.count(0xF7):<2} "
              f"{s[:30].hex(' ')}")
        pos = e + 1
        k += 1
    # 该区在版里是否被指针引用
    pa = np.frombuffer(ja_b[:m], dtype=np.uint32).astype(np.uint64)
    refs = 0
    for s0 in range(0, len(seg)):
        pass
    allrefs = Counter((pz[is_rom] - BASE).astype(np.int64).tolist())
    here = sum(v for k2, v in allrefs.items() if off <= k2 < off + 0x2000)
    print(f"\n  该 0x2000 区间内被 u32 引用的地址数：{here}")
    jhere = sum(1 for v in (pa[is_rom] - BASE).astype(np.int64).tolist()
                if off <= v < off + 0x2000)
    print(f"  原版对应区间被引用数：{jhere}")

    print("\n" + "=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
