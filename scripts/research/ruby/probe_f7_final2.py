#!/usr/bin/env python3
"""0xF7 安全性最终判据（快速版，只扫关键区）。

慢的原因：Python 逐字节扫 8MB 数据区。
改为只扫「已知会走文本打印」的区域 + 全局快速统计。

用法：
    python scripts/research/ruby/probe_f7_final2.py
"""
from __future__ import annotations

import json
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

# 关键文本区（小范围，快速）
ZONES = [
    ("名称表区",   0x1CA000, 0x1CC000),
    ("剧情文本区", 0x1C0000, 0x1D0000),
    ("UI 文本区",  0x1D0000, 0x1E0000),
]

CTRL_HI = 0xF5  # >=0xF5 视为控制/不可印


def scan(rom: bytes, lo: int, hi: int):
    ns = nf = cnt = 0
    i = lo
    while i < hi:
        j = i
        while j < hi and rom[j] < CTRL_HI:
            j += 1
        if j < hi and rom[j] == 0xFF and 3 <= (j - i) <= 200:
            body = rom[i:j]
            ns += 1
            c = body.count(0xF7)
            if c:
                nf += 1
                cnt += c
            i = j + 1
        else:
            i += 1
    return ns, nf, cnt


def main() -> int:
    rom = ORIG.read_bytes()
    print(f"ROM {len(rom):,} B\n")

    print("=== 关键文本区的 0xF7 ===")
    for label, lo, hi in ZONES:
        ns, nf, cnt = scan(rom, lo, hi)
        pct = nf / ns if ns else 0
        flag = "✅ 干净" if nf == 0 else "⚠️ 有 F7"
        print(f"  {label:<10} 0x{lo:06X}..0x{hi:06X}  串 {ns:>5}  "
              f"含F7 {nf:>4} ({pct:.2%})  {flag}")

    print("\n=== 全 ROM 快速统计（不做串解析）===")
    # 用分块 count 加速
    total = 0
    for base in range(0, len(rom), 0x100000):
        chunk = rom[base:base + 0x100000]
        c = chunk.count(b"\xF7")
        total += c
        if c:
            print(f"  0x{base:06X}..0x{base+0xFFFFF:06X}  0xF7 × {c:,}")
    print(f"  合计 {total:,}")

    print("\n=== 0x01 0xF7（全角空格）用量 ===")
    if BUILD.is_file():
        d = json.loads(BUILD.read_text(encoding="utf-8"))
        hits = [e for e in (d.get("entries") or [])
                if "01f7" in (e.get("target_hex") or "").replace(" ", "").lower()]
        print(f"  build.json 含 01f7 的条目: {len(hits)}")
        for e in hits[:3]:
            print(f"    {e.get('module')} {e.get('address')}: {e.get('target_hex')[:60]}")
    if OUT.is_file():
        out = OUT.read_bytes()
        print(f"  产物里 01 F7 出现: {out.count(b'\x01\xF7')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
