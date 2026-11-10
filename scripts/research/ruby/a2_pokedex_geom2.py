#!/usr/bin/env python3
"""图鉴分类名：名称字段在条目内的真实偏移。

观察条目 0x38474C 起的 28 字节：
  20 06 08 16 2e 00 | 00 00 00 00 00 00 00 | 7d db 37 08 | 00 00 00 01 | 00 00 00 01
  └─ 名字 'みかくにん'(6B) ─┘  零填充        指针          标志

0x384768: 10 18 00 00 00 00 07 00 45 00 ...
          └'たね'(2B)┘ 零填充

⇒ 名字就在条目 +0x00，后面补 0x00 到某个边界，再放元数据

但 build.json 说条目地址是 0x38474C，而 ROM 里 0x38474C 是 'みかくにん' 的起始 —— 吻合！

所以 name_offset = 0，stride = 28。

但 texts.json 说 name_offset=6，那是把「名字最多 6 字节」误当成了偏移。

验证：
  0x38474C + 7 = 0x384753 → 下一字节应是 0x00 填充
  0x384768 + 3 = 0x38476B → 'たね' 之后

用法：
    python scripts/research/ruby/a2_pokedex_geom2.py
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000

BASE = 0x38474C
STRIDE = 28
N = 386


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    items = {}
    for e in d.get("entries") or []:
        if e.get("module") != "图鉴分类名":
            continue
        try:
            a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
        except ValueError:
            continue
        if a >= GBA_BASE:
            a -= GBA_BASE
        items[a] = e

    print("=== 验证 name_offset=0 ===")
    print("条目号 地址      原文          名字长度 ROM 前 12B")
    ok = 0
    for i in range(10):
        off = BASE + i * STRIDE
        e = items.get(off)
        seg = rom[off:off + 12]
        ff = seg.find(b"\xFF")
        # 名字长度 = 第一个 FF 或第一个 0x00
        z = seg.find(b"\x00")
        name_len = min(x for x in (ff, z if z >= 0 else 99) if x >= 0)
        orig = (e.get("original") or "") if e else ""
        match = "✅" if e and len(orig) == name_len else "⚠️"
        if e and len(orig) == name_len:
            ok += 1
        print(f"  {i:>3}  0x{off:06X}  {orig[:12]!r:<16} {name_len:>2}  "
              f"{seg.hex(' ')}  {match}")
    print(f"  前 10 项吻合 {ok}/10")
    print()

    # 全量校验
    print("=== 全量：名字长度 == build.json original 长度 ===")
    full_ok = 0
    bad = []
    for i in range(N):
        off = BASE + i * STRIDE
        e = items.get(off)
        if not e:
            continue
        orig = e.get("original") or ""
        try:
            raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        # ROM 里这段是否就是 raw
        if rom[off:off + len(raw)] == raw:
            full_ok += 1
        elif len(bad) < 5:
            bad.append((i, off, orig, len(raw)))
    print(f"  ROM 字节与 original_hex 完全一致: {full_ok}/{N}")
    for i, off, orig, n in bad:
        print(f"    item{i} 0x{off:06X} {orig!r} ({n}B)")

    print()
    print("=== 结论 ===")
    if full_ok >= N * 0.95:
        print(f"✅ name_offset=0, stride={STRIDE} 正确")
        print(f"   名字可用宽度 = {STRIDE} 字节（整项）")
        print(f"   但实际元数据也从 +N 开始，需确认名字最大长度")
        # 统计原文最长
        lens = [len(bytes.fromhex((e.get('original_hex') or '').replace(' ', '')))
                for e in items.values() if e.get('original_hex')]
        if lens:
            print(f"   原文最长 {max(lens)}B")
    else:
        print("❌ 仍有不一致，需进一步查")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
