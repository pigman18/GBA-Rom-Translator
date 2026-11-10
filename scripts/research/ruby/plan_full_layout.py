#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用项目自带的 auto_layout 生成完整翻译计划（不手写任何 stride 常量）。

## 为什么要有这个脚本

2026-11-05 用户指出：整套流程应该是「解析 texts.json → 判定归属 →
算步长 → 排放 → 批量出补丁」，项目里 auto_layout / table_expand /
table_relink / region_alloc 早就实现了这些。之前手写脚本逐表试错是错的。

本脚本只做一件事：把 build.json 的条目喂给 auto_layout，
打印它给出的**完整计划**（每张表属于哪个容器、用什么模式、步长候选多少）。

用法：
    python scripts/research/ruby/plan_full_layout.py
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
sys.path.insert(0, str(ROOT / "src"))

GAME = "POKEMON_RUBY_AXVJ00"
ROM = ROOT / "roms" / "origin" / f"{GAME}.gba"
BUILD = ROOT / "work" / GAME / "translate.build.json"

# 各定长表「名字字段真实可用字节数」——逐字节对过 ROM（emit_table_data.py）。
# texts.json 不带这个信息，而 stride-name_offset 会把元数据算进名字区。
MEASURED_USABLE = {
    "招式名": 8,
    "特性名": 8,
    "属性名": 5,
    "宝可梦名": 6,
    "特性说明": 19,
    "招式说明": 56,
    "道具名": 9,          # +0x09 之后是 u16/u8 字段
    "图鉴分类名": 6,      # +6 起 6B 名字，+0x0C 起 16B 元数据
    "秘密基地装饰名": 10,  # +13 起 10B
    "树果名": 10,
    "训练家个人名": 32,
    "性格名": 4,
    "UI-详情页": 4,
    "招式名-华丽大赛": 4,
    "招式说明-华丽大赛": 4,
    "属性名-华丽大赛": 4,
}


def load_tables_from_texts_json() -> dict:
    """从 texts.json 读出全部定长表的几何（base/stride/n/name_offset）。

    texts.json 的实际结构（勿猜）::

        "招式名": {
          "start": "0x1cad04", "end": "0x1cb813",
          "type": "stride",
          "read": {"stride": 8}
        }
        "道具名": {
          "start": "0x39a648", "end": "0x39dca7",
          "type": "struct",
          "read": {"entry_size": 40, "desc_ptr_offset": 16, "name_offset": 0}
        }

    即 start/end 在模块顶层，stride/entry_size 在 read 里。
    n 由 (end - start) / stride 推出来，不单独存。
    """
    p = ROOT / "configs" / GAME / "translate" / "texts.json"
    tj = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for mid, meta in (tj.get("modules") or {}).items():
        if not isinstance(meta, dict):
            continue
        typ = meta.get("type") or ""
        if typ not in ("stride", "struct", "stride_ptr", "ptr_stride"):
            continue
        start = meta.get("start")
        end = meta.get("end")
        if start is None or end is None:
            continue
        read = meta.get("read") or {}
        stride = int(read.get("stride") or read.get("entry_size") or 0)
        if stride <= 0:
            continue
        base = int(str(start), 16) if isinstance(start, str) else int(start)
        last = int(str(end), 16) if isinstance(end, str) else int(end)
        n = (last - base) // stride if last > base else 0
        noff = int(read.get("name_offset") or 0)
        # usable：名字字段的真实可用字节数。
        # texts.json 没有这个字段，用 scripts/research/ruby/emit_table_data.py
        # 里实测过的表来补（那份几何逐字节对过 ROM）。
        usable = MEASURED_USABLE.get(mid)
        if usable is None:
            usable = stride - noff
        out[mid] = {
            "base": base,
            "stride": stride,
            "n": n,
            "name_offset": noff,
            "usable": int(usable),
            "type": typ,
        }
    return out


def main() -> int:
    from meowth.auto_layout import build_layout_plan, report

    if not BUILD.is_file():
        print(f"[ERR] 缺 {BUILD}")
        return 3
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = build.get("entries") or []

    tables = load_tables_from_texts_json()
    print(f"from texts.json 读到 {len(tables)} 张定长表：")
    for k, v in tables.items():
        print(f"  {k:<16} base=0x{v['base']:06X} stride={v['stride']:<3} "
              f"n={v['n']:<4} name@+{v['name_offset']}")
    print()

    rom = ROM.read_bytes()

    # ★ 关键修正：body 必须是「译文的真实编码长度」，不能用 target_hex。
    #   target_hex 是编排期已经决定好的结果（可能已是 keep 原文），
    #   拿它算容量会得出「全都装得下」的假结论（实测 11 张表全报 fixed、溢出 0）。
    #   正确做法：用 texts_translated 的中文重新 encode，长度含结尾 FF。
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path

    cm = Charmap(charmap_path=get_charmap_path(GAME), target_lang="zh-Hans")
    trans = ROOT / "configs" / GAME / "translate" / "texts_translated.json"
    tj = json.loads(trans.read_text(encoding="utf-8"))
    zh_by_orig = {}
    for x in tj:
        o = (x.get("original") or "")
        t = x.get("translated")
        if o and isinstance(t, str) and t.strip():
            zh_by_orig[o.strip()] = t

    by_id = {str(e.get("id") or ""): e for e in entries}

    def body_of(c) -> bytes:
        e = by_id.get(str(getattr(c, "entry_id", "") or ""))
        if e is None:
            return b""
        orig = (e.get("original") or "").strip()
        zh = zh_by_orig.get(orig)
        if not zh:
            return b""
        try:
            return cm.encode(zh)
        except Exception:
            return b""

    plan = build_layout_plan(rom, entries, tables, body_of=body_of)
    print(report(plan))
    print()
    print("定长表详细：")
    print(f"{'表':<16}{'条数':>5}{'stride':>8}{'新stride':>9}{'倍数':>5}"
          f"{'容量':>6}{'字数上限':>9}{'溢出':>6}  模式")
    print("-" * 92)
    for g in plan.table_groups:
        cap = g.stride - g.name_offset
        new_cap = g.new_stride - g.name_offset
        print(f"{g.table_name:<16}{len(g.entries):>5}{g.stride:>8}"
              f"{g.new_stride:>9}{g.stride_mult:>5}{cap:>6}{new_cap // 4:>9}"
              f"{g.overflow:>6}  {g.mode.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
