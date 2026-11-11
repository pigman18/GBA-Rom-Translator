#!/usr/bin/env python3
"""判据：ruby 的定长名称表是「指针表」还是「基址+偏移结构体」？

决定方向 1 第 1 条能否成立：
  - 指针表   → 每个元素有独立指针，可逐元素 relocate（火红 10/68 块的情况）
  - 基址+偏移 → 结构体内嵌字段，改不了指针（火红 58/68 块的情况）

用法：
    python scripts/research/ruby/probe_fixed_table_access.py

对每张表输出：
  表类型      stride / struct
  表范围      起止
  元素数
  元素首地址是否被 u32 指针引用       ← 指针表的核心判据
  表内是否存在 u32 值落在本表范围内    ← 元素间互相引用（罕见）
  结论        POINTER_TABLE / INLINE_STRUCT / MIXED
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

# Windows 控制台默认 GBK，输出含中文/符号会炸；统一转 UTF-8
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
SYM = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "symbols" / "pokeruby_jp.sym"

GBA_BASE = 0x08000000

# 要探测的定长表模块（历史背景见 git 里的 RUBY_ENCODING_CURRENT.md，已删）
TARGETS = [
    "招式名",
    "道具名",
    "图鉴分类名",
    "秘密基地装饰名",
    "属性名",
    "特性名",
    "树果名",
    "性格名",
]


def load_rom() -> bytes:
    if not ROM.is_file():
        sys.exit(f"ROM not found: {ROM}")
    return ROM.read_bytes()


def build_pointer_index(rom: bytes) -> dict[int, int]:
    """扫全 ROM 的 4 字节对齐 u32，建立「目标地址 → 引用次数」。

    只收 GBA 指针空间（0x08xxxxxx / 0x09xxxxxx），与 rom_writer 的指针判据一致。
    """
    idx: dict[int, int] = {}
    n = len(rom) - 4
    for off in range(0, n, 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            idx[v] = idx.get(v, 0) + 1
    return idx


def parse_hex(s) -> int:
    return int(str(s).replace("0x", "").replace("0X", ""), 16)


def element_offsets(meta: dict) -> tuple[list[int], str]:
    """按模块 type 算出每个元素的「名称字段」文件偏移。"""
    start = parse_hex(meta["start"])
    end = parse_hex(meta["end"])
    read = meta.get("read") or {}
    typ = str(meta.get("type") or "")
    outs: list[int] = []

    if typ in ("stride", "stride_ptr", "ptr_stride"):
        stride = int(read.get("stride") or 0)
        if stride <= 0:
            return [], typ
        off = start
        while off < end:
            outs.append(off)
            off += stride
        return outs, typ

    if typ in ("struct", "fixed_table", "struct_table"):
        size = int(read.get("entry_size") or 0)
        noff = int(read.get("name_offset") or 0)
        if size <= 0:
            return [], typ
        off = start
        while off < end:
            e = off + noff
            if e < end:
                outs.append(e)
            off += size
        return outs, typ

    return [], typ


def main() -> int:
    rom = load_rom()
    texts = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = texts.get("modules") or {}
    print(f"ROM: {ROM.name}  {len(rom):,} B")
    print("建立全 ROM 指针索引 …")
    ptr = build_pointer_index(rom)
    print(f"  指针条目 {len(ptr):,}\n")

    rows = []
    for name in TARGETS:
        meta = mods.get(name)
        if not meta:
            print(f"[skip] {name}: 模块不存在")
            continue
        elems, typ = element_offsets(meta)
        if not elems:
            print(f"[skip] {name}: 无法解析几何 (type={typ})")
            continue

        hit = [e for e in elems if (e + GBA_BASE) in ptr]
        hit_n = sum(ptr.get(e + GBA_BASE, 0) for e in elems)

        # 表内是否有 u32 落在本表范围内（元素间互引）
        start = parse_hex(meta["start"])
        end = parse_hex(meta["end"])
        intra = 0
        for off in range(start, min(end, len(rom)) - 4, 4):
            v = struct.unpack_from("<I", rom, off)[0] - GBA_BASE
            if start <= v < end:
                intra += 1

        ratio = len(hit) / len(elems) if elems else 0.0
        if ratio >= 0.9:
            verdict = "POINTER_TABLE  → 可逐元素 relocate"
        elif ratio <= 0.1:
            verdict = "INLINE_STRUCT  → 只能整块搬或原地"
        else:
            verdict = "MIXED          → 需逐表判断"

        rows.append({
            "module": name,
            "type": typ,
            "start": f"0x{start:06X}",
            "end": f"0x{end:06X}",
            "elems": len(elems),
            "ptr_elems": len(hit),
            "ratio": ratio,
            "ptr_refs": hit_n,
            "intra": intra,
            "verdict": verdict,
        })

        print(f"=== {name} ===")
        print(f"  type={typ}  范围 0x{start:06X}..0x{end:06X}  元素 {len(elems)}")
        print(f"  元素首被指针引用: {len(hit)}/{len(elems)} ({ratio:.1%})，引用总次数 {hit_n}")
        print(f"  表内 u32 落本表范围: {intra}")
        print(f"  ⇒ {verdict}")
        if hit[:5]:
            print(f"  样本（前 5 个被引用的元素偏移）: "
                  + ", ".join(f"0x{e:06X}" for e in hit[:5]))
        print()

    out = ROOT / "work" / "_probe" / "ruby_fixed_table_access.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"rom": ROM.name, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"结果 → {out}")

    n_ptr = sum(1 for r in rows if r["ratio"] >= 0.9)
    n_inline = sum(1 for r in rows if r["ratio"] <= 0.1)
    print(f"\n汇总: 指针表 {n_ptr} 张 / 内联结构 {n_inline} 张 / 混合 {len(rows)-n_ptr-n_inline} 张")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
