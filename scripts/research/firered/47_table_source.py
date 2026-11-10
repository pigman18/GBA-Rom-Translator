#!/usr/bin/env python3
"""调研㊼ 定案：F7 表在 0x0203F2C0（EWRAM），谁写入的、内容是什么。

═══════════════════════════════════════════════════════════════════════════
【已解出的完整链条（㊺/㊻）】
═══════════════════════════════════════════════════════════════════════════
   转码函数 @ 0x081DB660 / 0x081DB800：
     ch = *src
     F6            → 写 0xF7 + 复制 2 字节（F6 hi lo → F7 hi lo）
     F7            → hi = src[1]; ptr = TABLE[hi]; 展开 ptr 指向的串
     F8 F7 hi lo   → 写成 F7 hi lo
     F8 F8         → 另有分支
     其他          → 原样复制

   TABLE 基址 = 字面量 0x081DB85C = **0x0203F2C0**（EWRAM，可写）
   原版此字面量 = 0x00000000

⇒ 汉化在**运行时把一张表铺到 EWRAM 0x0203F2C0**，然后 F7 用它查表。
  这是「中文 = 原版字符片段组合」的实现方式。

═══════════════════════════════════════════════════════════════════════════
【要坐实】
═══════════════════════════════════════════════════════════════════════════
 ① 谁引用 0x0203F2C0（找初始化代码）
 ② 这个表在 ROM 里的**原始数据源**在哪
 ③ 表项数（hi 只有 0x00–0x0A 11 页？那表最多 11 项，与「2299 码位」矛盾）
    —— 这里必须有清楚解释，否则前面「2299 码位」的结论要重审
 ④ F8 F8 分支干什么

用法：python scripts/research/firered/47_table_source.py
"""
from __future__ import annotations

import struct
import subprocess
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
TABLE_ADDR = 0x0203F2C0
TMP = ROOT / "work" / "_probe" / "dis"


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def dis(rom: bytes, addr: int, size: int = 0x100) -> list[str]:
    off = addr - BASE
    TMP.mkdir(parents=True, exist_ok=True)
    b, e = TMP / "r4.bin", TMP / "r4.elf"
    b.write_bytes(rom[off:off + size])
    subprocess.run(["arm-none-eabi-objcopy", "-I", "binary", "-O",
                    "elf32-littlearm", "-B", "arm",
                    "--rename-section", ".data=.text", str(b), str(e)],
                   capture_output=True)
    r = subprocess.run(["arm-none-eabi-objdump", "-d",
                        "--adjust-vma=" + hex(addr), "-M", "force-thumb",
                        str(e)], capture_output=True, text=True)
    return [ln.rstrip() for ln in r.stdout.splitlines()
            if "file format" not in ln and "Disassembly" not in ln and ln.strip()]


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))
    m = n // 4 * 4

    print("=" * 78)
    print("① 谁引用 0x0203F2C0（找 EWRAM 表的初始化代码）")
    print("=" * 78)
    pz = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)
    pa = np.frombuffer(ja[:m], dtype=np.uint32).astype(np.uint64)
    addr = TABLE_ADDR
    hit = np.flatnonzero(pz == addr)
    print(f"  u32 == 0x{addr:08X}：{len(hit)} 处")
    for h in hit.tolist()[:20]:
        o = h * 4
        print(f"    0x{BASE+o:08X}  " +
              ("（原版相同）" if pa[h] == pz[h] else "★汉化新增"))

    # 也搜 0x0203F2xx 一片（基址可能有偏移）
    lo, hi = addr - 0x100, addr + 0x400
    hit2 = np.flatnonzero((pz >= lo) & (pz < hi))
    print(f"\n  u32 落在 0x{lo:08X}..0x{hi:08X}：{len(hit2)} 处")
    for h in hit2.tolist()[:20]:
        o = h * 4
        print(f"    0x{BASE+o:08X} = 0x{int(pz[h]):08X}  " +
              ("（原版相同）" if pa[h] == pz[h] else "★汉化新增"))

    print("\n" + "=" * 78)
    print("② 反汇编引用点（看初始化逻辑）")
    print("=" * 78)
    for h in hit2.tolist()[:3]:
        o = h * 4
        if pa[h] == pz[h]:
            continue
        a = BASE + max(0, o - 0x30)
        print(f"\n  ---- 引用点 0x{BASE+o:08X} ----")
        for ln in dis(zh, a, 0xA0)[:18]:
            print("    " + ln)

    # ── ③ F8 F8 分支 ──────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ F8 F8 的含义：统计它的用法")
    print("=" * 78)
    for name, rom in (("原版", ja), ("汉化", zh)):
        c = Counter()
        i = rom.find(b"\xf8\xf8")
        while i >= 0:
            c[rom[i + 2] if i + 2 < n else 0] += 1
            i = rom.find(b"\xf8\xf8", i + 1)
        print(f"  {name} F8 F8 后面的字节 top8："
              + ", ".join(f"0x{k:02X}:{v}" for k, v in c.most_common(8)))

    # ── ④ 关键：hi 只有 11 页，那 2299 码位怎么来 ─────────────────
    print("\n" + "=" * 78)
    print("④ 关键矛盾：hi 只有 0x00–0x0A，表最多 11 项？")
    print("=" * 78)
    # 统计 F7 后面第一个字节（= hi）的分布
    c = Counter()
    i = zh.find(b"\xf7")
    while i >= 0 and i + 1 < n:
        c[zh[i + 1]] += 1
        i = zh.find(b"\xf7", i + 1)
    tot = sum(c.values())
    print(f"  傅化版 F7 后面那一字节（hi）的分布，共 {tot:,} 处：")
    for k, v in c.most_common(20):
        print(f"    0x{k:02X}: {v:>7,}（{v/tot*100:>5.1f}%）")
    print(f"  不同 hi 取值：{len(c)}")
    print(f"\n  ⇒ 若 hi 集中在 0x00–0x0A，则表只有 ~11 项，每项一个「字符片段」")
    print(f"     那么「2299 码位」的说法是**错的**——需按『表项数』重算")

    # ── ⑤ 表项数上限 ──────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("⑤ 表结构：F7 hi 的 2 字节形式 vs F6/F8 的 4 字节形式")
    print("=" * 78)
    for name, rom in (("原版", ja), ("汉化", zh)):
        c6 = rom.count(b"\xf6")
        c7 = rom.count(b"\xf7")
        c8 = rom.count(b"\xf8")
        print(f"  {name}: F6={c6:,}  F7={c7:,}  F8={c8:,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
