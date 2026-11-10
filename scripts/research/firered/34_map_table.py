#!/usr/bin/env python3
"""调研㉞ 解剖 0x0871F246 之前的指针数组 + 0x0871F446 名表，确认这是显示映射表。

═══════════════════════════════════════════════════════════════════════════
【㉝ 的发现】
═══════════════════════════════════════════════════════════════════════════
 0x0871F446 起是「00 补齐 + 中文名 + FF」的变长项表，前 40 项汉字数 1~5，
 符合**名字**特征（名字短）。

 更关键：紧邻它之前的 0x0871F246 是**步长 0x10 的指针数组**，
 值形如 0x08E70071 / 0x08E71071 / 0x08E72071 …（递增 0x1000）。

 原版 0x71F000..0x722000 **全 FF** ⇒ 这块是汉化**完全新增**的。

⇒ 强烈怀疑：这是「索引 → 名字」的**显示映射表**，
  原版物种名的存储和存档结构完全没动 ⇒ 这就是「串档不乱」的机制。

本脚本坐实：
 ① 指针数组长度、步长、目标规律
 ② 目标处（0x08E7xxxx）的内容是什么
 ③ 名表项数 vs 火红物种数
 ④ 对照：汉化有没有改过「存档会用到的那份物种名」

用法：python scripts/research/firered/34_map_table.py
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
ARR = 0x71F246
NAMES = 0x71F446


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    print("=" * 78)
    print("① 0x0871F246 指针数组")
    print("=" * 78)
    # 找这个数组的真实起点和长度：向两侧扩，只要值在 ROM 内
    def valid(o):
        if o < 0 or o + 4 > len(zh):
            return False
        v = u32(zh, o)
        return BASE <= v < 0x0A000000

    lo = ARR
    while lo - 4 >= 0 and valid(lo - 4):
        lo -= 4
    hi = ARR
    while hi + 4 <= len(zh) and valid(hi + 4):
        hi += 4
    cnt = (hi - lo) // 4 + 1
    print(f"  数组范围 0x{BASE+lo:08X}..0x{BASE+hi:08X}  共 {cnt} 个 u32")

    vals = [u32(zh, lo + k * 4) for k in range(cnt)]
    print(f"  前 12 个: {[f'0x{v:08X}' for v in vals[:12]]}")
    gaps = [vals[k + 1] - vals[k] for k in range(min(20, cnt - 1))]
    print(f"  相邻差值: {[hex(g) for g in gaps]}")

    # 目标分布
    print(f"\n  目标地址分布（按 64KB）：")
    tc = Counter((v - BASE) // 0x10000 for v in vals
                 if BASE <= v < len(zh) + BASE)
    for s, c in tc.most_common(10):
        print(f"    0x{BASE+s*0x10000:08X}  {c:>5} 个")

    print(f"\n  前 6 个目标处的内容：")
    for v in vals[:6]:
        if not (BASE <= v < len(zh) + BASE):
            continue
        t = v - BASE
        blob = zh[t:t + 40]
        print(f"    0x{v:08X}: {blob.hex(' ')}")
        print(f"      汉字数 {blob.count(0xF7)}")

    # ── ② 名表 ─────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 0x0871F446 名表：项数、汉字数分布")
    print("=" * 78)
    seg = zh[NAMES:NAMES + 0x4000]
    items = []
    pos = 0
    while pos < len(seg):
        e = seg.find(b"\xff", pos)
        if e < 0:
            break
        items.append(seg[pos:e])
        pos = e + 1
    print(f"  0x4000 字节内项数：{len(items)}")
    han = []
    for it in items:
        pad = 0
        while pad < len(it) and it[pad] == 0:
            pad += 1
        han.append(it[pad:].count(0xF7))
    print(f"  汉字数分布：{dict(Counter(han))}")
    print(f"  平均汉字数 {sum(han)/len(han):.2f}")
    print(f"  ⇒ 火红可捕捉物种 386 种，含空槽 412")
    print(f"  前 30 项汉字数：{han[:30]}")

    # ── ③ 原版该区 ─────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 原版 0x0871F000..0x08722000 是否为空（证明是新增表）")
    print("=" * 78)
    a = ja[0x71F000:0x722000]
    nz = sum(1 for x in a if x != 0xFF)
    print(f"  区间 {len(a):,} 字节，非 FF 字节 {nz:,}")
    print(f"  ⇒ {'**全空，表为汉化完全新增**' if nz == 0 else '有原版数据'}")

    # 整个 0x0710000..0x0722000
    a2 = ja[0x710000:0x722000]
    nz2 = sum(1 for x in a2 if x != 0xFF)
    print(f"  原版 0x08710000..0x08722000：{len(a2):,} 字节，非 FF {nz2:,}")

    # ── ④ 存档用的物种名是否被改 ───────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 存档会读到的那份物种名，汉化有没有改")
    print("=" * 78)
    # Gen3 存档里名字来自 gSpeciesNames[]（POKEMON_NAME_LENGTH=10 + 1）
    # 判据：在**原版非空区**里找「汉化版含 F7」的位置
    # 前面 ⒇ 已测：原版日文文本 97.9% 原样保留；这里专门看
    # 「原版非空 + 汉化含 F7」的块
    blk = 64
    hits = []
    for o in range(0, len(zh) - blk, blk):
        a3 = ja[o:o + blk]
        b3 = zh[o:o + blk]
        if a3 == b3:
            continue
        if a3.count(0xFF) == blk:
            continue          # 原本就是空的（新增区）
        if b3.count(0xF7) >= 4:
            hits.append(o)
    print(f"  「原版非空 + 汉化含 ≥4 个 F7」的 64B 块：{len(hits):,}")
    if hits:
        runs = []
        s = p = hits[0]
        for x in hits[1:]:
            if x == p + blk:
                p = x
            else:
                runs.append((s, p + blk))
                s = p = x
        runs.append((s, p + blk))
        print(f"  聚合成 {len(runs)} 个区间，前 12：")
        for s, e in runs[:12]:
            print(f"    0x{BASE+s:08X}..0x{BASE+e:08X}  {(e-s)//1024}KB")
    else:
        print("  ⇒ **一处都没有：汉化没在任何「原版非空区」里塞中文**")
        print("  ⇒ 所有中文都在原版空白区 ⇒ 原版数据结构（含存档用的名字）完全未动")
        print("  ⇒ 这就是「串档不乱」的机制")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
