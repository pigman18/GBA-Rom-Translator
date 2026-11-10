#!/usr/bin/env python3
"""最终判据：0xF7 作为中文前缀是否安全。

前面发现：
  - 四张已确认名称表里 0xF7 = 0 ✅
  - 数据区高密度区（0x100000~0x150000）是 Thumb bl 指令的误命中
    典型形态：`ff f7 xx fe` / `b6 f7 42 fb` —— bl 的第二个半字

本脚本用「真文本流」判据验证：
  真正的文本串 = 连续字节里不含 FF/FE/FD 等控制码，且以 FF 结尾
  统计这种串内部出现 0xF7 的比例

另外验证关键前提：现有 charmap 里 0x01 0xF7 的「全角空格」是否真的在产物里用到。

用法：
    python scripts/research/ruby/probe_f7_final.py
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ORIG = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
OUT = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"

# 文本串判据：可打印字节范围（排除控制码）
CTRL = set(range(0xF5, 0x100)) | {0xFE, 0xFD, 0xFC, 0xFB, 0xFA}


def scan_text_streams(rom: bytes, lo: int, hi: int):
    """扫「无控制码 + FF 结尾」的串，返回 (串数, 含 F7 的串数, F7 总数)。"""
    n_stream = 0
    n_with_f7 = 0
    n_f7 = 0
    i = lo
    while i < hi:
        j = i
        while j < hi and rom[j] not in CTRL:
            j += 1
        if j < hi and rom[j] == 0xFF and 3 <= (j - i) <= 200:
            body = rom[i:j]
            n_stream += 1
            c = body.count(0xF7)
            if c:
                n_with_f7 += 1
                n_f7 += c
            i = j + 1
        else:
            i += 1
    return n_stream, n_with_f7, n_f7


def main() -> int:
    rom = ORIG.read_bytes()
    print(f"ROM {len(rom):,} B\n")

    print("=== 真文本流里的 0xF7（排除代码/图形）===")
    for label, lo, hi in (
        ("整个数据区", 0x100000, 0x400000),
        ("名称表区",   0x1CA000, 0x1CC000),
        ("剧情文本区", 0x1C0000, 0x1D0000),
        ("后半 ROM",   0x400000, len(rom)),
    ):
        ns, nf, cnt = scan_text_streams(rom, lo, hi)
        pct = nf / ns if ns else 0
        print(f"  {label:<12} 0x{lo:06X}..0x{hi:06X}  "
              f"文本串 {ns:>6}  含F7串 {nf:>5} ({pct:.2%})  F7 共 {cnt}")

    print("\n=== 产物里 0x01 0xF7（全角空格）是否在用 ===")
    if OUT.is_file():
        out = OUT.read_bytes()
        print(f"  0x01 0xF7 出现: {out.count(b'\x01\xF7')}")
    if BUILD.is_file():
        import json
        d = json.loads(BUILD.read_text(encoding="utf-8"))
        n_ph = sum(1 for e in d.get("entries") or []
                   if "01f7" in (e.get("target_hex") or "").replace(" ", ""))
        print(f"  build.json 里含 01f7 的条目: {n_ph}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
