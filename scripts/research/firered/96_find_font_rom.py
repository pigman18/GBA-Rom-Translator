#!/usr/bin/env python3
"""调研(96) 找完整字库源头：VRAM 里的字形字节能否在 ROM 中找到。

═══════════════════════════════════════════════════════════════════════════
【用户指出的问题】
═══════════════════════════════════════════════════════════════════════════
「字库图怎么只有这几个字？」

**问得对。** (94)/(95) 只抓到 28 个字位，因为那是**当前菜单画面**
（继续游戏/主角/时间/图鉴/徽章/开始新游戏）里出现的字。
VRAM 里只有这一帧用到的字形 —— 内存装不下两千多个字。

真正的**完整字库在 ROM 里**，必须去 ROM 找。

═══════════════════════════════════════════════════════════════════════════
【本脚本的判据链】
═══════════════════════════════════════════════════════════════════════════
 ① 从 VRAM 取出一个已知字形的原始字节
    （如 tile 2 的 32 字节 = "续" 的左上半）
 ② 在汉化 ROM 里逐字节搜索
    · 找到 ⇒ 字库在 ROM 且格式相同（4bpp 直接存）
    · 找不到 ⇒ ROM 里的字库格式不同（压缩/不同位深/或运行时生成）
 ③ 若直接搜不到，试：
    · 只搜 8 字节前缀（容忍后面被改）
    · 搜 nibble 重排后的形式（4bpp 有时按 bitplane 存）
 ④ 也检查「原版空白、汉化有内容」但 F7=0 的那几个区
    （0x089B0000 / 0x08B50000 / 0x08B60000 —— 不是文本但被写入）

用法：python scripts/research/firered/96_find_font_rom.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
G = ROOT / "work" / "_probe" / "glyphs"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def main() -> int:
    vram = (G / "g1.vram.bin").read_bytes()
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    print("=" * 78)
    print("① 从 VRAM 取已知字形的原始字节")
    print("=" * 78)
    # tile 2 = "续" 的左上块（pal=15 的文字 tile）
    samples = {}
    for t in (2, 3, 4, 26, 27, 28):
        blob = vram[t * 32:(t + 1) * 32]
        samples[t] = blob
        print(f"  tile {t}: {blob.hex(' ')}")

    print("\n" + "=" * 78)
    print("② 在汉化 ROM 里搜这些 32 字节")
    print("=" * 78)
    for t, blob in samples.items():
        hits = []
        i = zh.find(blob)
        while i >= 0 and len(hits) < 8:
            hits.append(i)
            i = zh.find(blob, i + 1)
        print(f"  tile {t}: 完整 32B 命中 {len(hits)} 处"
              + (f"  {[f'0x{BASE+x:08X}' for x in hits]}" if hits else ""))

    print("\n" + "=" * 78)
    print("③ 只搜 8 字节（容忍后面被改）")
    print("=" * 78)
    for t, blob in samples.items():
        head = blob[:8]
        hits = []
        i = zh.find(head)
        while i >= 0 and len(hits) < 10:
            hits.append(i)
            i = zh.find(head, i + 1)
        print(f"  tile {t} 前8B: {head.hex()} → {len(hits)} 处"
              + (f"  {[f'0x{BASE+x:08X}' for x in hits[:5]]}" if hits else ""))

    # ── ④ 检查「原版空白、汉化有内容但 F7=0」的区 ────────────────
    print("\n" + "=" * 78)
    print("④ 「原版全FF、汉化有内容、F7=0」的区（字库候选）")
    print("=" * 78)
    n = min(len(zh), len(ja))
    SEG = 0x8000
    for base in range(0, n, SEG):
        seg_z = zh[base:base + SEG]
        seg_j = ja[base:base + SEG]
        if len(seg_z) < SEG:
            break
        if seg_j.count(0xFF) < SEG * 0.99:
            continue                      # 原版不是空白
        nonff = SEG - seg_z.count(0xFF)   # 汉化写入了
        if nonff < SEG * 0.05:
            continue
        f7 = seg_z.count(0xF7)
        if f7 > SEG * 0.01:
            continue                      # 是文本区，跳过
        print(f"  0x{BASE+base:08X}: 原版全空 / 汉化非FF {nonff/SEG*100:>5.1f}% "
              f"/ F7 {f7:>4}  ← 候选字库区")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
