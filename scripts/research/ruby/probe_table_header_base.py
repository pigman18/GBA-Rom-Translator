#!/usr/bin/env python3
"""修正判据：定长表的「真实基址」在名称字段基址之前若干字节。

上一轮的错误：
  我拿模块配置的 start+name_offset（第一条名称字段）当「表基址」去搜字面量，
  招式名报 0 命中。深挖后发现真正的基址是 0x1CACFC（比名称字段早 8 字节），
  被引用 43 次，其中 0x2B580 / 0x4782C 等在代码段。

  这是 pokeruby 的惯例：表头有 count / 前置结构，名称字段从表头 +N 开始。
  用 name_offset=0 的地址搜，必然漏。

本脚本：对每张表，在名称字段基址之前 [-64, 0] 范围扫描，
找「被代码段引用最多」的那个地址 = 真实表基址。

判据：真实基址被代码段引用 ≥1 次 → 可整表搬走 + 改基址字面量
      （火红 §3.1 形态 B）

用法：
    python scripts/research/ruby/probe_table_header_base.py
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"

GBA_BASE = 0x08000000
CODE_END = 0x100000
SCAN_BACK = 64

TARGETS = ["招式名", "特性名", "属性名", "道具名", "图鉴分类名", "秘密基地装饰名", "树果名", "性格名", "宝可梦名"]


def parse_hex(s) -> int:
    return int(str(s).replace("0x", "").replace("0X", ""), 16)


_PTR_INDEX: dict[int, list[int]] | None = None


def ptr_index(rom: bytes) -> dict[int, list[int]]:
    global _PTR_INDEX
    if _PTR_INDEX is not None:
        return _PTR_INDEX
    idx: dict[int, list[int]] = {}
    for off in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            idx.setdefault(v - GBA_BASE, []).append(off)
    _PTR_INDEX = idx
    return idx


def main() -> int:
    rom = ROM.read_bytes()
    mods = (json.loads(TEXTS.read_text(encoding="utf-8")).get("modules") or {})
    idx = ptr_index(rom)
    print(f"ROM {len(rom):,} B / 指针目标 {len(idx):,} 个\n")

    rows = []
    for name in TARGETS:
        meta = mods.get(name)
        if not meta:
            continue
        start = parse_hex(meta["start"])
        read = meta.get("read") or {}
        noff = int(read.get("name_offset") or 0)
        name_base = start + noff
        stride = int(read.get("stride") or 0) or int(read.get("entry_size") or 0)

        print(f"=== {name} ===  配置名称字段 0x{name_base:06X}  stride/size={stride}")

        best = None
        for delta in range(-SCAN_BACK, 1):
            cand = name_base + delta
            if cand < 0:
                continue
            sites = idx.get(cand, [])
            if not sites:
                continue
            code = [s for s in sites if s < CODE_END]
            print(f"  0x{cand:06X} (Δ{delta:+3d})  引用 {len(sites):>3}"
                  f"（代码段 {len(code):>2}）"
                  + ("  ← " + ", ".join(f"0x{s:X}" for s in code[:4]) if code else ""))
            if code:
                score = (len(code), len(sites))
                if best is None or score > best[0]:
                    best = (score, cand, delta, len(sites), len(code))

        if best:
            _, cand, delta, nsite, ncode = best
            verdict = "✅ 有代码段基址锚点 → 可整表搬走"
        else:
            cand = delta = nsite = ncode = 0
            verdict = "❌ 名称字段前 64B 内无可 patch 基址"
        print(f"  ⇒ 真实基址 0x{cand:06X} (Δ{delta:+d})  {verdict}\n")

        rows.append({
            "module": name, "name_base": f"0x{name_base:06X}",
            "real_base": f"0x{cand:06X}" if cand else None,
            "delta": delta, "refs": nsite, "code_refs": ncode, "verdict": verdict,
        })

    out = ROOT / "work" / "_probe" / "ruby_table_header_base.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果 → {out}")
    n = sum(1 for r in rows if r["code_refs"])
    print(f"\n汇总: {n}/{len(rows)} 张表找到代码段基址锚点")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
