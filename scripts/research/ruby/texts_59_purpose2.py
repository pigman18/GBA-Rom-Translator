#!/usr/bin/env python3
"""texts_59: 判定 0x3B3E64 指针表的用途 —— 9 个函数都在用什么。

事实：
  · 表 @0x3B3E64，22 项，全是指向词库的指针
  · 9 个不同函数用 ldr 字面量加载 0x083B3E64（0xE6058 等，字面量池里确实是该地址）
  · 9 个函数都在 0xE6000..0xE6E00 这一片，符号名都是 sub_80E9xxx / sub_80EAxxx

要回答：
  C1 这 9 个函数是不是「同一类功能」？（比如都是某个菜单的渲染）
  C2 22 项内容是什么语义？
  C3 800+ 条无指针词条该怎么处理？

方法：反汇编那 9 个函数入口，看它们对表做什么（取第几项、怎么用）。
在没有反汇编器的前提下，用字面量池 + 调用关系做结构性判断。

用法: python scripts/research/ruby/texts_59_purpose2.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
SYM = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "symbols" / "pokeruby_jp.sym"
BASE = 0x08000000

REFS = [0xE6058, 0xE61C4, 0xE62F4, 0xE63F8, 0xE66EC,
        0xE67BC, 0xE68D4, 0xE6A50, 0xE6D24]
TABLE = 0x3B3E64


def load_syms() -> list[tuple[int, str]]:
    out = []
    if not SYM.exists():
        return out
    for line in SYM.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            a = int(parts[0], 16)
        except ValueError:
            continue
        name = parts[2]
        out.append((a - BASE if a >= BASE else a, name))
    out.sort()
    return out


def thumb_bl_target(rom: bytes, addr: int) -> int | None:
    """addr 处的 32-bit Thumb BL/BLX，返回目标。"""
    if addr + 4 > len(rom):
        return None
    w1, w2 = struct.unpack_from("<HH", rom, addr)
    if (w1 & 0xF800) != 0xF000 or (w2 & 0xF800) != 0xF800:
        return None
    s = (w1 >> 10) & 1
    i1 = 1 - (((w2 >> 13) & 1) ^ s)
    i2 = 1 - (((w2 >> 11) & 1) ^ s)
    imm = (s << 24) | (i1 << 23) | (i2 << 22) | ((w1 & 0x3FF) << 12) | ((w2 & 0x7FF) << 1)
    if imm & (1 << 24):
        imm -= 1 << 25
    return addr + 4 + imm


def main() -> int:
    rom = ROM_PATH.read_bytes()
    syms = load_syms()

    def sym_at(a: int) -> str | None:
        prev = None
        for s, n in syms:
            if s <= a:
                prev = (s, n)
            else:
                break
        return prev[1] if prev else None

    print("=" * 112)
    print("A. 9 个引用点所属函数、以及它们的调用者")
    print("=" * 112)
    # 建立 BL 调用图
    callers: dict[int, list[int]] = {}
    for a in range(0, len(rom) - 4, 2):
        t = thumb_bl_target(rom, a)
        if t is not None and 0 <= t < len(rom):
            callers.setdefault(t, []).append(a)
    # 每个符号函数入口的调用者
    funcs = [f for a, f in syms if 0xE6000 <= a < 0xE7000][:200]
    for r in REFS:
        fn = sym_at(r)
        # 找该函数入口
        entry = None
        for a, n in syms:
            if a <= r and n == fn:
                entry = a
                break
        cs = callers.get(entry, []) if entry else []
        cnames = sorted({sym_at(c) or f"0x{c:X}" for c in cs})
        print(f"  字面量 0x{r:06X} 函数 {fn} (0x{entry:06X})  "
              f"调用者 {len(cs)} 个: {cnames[:4]}")

    print()
    print("=" * 112)
    print("B. 表 22 项内容（重新逐项看，含空项）")
    print("=" * 112)
    sys.path.insert(0, str(ROOT / "src"))
    from meowth.jp_pcs import decode_pcs

    for k in range(22):
        v = struct.unpack_from("<I", rom, TABLE + k * 4)[0]
        if not (BASE <= v < BASE + len(rom)):
            print(f"  [{k:>2}] 0x{v:08X}  非指针（表尾）")
            continue
        t = v - BASE
        s = ""
        for i in range(t, min(len(rom), t + 64)):
            if rom[i] == 0xFF:
                s = decode_pcs(rom[t:i + 1])
                break
        print(f"  [{k:>2}] -> 0x{t:06X}  {s!r}")

    print()
    print("=" * 112)
    print("C. 关键判断：22 项 vs 800+ 条")
    print("=" * 112)
    print("  · 表只有 22 项，指向词库里 22 个点")
    print("  · 词库本体 926 条（≥Chief 的 847）")
    print("  · 说明：表是「按需引用」的索引，不是词库全量的枚举")
    print()
    print("  22 项的内容特征：")
    print("    [1] きみにきめた！  [2] あく  [3] あいしょう  [4] ありがとう")
    print("    [12] アルバイト  [13] アイドル  [16] うろうろ  [17] アピール")
    print("  → 大部分是「あ行 / ア行」开头的词，且是**玩家可选的称呼/性格/台词片段**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
