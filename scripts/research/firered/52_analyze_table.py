#!/usr/bin/env python3
"""调研(52) 解剖实测 EWRAM 里的 F7 表 —— 验证「用原版字符拼」还是「有解压算法」。

═══════════════════════════════════════════════════════════════════════════
【这一步是整个调研的关键】
═══════════════════════════════════════════════════════════════════════════
前一轮我从静态反汇编推断「汉化的中文 = 原版字符序列拼出来的」。
用户提醒：**不要轻易下结论，可能有解压算法在里面**。

现在有了实测 EWRAM（6 个界面状态，`0x0203F2C0` 起 1024 字节），
可以正面回答：

  · 若表项是 ROM 指针，且指向的串**就是普通单字节文本**
    ⇒ 「拼字符」成立
  · 若表项指向的数据**不像文本**（高熵、位图特征、RLE 标记）
    ⇒ 存在压缩/解压，之前结论作废

判据（逐项检查）：
  A) 表项是否为合法 ROM 指针（0x08xxxxxx）
  B) 指向的串是否符合「原版单字节文本」特征：
     - 以 0xFF 结尾
     - 字节大多落在原版字符集范围
     - 长度合理（1~64）
  C) 若大量表项为 0 或非指针 ⇒ 表未被填充 / 位置不对

用法：python scripts/research/firered/52_analyze_table.py
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "ewram"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
TABLE = 0x0203F2C0


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    dumps = sorted(OUT.glob("d?.f7table.bin"))
    if not dumps:
        print("没有 f7table.bin，先跑 51_dump_ewram.py")
        return 1

    for d in dumps:
        tag = d.name.split(".")[0]          # "d1.f7table.bin" → "d1"
        tbl = d.read_bytes()

        print("=" * 78)
        print(f"{tag}  （{len(tbl)} 字节 = 256 个 u32）")
        print("=" * 78)
        vals = [u32(tbl, i * 4) for i in range(len(tbl) // 4)]

        # ── A) 指针合法性 ──────────────────────────────────────────
        rom_ptr = sum(1 for v in vals if BASE <= v < 0x0A000000)
        rom_shift = sum(1 for v in vals if 0x02000000 <= v < 0x03000000)
        zero = sum(1 for v in vals if v == 0)
        other = len(vals) - rom_ptr - rom_shift - zero
        print(f"  ROM 指针 (0x08xxxxxx): {rom_ptr:>4}")
        print(f"  EWRAM 指针(0x02xxxxxx): {rom_shift:>4}")
        print(f"  0:                     {zero:>4}")
        print(f"  其他:                  {other:>4}")

        print(f"\n  前 16 项：")
        for i in range(16):
            v = vals[i]
            mark = ""
            if BASE <= v < BASE + n:
                e = ja.find(b"\xff", v - BASE, v - BASE + 80)
                if e > 0:
                    content = ja[v - BASE:e]
                    mark = f"  → {content.hex(' ')}  (L={len(content)})"
                else:
                    mark = "  → (无 FF，不像文本)"
            print(f"    [{i:>3}] 0x{v:08X}{mark}")

        # ── B) 指向的内容像不像文本 ────────────────────────────────
        print(f"\n  检查所有 ROM 指针指向的内容：")
        lens = []
        bad = 0
        samples = []
        for i, v in enumerate(vals):
            if not (BASE <= v < BASE + n):
                continue
            off = v - BASE
            e = ja.find(b"\xff", off, off + 80)
            if e < 0:
                bad += 1
                continue
            L = e - off
            lens.append(L)
            if len(samples) < 10:
                samples.append((i, off, L, ja[off:e]))

        if lens:
            a = np.array(lens)
            print(f"    有效串 {len(lens)} 条，无 FF {bad} 条")
            print(f"    长度：均值 {a.mean():.1f} 中位 {np.median(a):.0f} "
                  f"最小 {a.min()} 最大 {a.max()}")
            print(f"    样本：")
            for i, off, L, content in samples:
                print(f"      [{i:>3}] 0x{BASE+off:08X} L={L:<3} "
                      f"{content.hex(' ')}")
        else:
            print("    没有任何合法文本串")
        print()

    # ── C) 与前几次 dump 对比：表是否稳定 ─────────────────────────
    print("=" * 78)
    print("表内容是否随界面变化")
    print("=" * 78)
    prev = None
    for d in dumps:
        tbl = d.read_bytes()
        if prev is None:
            print(f"  {d.stem}: 基准")
        else:
            diff = sum(1 for a, b in zip(prev, tbl) if a != b)
            print(f"  {d.stem}: 与上一帧不同 {diff} 字节")
        prev = tbl
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
