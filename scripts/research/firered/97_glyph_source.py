#!/usr/bin/env python3
"""调研(97) 字形从哪来：查候选区是不是「压缩字形」或「字形索引」。

═══════════════════════════════════════════════════════════════════════════
【关键事实】
═══════════════════════════════════════════════════════════════════════════
(96) 结论：
  · VRAM 里字形的**完整 32 字节在 ROM 里搜不到**（0 处命中）
  · 但存在大量「原版全 FF、汉化有内容、F7=0」的区：
      0x08908000, 0x08930000, 0x089B0000(49.9%!), 0x089C0000,
      0x08A70000, 0x08B00000, 0x08B50000(40.3%), 0x08B60000(39.4%), ...

⇒ 字形**不是** ROM 里直接存 4bpp 位图。两种可能：
    H1 字形在 ROM 里按别的格式存（1bpp / bitplane / 压缩），运行时展开成 4bpp
    H2 字形是从「原版日文字模」变形生成的（比如放大/替换笔画）

【本脚本】
 ① 检查候选区的字节特征（是不是 1bpp 位图？是不是压缩？）
 ② 若像 1bpp：按 11×11 或 8×8 切，画出来看
 ③ 若像压缩：找 LZ/RLE 标记
 ④ 对比原版同一区域（应该是全 FF）

用法：python scripts/research/firered/97_glyph_source.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000

# (96) 里最有希望的候选（汉化非FF 占比高、F7≈0）
CAND = [
    (0x9B0000, "0x089B0000", 49.9),
    (0xB50000, "0x08B50000", 40.3),
    (0xB60000, "0x08B60000", 39.4),
    (0xB70000, "0x08B70000", 26.5),
    (0xB80000, "0x08B80000", 26.4),
    (0xB90000, "0x08B90000", 26.9),
    (0xB00000, "0x08B00000", 24.6),
    (0xA70000, "0x08A70000", 23.0),
    (0x908000, "0x08908000", 20.5),
]


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("① 候选区的字节特征")
    print("=" * 78)
    print(f"  {'区':>14} {'大小':>8} {'不同字节值':>10} {'00占比':>8} "
          f"{'FF占比':>8} {'高熵?':>6}")
    for off, name, _ in CAND:
        seg = np.frombuffer(zh[off:off + 0x8000], dtype=np.uint8)
        uq = len(np.unique(seg))
        z = (seg == 0).mean()
        ff = (seg == 0xFF).mean()
        # 熵（越高越像压缩/随机）
        c = Counter(seg.tolist())
        ent = -sum((v / len(seg)) * np.log2(v / len(seg))
                   for v in c.values())
        print(f"  {name:>14} {len(seg):>8,} {uq:>10} {z:>7.1%} "
              f"{ff:>7.1%} {ent:>6.2f}")

    # ── ② 逐个候选看前 64 字节 ──────────────────────────────────
    print("\n" + "=" * 78)
    print("② 各候选区前 64 字节")
    print("=" * 78)
    for off, name, _ in CAND:
        print(f"\n  {name}:")
        for i in range(0, 64, 16):
            print(f"    +0x{i:02X}: {zh[off+i:off+i+16].hex(' ')}")

    # ── ③ 试按 1bpp 8×8 / 11×11 解释 0x089B0000 ─────────────────
    print("\n" + "=" * 78)
    print("③ 按 1bpp 解释 0x089B0000（每字 11×11 => 16 字节）")
    print("=" * 78)
    off = 0x9B0000
    for k in range(6):
        blob = zh[off + k * 16: off + (k + 1) * 16]
        print(f"\n  第 {k} 个 16 字节: {blob.hex(' ')}")
        # 按每行 2 字节（16 位）画 11 行
        for y in range(11):
            if y * 2 + 1 >= len(blob):
                break
            bits = (blob[y * 2] << 8) | blob[y * 2 + 1]
            line = "".join("#" if (bits >> (15 - x)) & 1 else "."
                           for x in range(11))
            print(f"    {line}")

    # ── ④ 也试 8×8 1bpp（8 字节/字）──────────────────────────────
    print("\n" + "=" * 78)
    print("④ 按 8×8 1bpp 解释（8 字节/字）")
    print("=" * 78)
    for k in range(6):
        blob = zh[off + k * 8: off + (k + 1) * 8]
        print(f"\n  第 {k} 个 8 字节: {blob.hex(' ')}")
        for y in range(8):
            line = "".join("#" if (blob[y] >> (7 - x)) & 1 else "."
                           for x in range(8))
            print(f"    {line}")

    # ── ⑤ 对比原版 ──────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("⑤ 原版同一区域（确认是空白）")
    print("=" * 78)
    for off, name, _ in CAND[:4]:
        seg = ja[off:off + 0x1000]
        nz = sum(1 for b in seg if b != 0xFF)
        print(f"  {name}: 原版 0x1000 字节里非 FF {nz}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
