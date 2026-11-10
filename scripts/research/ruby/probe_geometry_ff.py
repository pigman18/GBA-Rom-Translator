#!/usr/bin/env python3
"""修正判据：ruby 定长名称表用 FF 填充（不是 00），重新验算几何。

上一支脚本的错误：
  判据是「首个 FF 之后全是 0x00」→ 招式名合规 26%，误判 texts.json 地址错。
  实际 ruby 用 FF 填充：
    0x1CAD04: 1a 10 08 ff ff ff ff ff   ← 3B 文本 + 5×FF，正好 stride 8
    0x1CAD0C: 06 27 13 61 86 a0 9d ff   ← 7B 文本 + 1×FF，正好 stride 8

本脚本用正确判据复验，并计算「F900 vs F7 编码能否塞进各 stride」。

用法：
    python scripts/research/ruby/probe_geometry_ff.py
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
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

# 地址均已在 ROM 字节级确认过首条文本
TABLES = [
    ("招式名", 0x1CAD04, 354, 8),
    ("特性名", 0x1CBC4C, 77, 8),
    ("属性名", 0x1CBB0C, 18, 5),
    ("宝可梦名", 0x1CA354, 412, 6),
]


def compliance_ff(rom: bytes, base: int, stride: int, n: int) -> tuple[float, int]:
    """合规 = 项内文本不含 FF，且首个 FF 之后全为 FF（FF 填充）。"""
    ok = total = 0
    for i in range(n):
        off = base + i * stride
        if off + stride > len(rom):
            break
        seg = rom[off:off + stride]
        total += 1
        ff = seg.find(0xFF)
        if ff < 0:
            continue
        if all(b == 0xFF for b in seg[ff + 1:]):
            ok += 1
    return (ok / total if total else 0.0), total


def main() -> int:
    rom = ROM.read_bytes()
    print(f"ROM {len(rom):,} B\n")

    print("=== 正确判据（FF 填充）下的 stride 打分 ===")
    for name, base, n, cfg_stride in TABLES:
        best = []
        for s in range(4, 17):
            r, total = compliance_ff(rom, base, s, min(n, 120))
            best.append((r, s))
        best.sort(reverse=True)
        top = best[0]
        flag = "✅ 与配置一致" if top[1] == cfg_stride and top[0] > 0.95 else "⚠️ 不一致"
        print(f"  {name:<8} 配置 stride={cfg_stride}  实测最佳 stride={top[1]} "
              f"合规 {top[0]:.0%}   {flag}")
        if len(best) > 1:
            print(f"           次佳: stride={best[1][1]} 合规 {best[1][0]:.0%}")
    print()

    print("=== 编码长度能否塞进各 stride ===")
    print("  编码格式：F900 hi lo = 4B/字；F7 hi lo = 3B/字；结尾 FF = 1B")
    print()
    for name, base, n, stride in TABLES:
        print(f"  {name}  stride={stride}")
        for label, per in (("F900", 4), ("F7", 3)):
            row = []
            for chars in (1, 2, 3):
                need = per * chars + 1
                ok = "✓" if need <= stride else "✗"
                row.append(f"{chars}字={need}B{ok}")
            print(f"    {label}: " + "  ".join(row))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
