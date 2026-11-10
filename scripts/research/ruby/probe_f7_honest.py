#!/usr/bin/env python3
"""诚实的 0xF7 占用分析——基于真实抽取的文本，不用「F7 是控制码」当判据。

⚠️ 之前 probe_f7_final2.py 的方法有致命缺陷：
   它把 >= 0xF5 的字节当作「控制码」用来切分文本串，
   而 0xF7 本身就 >= 0xF5，所以永远不可能出现在「串体内」。
   「文本区 0xF7 = 0」是循环论证的必然结果，不能作为证据。

本脚本改用真正的事实来源：translate.build.json 里 12,697 条已抽取文本的
original_hex —— 那是 extract 从 ROM 里真实读出的文本字节流。

判据：
  若 original_hex 里出现 f7 → 0xF7 在原版文本里是真实使用的（表情码），
  不能安全地独占为中文前缀。

另外核对 pcs_codes.py 里 0xF7 = [angry] 的说法。

用法：
    python scripts/research/ruby/probe_f7_honest.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
OUT = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"


def main() -> int:
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []
    print(f"条目 {len(entries):,}\n")

    # 1. original_hex 里的 0xF7
    n_with_f7 = 0
    f7_total = 0
    samples = []
    byte_freq: Counter = Counter()

    for e in entries:
        oh = (e.get("original_hex") or "").replace(" ", "").lower()
        if not oh:
            continue
        try:
            raw = bytes.fromhex(oh)
        except ValueError:
            continue
        for b in raw:
            byte_freq[b] += 1
        if 0xF7 in raw:
            c = raw.count(0xF7)
            n_with_f7 += 1
            f7_total += c
            if len(samples) < 8:
                samples.append((e.get("module"), e.get("address"),
                                e.get("original"), oh))

    print("=== 真实抽取的文本里 0xF7 的出现 ===")
    print(f"  含 0xF7 的条目: {n_with_f7:,} / {len(entries):,}")
    print(f"  0xF7 总次数:    {f7_total:,}")
    if samples:
        print("  样本:")
        for mod, addr, orig, oh in samples:
            print(f"    {mod} {addr}")
            print(f"      original: {orig!r}")
            print(f"      hex: {oh}")
    print()

    # 2. 高位字节频率（看哪些 >=0xF5 的字节真出现在文本里）
    print("=== 抽取文本里 0xF0..0xFF 各字节频率 ===")
    for b in range(0xF0, 0x100):
        c = byte_freq.get(b, 0)
        mark = ""
        if b == 0xF7:
            mark = "  ← 待确认是否可占用"
        print(f"  0x{b:02X}: {c:>8,}{mark}")
    print()

    # 3. 产物里 0xF7 是否已被我们的编码使用（若已用，说明现有 hook 能处理）
    if OUT.is_file():
        out = OUT.read_bytes()
        print("=== 产物 ROM 里的 0xF7 ===")
        print(f"  总次数: {out.count(b'\xF7'):,}")
        print("  （对比原版 34,311；若显著增加说明已有编码在用 F7）")

    print()
    print("=== 结论判据 ===")
    if n_with_f7 == 0:
        print("  ✅ 已抽取的真实文本里 0xF7 = 0 → 0xF7 未被文本使用，可考虑占用")
        print("     （但仍需注意：原版可能有不走 extract 的界面用了 [angry] 表情）")
    else:
        print(f"  ❌ 有 {n_with_f7} 条真实文本含 0xF7 → 它是 [angry] 表情码，")
        print("     直接占用会破坏这些文本，需要保留旧通道或改用别的字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
