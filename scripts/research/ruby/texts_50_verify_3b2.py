#!/usr/bin/env python3
"""texts_50: 验证 Chief 的两个更正（不照抄，自己跑）。

要验的三件事：
  V1 0x3B2000.. 那段到底是不是「起点选错」而不是「串边界打断」
     —— 用不同 lo 扫同一区间末尾，看结果是否一致
  V2 从 0x3B219B 起真能扫出 ~869 条干净词条吗？真实区间到哪结束？
  V3 这 869 条在 ROM 里有没有指针（决定它是否需要翻译）

方法：直接用 scan 的固有语义 —— 从 lo 逐字节跳过 FF/00/F7+ 控制码，
遇到可打印字节起串，读到 PCS 结束。这是 rom 层面的事实，与模块 filter 无关。

用法: python scripts/research/ruby/texts_50_verify_3b2.py
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
LEX = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "lexicon"
BASE = 0x08000000

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs, BYTE_TO_CHAR  # noqa: E402


def read_pcs(rom: bytes, a: int, limit: int = 512) -> bytes | None:
    """从 a 起读一条 FF 结尾的 PCS 串；遇到非法字节返回 None。"""
    i = a
    n = min(len(rom), a + limit)
    while i < n:
        b = rom[i]
        if b == 0xFF:
            return rom[a:i + 1]
        if b == 0xFC:
            i += 2
            continue
        if b == 0xFD:
            i += 2
            continue
        if b in (0xFE, 0xFA, 0xFB):
            i += 1
            continue
        if b >= 0xF7:
            return None
        if b not in BYTE_TO_CHAR:
            return None
        i += 1
    return None


def scan_strings(rom: bytes, lo: int, hi: int) -> list[tuple[int, bytes]]:
    """完全照 extract.py 的推进方式扫串。"""
    out = []
    a = lo
    while a <= hi:
        b = rom[a]
        if b == 0xFF or b == 0x00 or (b >= 0xF7 and b not in (0xFC, 0xFD)):
            a += 1
            continue
        raw = read_pcs(rom, a, 512)
        if raw is None:
            a += 1
            continue
        out.append((a, raw))
        a += len(raw)
    return out


def main() -> int:
    rom = ROM_PATH.read_bytes()

    print("=" * 112)
    print("V1 同一区间末尾、不同起点 lo —— 结果是否一致（验证「起点偏移不影响」）")
    print("=" * 112)
    for lo in (0x3B2000, 0x3B1FF4, 0x3B1FF0, 0x3B1F00):
        got = scan_strings(rom, lo, 0x3B219B - 1)
        first = got[0][0] if got else None
        print(f"  lo=0x{lo:06X} -> {len(got):>3} 条，首条 @"
              f"{hex(first) if first else '-'}  {decode_pcs(got[0][1])[:20] if got else ''!r}")

    print()
    print("=" * 112)
    print("V2 从 0x3B219B 起能扫出多少条，真实区间到哪结束")
    print("=" * 112)
    for lo in (0x3B219B, 0x3B2000):
        got = scan_strings(rom, lo, 0x3B6000)
        print(f"\n  lo=0x{lo:06X}: {len(got)} 条")
        for off, raw in got[:6]:
            print(f"      0x{off:06X} {decode_pcs(raw)!r}")
        print(f"      ...")
        for off, raw in got[-4:]:
            print(f"      0x{off:06X} {decode_pcs(raw)!r}")
        # 用词表命中率判断「干净词条」
        vocab = set()
        for p in LEX.glob("*.json"):
            try:
                dd = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(dd, dict):
                    vocab.update(dd.keys())
            except Exception:
                pass
        hit = sum(1 for _, raw in got if decode_pcs(raw) in vocab)
        print(f"      词表命中 {hit}/{len(got)} ({hit/max(len(got),1):.1%})")

    print()
    print("=" * 112)
    print("V3 该区间条目是否有指针引用")
    print("=" * 112)
    # 建立 ROM 内所有 u32 指针目标集合
    targets: set[int] = set()
    for o in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, o)[0]
        if BASE <= v < BASE + len(rom):
            targets.add(v - BASE)
    got = scan_strings(rom, 0x3B219B, 0x3B6000)
    with_ptr = sum(1 for off, _ in got if off in targets)
    print(f"  0x3B219B 起共 {len(got)} 条，其中有 u32 指针指向的: {with_ptr}")
    print(f"  零指针比例: {(len(got)-with_ptr)/max(len(got),1):.1%}")
    if with_ptr:
        ex = [hex(off) for off, _ in got if off in targets][:8]
        print(f"  有指针的样本: {ex}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
