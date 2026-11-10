#!/usr/bin/env python3
"""A1 归属分析：把 F980 条目按「属于哪个容器」分类。

原则（用户指示）：先定句子归属，再决定写法。等长/等距整块必然整块处理。

容器类型（按判定优先级）：
  1. CODE_LITERAL   代码字面量池 —— 站点在代码段且被 ldr [pc] 加载
  2. PTR_ARRAY      指针数组元素 —— 站点前后 4 字节也是指针（成组）
  3. FIXED_TABLE    定长表元素 —— 落在已知 stride 表范围内
  4. STRUCT_FIELD   结构体字段 —— 落在已知 struct 范围内
  5. SCRIPT_INLINE  脚本内嵌 —— 站点前有脚本 opcode
  6. FREE_TEXT      真自由文本 —— 以上都不是
  7. NO_PTR         完全无指针

输出：work/_probe/a1_ownership.json + 控制台汇总

用法：
    python scripts/research/ruby/a1_ownership.py
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter, defaultdict
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
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
OUT = ROOT / "work" / "_probe" / "a1_ownership.json"

GBA_BASE = 0x08000000
CODE_END = 0x100000     # 代码段上界（保守）

# 已实测确认的定长表（基址, stride, 名称字段偏移, 元素数）
KNOWN_TABLES = {
    "招式名":         (0x1CACFC, 8,  0, 354),
    "特性名":         (0x1CBC44, 8,  0, 77),
    "属性名":         (0x1CBB0C, 5,  0, 18),
    "宝可梦名":       (0x1CA354, 6,  0, 412),
    "道具名":         (0x39A648, 40, 0x18, 348),
    "图鉴分类名":     (0x38474C, 28, 6, 386),
    "秘密基地装饰名": (0x3C2A44, 28, 13, 120),
    "树果名":         (0x3A1034, 56, 0, 21),
}


def parse_hex(s) -> int:
    return int(str(s).replace("0x", "").replace("0X", ""), 16)


def find_ldr_refs(rom: bytes, lit: int, back: int = 4096) -> list[int]:
    """找引用该字面量的 thumb ldr [pc, #imm]。"""
    hits = []
    for off in range(max(0, lit - back), lit, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit:
            hits.append(off)
    return hits


def is_ptr(rom: bytes, off: int) -> bool:
    if off < 0 or off + 4 > len(rom):
        return False
    v = struct.unpack_from("<I", rom, off)[0]
    return GBA_BASE <= v < 0x0A000000


def in_known_table(addr: int) -> str | None:
    """该地址是否落在已知定长表范围内。"""
    for name, (base, stride, noff, n) in KNOWN_TABLES.items():
        lo = base
        hi = base + stride * n
        if lo <= addr < hi:
            return name
    return None


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []

    from meowth.policy import collect_entry_text_spans, ptr_site_in_text_body
    text_spans = collect_entry_text_spans(entries)

    f980 = [e for e in entries
            if e.get("type") == "replace" and e.get("phrase_code") is not None]
    print(f"待归类 F980 条目: {len(f980):,}\n")

    # 全 ROM 指针索引（4 对齐）
    idx: dict[int, list[int]] = {}
    for off in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            idx.setdefault(v - GBA_BASE, []).append(off)

    print("归类中…")
    result: dict[str, list[dict]] = defaultdict(list)
    per_mod: dict[str, Counter] = defaultdict(Counter)

    for e in f980:
        addr_s = e.get("address") or "0x0"
        try:
            addr = parse_hex(addr_s)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        mod = e.get("module") or ""
        eid = e.get("id") or addr_s

        # 先看是否落在已知定长表（这是最强的归属信号）
        tbl = in_known_table(addr)
        if tbl:
            result["FIXED_TABLE"].append({
                "id": eid, "module": mod, "addr": f"0x{addr:06X}",
                "container": tbl, "table_base": f"0x{KNOWN_TABLES[tbl][0]:06X}",
                "stride": KNOWN_TABLES[tbl][1],
            })
            per_mod[mod]["FIXED_TABLE"] += 1
            continue

        sites = idx.get(addr) or []
        aligned = [s for s in sites if not (s & 3)]
        usable = [s for s in aligned if not ptr_site_in_text_body(s, text_spans)]

        if not usable:
            # 无可用对齐指针
            if aligned:
                result["NO_PTR_BLOCKED"].append({
                    "id": eid, "module": mod, "addr": f"0x{addr:06X}",
                    "sites": [f"0x{s:X}" for s in aligned[:4]],
                    "why": "全被 filter 挡（落正文体）",
                })
                per_mod[mod]["NO_PTR_BLOCKED"] += 1
            else:
                result["NO_PTR"].append({
                    "id": eid, "module": mod, "addr": f"0x{addr:06X}",
                    "unaligned": len(sites),
                })
                per_mod[mod]["NO_PTR"] += 1
            continue

        # 有可用对齐指针：进一步判容器
        s0 = usable[0]
        ldrs = find_ldr_refs(rom, s0)
        in_code = s0 < CODE_END
        grouped = is_ptr(rom, s0 - 4) or is_ptr(rom, s0 + 4)

        if in_code and ldrs:
            result["CODE_LITERAL"].append({
                "id": eid, "module": mod, "addr": f"0x{addr:06X}",
                "site": f"0x{s0:X}", "ldr": f"0x{ldrs[0]:X}",
            })
            per_mod[mod]["CODE_LITERAL"] += 1
        elif grouped:
            result["PTR_ARRAY"].append({
                "id": eid, "module": mod, "addr": f"0x{addr:06X}",
                "site": f"0x{s0:X}",
                "prev_ptr": is_ptr(rom, s0 - 4),
                "next_ptr": is_ptr(rom, s0 + 4),
            })
            per_mod[mod]["PTR_ARRAY"] += 1
        else:
            result["CODE_LITERAL" if (in_code and ldrs) else "FREE_TEXT"].append({
                "id": eid, "module": mod, "addr": f"0x{addr:06X}",
                "site": f"0x{s0:X}", "in_code": in_code, "has_ldr": bool(ldrs),
            })
            per_mod[mod]["FREE_TEXT" if not (in_code and ldrs) else "CODE_LITERAL"] += 1

    # 汇总
    print("\n=== 归属汇总 ===")
    total = 0
    for k in ("FIXED_TABLE", "PTR_ARRAY", "CODE_LITERAL", "FREE_TEXT",
              "NO_PTR_BLOCKED", "NO_PTR"):
        n = len(result.get(k) or [])
        total += n
        print(f"  {k:<16} {n:>6}  ({n/max(len(f980),1):.1%})")
    print(f"  {'合计':<16} {total:>6}")

    print("\n=== 按模块 × 容器 ===")
    print(f"  {'模块':<18} " + " ".join(f"{k:>12}" for k in
          ("FIXED_TABLE", "PTR_ARRAY", "CODE_LITERAL", "FREE_TEXT", "NO_PTR")))
    for mod in sorted(per_mod, key=lambda m: -sum(per_mod[m].values())):
        c = per_mod[mod]
        print(f"  {mod:<18} " + " ".join(
            f"{c.get(k, 0):>12}" for k in
            ("FIXED_TABLE", "PTR_ARRAY", "CODE_LITERAL", "FREE_TEXT", "NO_PTR")))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {k: v for k, v in result.items()},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
