#!/usr/bin/env python3
"""调研㉘ 决定性实验：火红原版（日文）的文本到底是 1 字节还是 2 字节编码。

═══════════════════════════════════════════════════════════════════════════
【为什么必须做这个实验】
═══════════════════════════════════════════════════════════════════════════
㉖ 在 0x083DD000 看到：
    raw :  01 00 1c 10 1d 10 1e 10 1f 10 10 5e 10 5f 60 7f 70 10 71 10 ...
    u16 :  0001 101c 101d 101e 101f 5e10 5f10 7f60 1070 1071 ...

按 u16 读，**0x101c / 0x101d / 0x101e / 0x101f 是四个连续码位**；
按 1 字节读则完全不成话。

若日文火红是 **2 字节编码**，那么：
   · 我前面所有「日文 1 字节串」的切分（㉓/㉕/㉖/㉗）**全部作废**
   · 「F7 是 3 字节、比原版多 1 字节」的结论也要重算

═══════════════════════════════════════════════════════════════════════════
【三个独立判据（任一成立即可定案）】
═══════════════════════════════════════════════════════════════════════════
 判据 A：把整个 ROM 按 u16 读，统计「低字节 == 0x00」的比例
         2 字节编码里 0x00 高字节极常见（ASCII 段），1 字节编码里很少
 判据 B：找一个**已知的固定字符串**比对。火红标题画面/开场有
         「©2004 Pokémon」「PUSH START」之类，但更需要日文固定词。
         更稳的是找**连续重复的同一码位**（如「……」= 连续同码）
 判据 C：统计 1 字节与 2 字节两种切法下，**串尾 FF 的分布规整度**
         真编码的串尾应让「串长相异但都在合理范围」；
         假编码会产生超长串或无 FF 的长段

另有判据 D：F7 本身。若原始是 2 字节编码，F7 作为**前缀**意味着
         「F7 xx yy」= 3 字节，那就不是「固定 2 字节」，需要另外解释。
         实测 0x083DD000 的 F7 一次都没出现，说明这个区可能不是中文意义上的文本。

用法：python scripts/research/firered/28_encoding_width_test.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def seg_stats(rom: bytes, lo: int, hi: int, label: str) -> None:
    seg = rom[lo:hi]
    a = np.frombuffer(seg, dtype=np.uint8)
    n16 = len(seg) // 2
    u16 = np.frombuffer(seg[:n16 * 2], dtype="<u2")
    hi_byte = (u16 >> 8) & 0xFF
    lo_byte = u16 & 0xFF
    print(f"\n  {label}  [{hi-lo:,} B]")
    print(f"    u16 高字节 == 0x00 的比例: {(hi_byte == 0).mean():>6.1%}")
    print(f"    u16 高字节 == 0x10 的比例: {(hi_byte == 0x10).mean():>6.1%}")
    print(f"    u16 高字节 == 0xFF 的比例: {(hi_byte == 0xFF).mean():>6.1%}")
    print(f"    u16 低字节 == 0xFF 的比例: {(lo_byte == 0xFF).mean():>6.1%}")
    print(f"    u16 不同值个数: {len(np.unique(u16)):,} / {n16:,}")
    print(f"    u16 高字节不同值: {len(np.unique(hi_byte))}")
    c = Counter(hi_byte.tolist())
    print(f"    高字节 top10: "
          + ", ".join(f"0x{k:02X}:{v}" for k, v in c.most_common(10)))


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("判据 A：按 u16 读时的高字节分布")
    print("=" * 78)
    # 已知的日文文本区（㉕ 锚点集中处）与已知非文本区（代码开头）
    seg_stats(ja, 0x3DD000, 0x3E2000, "原版 0x083DD000（疑文本）")
    seg_stats(ja, 0x19B000, 0x1AA000, "原版 0x0819B000（疑文本）")
    seg_stats(ja, 0x000000, 0x004000, "原版 0x08000000（代码）")
    seg_stats(ja, 0x3E729C, 0x3E829C, "原版 0x083E729C（㉓ 首项指向）")
    seg_stats(zh, 0x6D0000, 0x6E0000, "汉化 0x086D0000（已知中文）")

    # ── 判据 B：找连续重复码位（「……」类）─────────────────────────
    print("\n" + "=" * 78)
    print("判据 B：连续相同码位（真文本里「重复标点/空格」常见）")
    print("=" * 78)
    for name, rom, lo, hi in (
        ("原版 0x083DD000", ja, 0x3DD000, 0x3E2000),
        ("原版 0x0819B000", ja, 0x19B000, 0x1AA000),
    ):
        seg = rom[lo:hi]
        u16 = np.frombuffer(seg[:len(seg) // 2 * 2], dtype="<u2")
        rep = int((u16[1:] == u16[:-1]).sum())
        print(f"  {name}: 相邻 u16 相同的次数 {rep}"
              f"（{rep/max(1,len(u16)-1)*100:.2f}%）")
        # 单字节切法
        a = np.frombuffer(seg, dtype=np.uint8)
        rep1 = int((a[1:] == a[:-1]).sum())
        print(f"    单字节切法: 相邻字节相同 {rep1}"
              f"（{rep1/max(1,len(a)-1)*100:.2f}%）")

    # ── 判据 C：两种切法下串尾 FF 出现的均匀度 ──────────────────────
    print("\n" + "=" * 78)
    print("判据 C：以 FF 为串尾，两种切法的「串长分布」谁更规整")
    print("=" * 78)
    for name, rom, lo, hi in (
        ("原版 0x083DD000", ja, 0x3DD000, 0x3E2000),
        ("原版 0x0819B000", ja, 0x19B000, 0x1AA000),
    ):
        seg = rom[lo:hi]
        # 单字节
        lens1 = []
        pos = 0
        while True:
            e = seg.find(b"\xff", pos)
            if e < 0:
                break
            if e > pos:
                lens1.append(e - pos)
            pos = e + 1
        # 双字节：FF 必须落在偶数字节（相对该区起点）
        lens2 = []
        pos = 0
        while True:
            e = seg.find(b"\xff", pos)
            if e < 0:
                break
            if e % 2 == 0:      # 高字节位置
                if e > pos:
                    lens2.append((e - pos) // 2)
            pos = e + 1
        print(f"\n  {name}")
        for nm, L in (("单字节", lens1), ("双字节", lens2)):
            if not L:
                print(f"    {nm}: 无串")
                continue
            a = np.array(L)
            print(f"    {nm}: {len(L):,} 串  均值 {a.mean():.1f} "
                  f"中位 {np.median(a):.0f} 最大 {a.max()}"
                  f"  >100 的 {int((a>100).sum())}")

    # ── 判据 D：在 0x083DD000 里找 F7 与 FB/FC/FE 控制符 ────────────
    print("\n" + "=" * 78)
    print("判据 D：该区出现的「特殊字节」—— 若按 u16 读，它们是控制码还是数据")
    print("=" * 78)
    for name, rom, lo, hi in (
        ("原版 0x083DD000", ja, 0x3DD000, 0x3E2000),
        ("原版 0x0819B000", ja, 0x19B000, 0x1AA000),
    ):
        seg = rom[lo:hi]
        u16 = np.frombuffer(seg[:len(seg) // 2 * 2], dtype="<u2")
        print(f"\n  {name}")
        for probe in (0x00FF, 0xFB00, 0xFC00, 0xFE00, 0xFF00,
                      0x00FB, 0x00FC, 0x00FE, 0x1010, 0x0000):
            c = int((u16 == probe).sum())
            if c:
                print(f"    u16 == 0x{probe:04X} × {c}")
        hib = Counter(((u16 >> 8) & 0xFF).tolist())
        print(f"    高字节 top6: "
              + ", ".join(f"0x{k:02X}:{v}" for k, v in hib.most_common(6)))

    print("\n" + "=" * 78)
    print("结论提示")
    print("=" * 78)
    print("  · 若『双字节』串长分布明显更规整、且 >100 的长串消失 ⇒ 是 2 字节编码")
    print("  · 若『单字节』更好 ⇒ 是 1 字节编码，0x10xx 只是恰好像连续码位")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
