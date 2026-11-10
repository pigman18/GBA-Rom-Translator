#!/usr/bin/env python3
"""A0 深查：被「非 4 对齐」挡掉的 2,782 条，指针到底是什么形态。

代码里 policy.py:1087 无条件过滤非对齐指针：
    if ptr_addr & 3: continue
理由是「非对齐的指针源是正文 PCS 里恰好拼成总线地址的假指针」。

但 translate_plan 的注释说：
    「始终 expand（全 ROM 搜 LE 字面量，含脚本 message 非对齐嵌入）」

这两处矛盾。本脚本实测：这些非对齐指针是
  A. 真的脚本指针（如 02 67 <ptr> 形态）
  B. 假指针（正文 PCS 里巧合）

判据：
  A 类：指针前后是脚本 opcode（02/03/04/05），且目标文本确实是日文串
  B 类：指针落在其他文本正文体内

用法：
    python scripts/research/ruby/a0_unaligned.py
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
sys.path.insert(0, str(ROOT / "src"))

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000

# 已知文本区范围（用于判断「目标是否真的是文本」）
def is_text_zone(off: int) -> bool:
    return 0x1C0000 <= off < 0x200000 or 0x370000 <= off < 0x400000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []

    from meowth.policy import collect_entry_text_spans, ptr_site_in_text_body

    text_spans = collect_entry_text_spans(entries)

    f980 = [e for e in entries
            if e.get("type") == "replace" and e.get("phrase_code") is not None]

    idx: dict[int, list[int]] = {}
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            idx.setdefault(v - GBA_BASE, []).append(off)

    # 只看「唯一指针是非对齐」的条目
    prev_byte: Counter = Counter()
    samples = []
    n_unaligned_only = 0

    for e in f980:
        a = e.get("address") or "0x0"
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        sites = idx.get(addr)
        if not sites:
            continue
        aligned = [s for s in sites if not (s & 3)]
        unaligned = [s for s in sites if (s & 3)]
        if aligned or not unaligned:
            continue
        n_unaligned_only += 1
        for s in unaligned[:2]:
            prev = rom[s - 1] if s > 0 else 0
            prev_byte[prev] += 1
            if len(samples) < 15:
                samples.append((e, s, prev))

    print(f"=== 只有非对齐指针的条目: {n_unaligned_only:,} ===\n")

    print("=== 非对齐指针的「前一字节」分布（前 12）===")
    for b, c in prev_byte.most_common(12):
        hint = ""
        if b in (0x02, 0x03, 0x04, 0x05):
            hint = "  ← 疑似脚本 opcode"
        elif b in (0x67, 0x68):
            hint = "  ← 疑似脚本内嵌"
        print(f"  0x{b:02X}: {c}{hint}")
    print()

    print("=== 样本 ===")
    for e, s, prev in samples:
        in_body = ptr_site_in_text_body(s, text_spans)
        ctx = rom[max(0, s - 8):s + 8]
        print(f"  条目 {e.get('module')} {e.get('address')} bl={e.get('byte_length')}")
        print(f"    指针站点 0x{s:X} 前字节 0x{prev:02X}  落在正文体: {in_body}")
        print(f"    上下文: {ctx.hex(' ')}")
        print(f"    原文: {(e.get('original') or '')[:44]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
