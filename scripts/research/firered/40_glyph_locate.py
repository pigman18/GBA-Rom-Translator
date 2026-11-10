#!/usr/bin/env python3
"""调研㊵ 中文字模到底在哪 —— 关键：是否覆盖了原版字模区。

═══════════════════════════════════════════════════════════════════════════
【㊴ 的重要发现】
═══════════════════════════════════════════════════════════════════════════
所有「原版空白 + 汉化有内容」的新增区里：
    0x086D0000..0x08730000   F7 占 23%~30%  ⇒ 是**文本**
    0x089B0000 / 0x08B50000 / 0x08B60000  F7 = 0% ⇒ **不是文本**（可能是字模！）
    （但这两片「汉化非 FF 只有 24%」，说明大半还是 FF）

⇒ **中文字模不在文本区旁边**。两个可能：
   A) 在 0x089B0000 / 0x08B50000 这类「F7=0 的新增区」
   B) **覆盖了原版的字模区**（原版字模是日文假名，汉化换成汉字，同样大小）

B 很关键：若字模区被就地覆盖，那么：
   · 火红不需要「新增字模区」
   · 但也就**不能同时显示日文和中文**（日文字模被覆盖了）
   · 实测火红是「日版汉化」，确实可能全中文、不留日文

═══════════════════════════════════════════════════════════════════════════
【验证方法】
═══════════════════════════════════════════════════════════════════════════
 ① 检查 0x089B0000 / 0x08B50000 / 0x08B60000 是什么（位图？）
    —— 用「行墨量钟形」和「相邻块相关」判
 ② 找原版字模区（原版就有、汉化也改动的区）
    —— 差异分析：原版非空 + 汉化非空 + 大量差异
 ③ 对候选字模区，用 8×12 / 8×16 切块，把某几个 tile **画成 ASCII 点阵**
    —— 人眼直接判断是不是汉字（这是最硬的判据，不靠统计）

用法：python scripts/research/firered/40_glyph_locate.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def draw_tile(blob: bytes, w: int, h: int, bpp: int = 1) -> list[str]:
    """把字模画成 ASCII。bpp=1 时每行 w/8 字节，每像素 1 位。"""
    row_bytes = (w * bpp + 7) // 8
    out = []
    for y in range(h):
        row = blob[y * row_bytes:(y + 1) * row_bytes]
        if len(row) < row_bytes:
            break
        bits = np.unpackbits(np.frombuffer(row, dtype=np.uint8))
        line = "".join("#" if b else "." for b in bits[:w])
        out.append(line)
    return out


def show(rom: np.ndarray, off: int, w: int, h: int, n: int = 4,
         label: str = "") -> None:
    tb = ((w + 7) // 8) * h
    print(f"\n  {label}  起始 0x{BASE+off:08X}  每字 {tb} 字节")
    for k in range(n):
        o = off + k * tb
        blob = rom[o:o + tb].tobytes()
        ink = sum(bin(x).count("1") for x in blob)
        print(f"    tile[{k}] ink={ink}")
        for line in draw_tile(blob, w, h):
            print(f"      {line}")


def main() -> int:
    zh = np.frombuffer(FR_ZH.read_bytes(), dtype=np.uint8)
    ja = np.frombuffer(FR_JA.read_bytes(), dtype=np.uint8)
    n = min(len(zh), len(ja))

    # ── ① 检查 F7=0 的新增区 ──────────────────────────────────────
    print("=" * 78)
    print("① 新增区里 F7=0 的几片是什么（0x089B0000 / 0x08B50000 / 0x08B60000）")
    print("=" * 78)
    for off in (0x9B0000, 0xB50000, 0xB60000):
        for w, h in ((8, 12), (8, 16), (16, 16)):
            tb = ((w + 7) // 8) * h
            cnt = 0x4000 // tb
            blk = zh[off:off + cnt * tb].reshape(cnt, tb)
            ink = np.unpackbits(blk).reshape(cnt, tb * 8).sum(axis=1)
            # 有多少 tile 墨量在合理区间（不是全空也不是全满）
            good = int(((ink > 2) & (ink < tb * 8 * 0.7)).sum())
            print(f"  0x{BASE+off:08X} {w}×{h:<3} tile {tb:>3}B  "
                  f"墨量均值 {ink.mean():>5.1f}  有效 tile {good}/{cnt} "
                  f"({good/cnt*100:>5.1f}%)")
        print()

    print("  直接看图（0x089B0000，8×12）：")
    show(zh, 0x9B0000, 8, 12, 3, "汉化 0x089B0000")
    print("\n  原版同位置（8×12）：")
    show(ja, 0x9B0000, 8, 12, 3, "原版 0x089B0000")

    # ── ② 找「原版非空 + 汉化大量改动」的位图区 ──────────────────
    print("\n" + "=" * 78)
    print("② 原版和非空、汉化大量改动的区（疑似字模被覆盖）")
    print("=" * 78)
    SEG = 0x8000
    nseg = n // SEG
    a = ja[:nseg * SEG].reshape(nseg, SEG)
    b = zh[:nseg * SEG].reshape(nseg, SEG)
    diff = (a != b).mean(axis=1)
    notff_o = (a != 0xFF).mean(axis=1)
    notff_z = (b != 0xFF).mean(axis=1)
    # 原版有内容 + 汉化有内容 + 改动率高
    cand = np.flatnonzero((notff_o > 0.85) & (notff_z > 0.85) & (diff > 0.60))
    print(f"  候选 32KB 块：{len(cand)}")
    print(f"  {'区':>14} {'原版非FF':>9} {'汉化非FF':>9} {'改动率':>8}")
    for i in cand.tolist()[:25]:
        print(f"  0x{BASE+i*SEG:08X} {notff_o[i]:>8.1%} {notff_z[i]:>8.1%} "
              f"{diff[i]:>8.1%}")

    # ── ③ 对最像字模的区直接画图 ─────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 对「原版非空 + 高改动率」的区直接画点阵（人眼判汉字）")
    print("=" * 78)
    for i in cand.tolist()[:4]:
        off = i * SEG
        show(zh, off, 8, 12, 2, f"汉化 0x{BASE+off:08X} 8×12")
        show(zh, off, 8, 16, 2, f"汉化 0x{BASE+off:08X} 8×16")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
