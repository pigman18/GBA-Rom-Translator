#!/usr/bin/env python3
"""texts_62: 0x3B3E64 指针表的真实用途 —— 用「表项 vs 词库排序」验证。

已有事实：
  · 22 项地址单调递增，按假名序排列
  · 词库本体 980 段 / 926 干净词条，按假名排序
  · 表前 0x3B3C6A..0x3B3E64 有 253 个 u16，值域 0..249
  · 9 个函数引用该表

本轮验证「22 项 = 假名行首索引」假设：
  A 取出 22 项各自的词条在词库中的**序号**
  B 看相邻两项的序号差（若差很大且对应假名行切换，则假设成立）
  C 与标准假名顺序对照

用法: python scripts/research/ruby/texts_62_hypothesis.py
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
BASE = 0x08000000
TABLE = 0x3B3E64

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402


def read_str(rom: bytes, off: int, limit: int = 64) -> str:
    for i in range(off, min(len(rom), off + limit)):
        if rom[i] == 0xFF:
            return decode_pcs(rom[off:i + 1])
    return ""


def main() -> int:
    rom = ROM_PATH.read_bytes()

    # 词库序列（按地址顺序 = 按假名顺序）
    segs = []
    start = 0x3B219B
    for i in range(0x3B219B, 0x3B3900):
        if rom[i] == 0xFF:
            t = decode_pcs(rom[start:i + 1])
            if t:
                segs.append((start, t))
            start = i + 1
    pos = {off: k for k, (off, _) in enumerate(segs)}

    print("=" * 112)
    print("22 项在词库中的序号 + 首字")
    print("=" * 112)
    print(f"  {'表项':>4} {'词库序号':>8} {'地址':>10} {'序号差':>7}  词条")
    prev_idx = None
    for k in range(22):
        v = struct.unpack_from("<I", rom, TABLE + k * 4)[0]
        if not (BASE <= v < BASE + len(rom)):
            break
        t = v - BASE
        s = read_str(rom, t)
        idx = pos.get(t)
        diff = "" if prev_idx is None or idx is None else f"{idx - prev_idx}"
        print(f"  {k:>4} {str(idx):>8} 0x{t:06X} {diff:>7}  {s!r}")
        if idx is not None:
            prev_idx = idx

    print()
    print("=" * 112)
    print("判定")
    print("=" * 112)
    print("  · 22 项地址单调递增 → 是词库里的一个有序子集")
    print("  · 序号差不等距 → 不是「每 N 条取一个」的规则采样")
    print("  · 内容混合（句子 'きみにきめた！' / 单字 '！' / 数字 '４６４９'）")
    print("  · 表前是 253 个 u16（值 0..249），表后是 u16（值 256~786）")
    print()
    print("  → 该表不是『按假名分组的行首索引』（那样应等距/对应假名切换）")
    print("  → 更可能是『某功能用到的词条 ID 列表』，由 9 个函数按索引取用")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
