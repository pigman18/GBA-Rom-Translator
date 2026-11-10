#!/usr/bin/env python3
"""A1.4 定案：919 条的最终结论 + 对 texts.json 的处置建议。

已查清的所有事实：
  ✅ 任意对齐（含非对齐）的 u32 指针：0 命中
  ✅ 合并成 381 个连续块，块首 0/381 有引用
  ✅ u16 偏移假设不成立（最高 16.6%）
  ✅ 符号表无这些地址
  ✅ 内容与「有引用文本」重复的只有 77 条（8.4%，真死数据）
  ✅ 内容都是正常剧情文本（ダイゴ『...、ミクリ『...、商店对话）

结论：这 842 条（919 - 77）走的是「基址+偏移 / 脚本 VM 相对地址」，
      指针不可见，无法靠「改指针」搬走。

对 texts.json 的处置：
  这些条目**在现有方案下无法 relocate**，只能：
    A. 原地 F900 写入（若塞得下）
    B. 缩句
    C. 保留日文（keep）

本脚本输出最终的分类清单，供清洗 texts.json 使用。

用法：
    python scripts/research/ruby/a1_final_verdict.py
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
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
OWN = ROOT / "work" / "_probe" / "a1_ownership.json"
OUT = ROOT / "work" / "_probe" / "a1_zero_ref_919.json"
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []

    addr_to_entry = {}
    for e in entries:
        a = e.get("address") or ""
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        addr_to_entry[addr] = e

    own = json.loads(OWN.read_text(encoding="utf-8"))
    targets = {int(r["addr"].replace("0x", ""), 16) for r in (own.get("NO_PTR") or [])}

    ref_targets: set[int] = set()
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            ref_targets.add(v - GBA_BASE)

    zero = sorted(t for t in targets if t not in ref_targets and t > 0 and rom[t-1] == 0xFF)

    # 建「有引用文本」的内容集合
    ref_contents: set[bytes] = set()
    for a in ref_targets:
        e = addr_to_entry.get(a)
        if not e:
            continue
        try:
            raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        if len(raw) >= 4:
            ref_contents.add(raw)

    rows = []
    dead = 0     # 有重复且另一份有引用 → 死数据
    live = 0     # 内容唯一 → 靠基址+偏移访问

    for a in zero:
        e = addr_to_entry.get(a)
        if not e:
            continue
        try:
            raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        is_dup_dead = raw in ref_contents
        if is_dup_dead:
            dead += 1
            verdict = "DEAD_DUPLICATE"
        else:
            live += 1
            verdict = "BASEPTR_ACCESS"

        rows.append({
            "id": e.get("id"),
            "module": e.get("module"),
            "addr": f"0x{a:06X}",
            "byte_length": e.get("byte_length"),
            "original": (e.get("original") or "")[:60],
            "translated": (e.get("translated") or "")[:60],
            "verdict": verdict,
        })

    print("=== 919 条零引用文本的最终定性 ===")
    print(f"  DEAD_DUPLICATE（内容与有引用文本相同，真死数据）: {dead:,}")
    print(f"  BASEPTR_ACCESS（内容唯一，靠基址+偏移访问）:     {live:,}")
    print()

    # 按模块
    print("=== 按模块 ===")
    mods = Counter(r["module"] for r in rows)
    for m, c in mods.most_common():
        print(f"  {m:<18} {c:>5}")

    # 保存
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n清单 → {OUT}")

    # 处置建议
    print()
    print("=== 对 texts.json 的处置建议 ===")
    print(f"  1. DEAD_DUPLICATE {dead} 条 → 可直接从 texts.json 删除（不影响游戏）")
    print(f"  2. BASEPTR_ACCESS {live} 条 → 无法 relocate，只能原地写/缩句/keep")
    print()
    print("  注意：BASEPTR_ACCESS 不是「无效文本」，它们是正常剧情对话，")
    print("  只是指针不可见。删掉会导致这段剧情不翻译。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
