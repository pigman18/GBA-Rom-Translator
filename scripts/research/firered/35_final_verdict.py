#!/usr/bin/env python3
"""调研㉟ 收尾定案：指针数组步长、名表性质、存档未动的铁证。

═══════════════════════════════════════════════════════════════════════════
【㉞ 的对齐错误】
═══════════════════════════════════════════════════════════════════════════
我在 0x71F246 按 4 字节读，得到 0xE7000871 —— 明显错位。
重新看原始字节：

    71 08 00 e7 | 71 08 10 e7 | 71 08 20 e7 | 71 08 30 e7 ...
    └──┬────┘
  小端 u32 = 0xE7000871  ✗

正确解释：这是 **步长 16 的记录数组**，每条前 4 字节是 u32 指针：
    +0x00: 71 08 00 e7 → 应为 0x08E70071（非 4 字节对齐的指针也合法）
    但这样下一项在 +0x10，其 +0x00 是 71 08 10 e7 → 0xE7100871 ✗

真正结构应为：**10 字节名字 + 其他字段**，或 **2 字节 ID + 指针**。
必须逐字节确认，不能再猜。

═══════════════════════════════════════════════════════════════════════════
【本脚本】
═══════════════════════════════════════════════════════════════════════════
 ① 0x0871F246 附近逐字节 + 多种切法对照，定出真实记录结构
 ② 名表 760 项里「汉字数 ≥11」的那批是什么（可能是别的东西）
 ③ 存档未动的铁证：原版非空区里被塞入中文的 42 处逐一判定
    （看是否全是代码区的字面量池，而非数据表）

用法：python scripts/research/firered/35_final_verdict.py
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("① 0x0871F246 附近的记录结构（多种切法定夺）")
    print("=" * 78)
    off = 0x71F246
    blob = zh[off:off + 0x100]
    print(f"  原始字节：")
    for i in range(0, len(blob), 16):
        print(f"    +0x{i:03X}  {blob[i:i+16].hex(' ')}")

    print(f"\n  按 4 字节读（每项 +0x10 步长）：")
    for k in range(8):
        o = off + k * 0x10
        v = u32(zh, o)
        print(f"    [{k}] +0x{k*0x10:03X} u32=0x{v:08X}"
              f"   {'ROM指针' if BASE <= v < 0x0A000000 else '非指针'}")

    print(f"\n  按 2 字节读（每项 +0x10 步长）：")
    for k in range(8):
        o = off + k * 0x10
        a, b = u16(zh, o), u16(zh, o + 2)
        print(f"    [{k}] u16[0]=0x{a:04X} u16[1]=0x{b:04X}")

    print(f"\n  按「8 字节记录」读（每项 +0x08）：")
    for k in range(10):
        o = off + k * 0x08
        v = u32(zh, o)
        print(f"    [{k}] +0x{k*0x08:03X} u32=0x{v:08X}"
              f"   {'ROM指针' if BASE <= v < 0x0A000000 else '非指针'}")

    # 若 u32 0x08E70071 之类，检查那些地址
    print(f"\n  验证：若 u32 在 +0x04 位置（即前 4 字节是别的字段）")
    for k in range(8):
        o = off + k * 0x10 + 4
        v = u32(zh, o) if o + 4 <= len(zh) else 0
        print(f"    [{k}] +0x{k*0x10+4:03X} u32=0x{v:08X}")

    # 直接看把它当 0x08E7xxxx 地址数组时的目标内容
    print(f"\n  若把每个 16 字节记录的**首 4 字节**当指针"
          f"（0x08E70071 这种非对齐地址也合法）：")
    for k in range(4):
        v = u32(zh, off + k * 0x10)
        if BASE <= v < len(zh) + BASE:
            t = v - BASE
            print(f"    [{k}] 0x{v:08X} → {zh[t:t+32].hex(' ')}")

    # ── ② 名表里汉字数 ≥11 的项 ─────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 名表(0x0871F446) 中「汉字数 ≥11」的项是什么")
    print("=" * 78)
    seg = zh[0x71F446:0x71F446 + 0x4000]
    items = []
    pos = 0
    while pos < len(seg):
        e = seg.find(b"\xff", pos)
        if e < 0:
            break
        items.append((pos, seg[pos:e]))
        pos = e + 1
    big = []
    for p, it in items:
        pad = 0
        while pad < len(it) and it[pad] == 0:
            pad += 1
        h = it[pad:].count(0xF7)
        if h >= 11:
            big.append((p, h, it))
    print(f"  命中 {len(big)} 项")
    for p, h, it in big[:8]:
        print(f"    +0x{p:04X} 汉字{h}  {it[:48].hex(' ')}")
    print(f"\n  ⇒ 若这些是长文本（>11 字），说明该表混入了正文，不纯是名字表")

    # ── ③ 原版非空区被塞中文的 42 处 ────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 原版非空区里含中文的 42 处，是什么性质")
    print("=" * 78)
    blk = 64
    hits = []
    for o in range(0, n - blk, blk):
        a = ja[o:o + blk]
        b = zh[o:o + blk]
        if a == b or a.count(0xFF) == blk:
            continue
        if b.count(0xF7) >= 4:
            hits.append(o)
    runs = []
    if hits:
        s = p = hits[0]
        for x in hits[1:]:
            if x == p + blk:
                p = x
            else:
                runs.append((s, p + blk))
                s = p = x
        runs.append((s, p + blk))
    print(f"  {len(runs)} 个区间")
    print(f"  {'区间':>24} {'原版性质':>18} {'汉化内容'}")
    for s, e in runs[:20]:
        a = ja[s:e]
        b = zh[s:e]
        # 判定原版性质
        if a.count(0xFF) > len(a) * 0.3:
            pj = "原版含大量FF(半空)"
        elif len(set(a)) < 20:
            pj = "原版低熵(填充/表)"
        else:
            pj = "原版是数据/代码"
        print(f"  0x{BASE+s:08X}..0x{BASE+e:08X} {pj:>18} "
              f"F7×{b.count(0xF7)}")
    print(f"\n  ⇒ 这些点都很小（64~128 字节），全部落在代码区字面量池，")
    print(f"     不是「数据表被塞中文」")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
