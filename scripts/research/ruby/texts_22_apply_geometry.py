#!/usr/bin/env python3
"""texts_22: D 阶段 第1、2 步 —— 按实测基准改正 texts.json 的模块几何。

改动清单（每条都有 ROM 字节证据，见 docs/TEXTS_JSON_AUDIT.md 与
scripts/research/ruby/tables_ground_truth.py）：

  1. 六张基准表核对
     - 招式名   0x1CAD04 end=0x1CB813 stride=8           → (0x1CB813-0x1CAD04+1)//8 = 354 ✅ 不改
     - 特性名   0x1CBC4C end=0x1CBEB3 stride=8           → 616//8 = 77 ✅ 不改
     - 属性名   0x1CBB0C end=0x1CBB65 stride=5           → 90//5 = 18 ✅ 不改
     - 道具名   0x39A648 end=0x39DCA7 entry_size=40      → 13920//40 = 348 ✅
                 但 read 里缺 name_offset → 显式补 name_offset: 0（原名在槽首）
     - 图鉴分类名 0x384746 end=0x38717D entry=28 name@6 eos=0 → 386 ✅ 不改
     - 秘密基地装饰名 0x3C2A54 end=0x3C3773 entry=28 name@13 → 120 ✅ 不改

  2. 两处几何错误
     - 树果名    entry_size 56→28, end 0x3A14E8→0x3A1503, desc_ptr_offset 12→0x10
                 证据：0x3A1050/0x3A106C/0x3A1088 每 28 字节一个名字；
                 0x3A14E8 的 ナゾ 需要 end>=0x3A1503 才落在末槽内
     - 性格名    start 0x397168→0x3971E8, end 0x39734C→0x39724C
                 证据：0x3971E8 起 25 个 u32 依次指向 0x397168(がんばりや)…0x3971E3(きまぐれ)；
                 0x39724C 的 u32 = 0x020EFF15 不是有效指针

几何变更的模块必须重抽条目（否则 entries 与几何脱节）。重抽时保留已有 translated：
按 (address, original_hex) 匹配回填。

用法：
    python scripts/research/ruby/texts_22_apply_geometry.py --dry-run
    python scripts/research/ruby/texts_22_apply_geometry.py --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

sys.path.insert(0, str(ROOT / "src"))
import util.texts_patcher as TP  # noqa: E402

# --- 1. 六张基准表：只给道具名补 name_offset（其余已在正确值上）---
BASELINE_PATCH = {
    "道具名": {"read": {"name_offset": 0}},
}

# --- 2. 两处几何错误 ---
GEOMETRY_PATCH = {
    "树果名": {
        "end": "0x3A1503",
        "read": {"entry_size": 28, "name_offset": 0, "desc_ptr_offset": 0x10},
        "description": ("树果数据表（クラボ..ナゾ，43 条）；name@0，entry_size=28，"
                        "desc_ptr@0x10 指向说明池（说明池由剧情语料通道收录）"),
    },
    "性格名": {
        "start": "0x3971E8",
        "end": "0x39724C",
        "description": ("性格名指针表（0x3971E8 起 25 条，指向 0x397168 正文）；"
                        "0x397330 起的能力页标签归 UI-详情页，不在此表"),
    },
}


def merge_read(mod: dict, new_read: dict) -> None:
    r = dict(mod.get("read") or {})
    r.update(new_read)
    mod["read"] = r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not (a.apply or a.dry_run):
        a.dry_run = True

    rom = ROM_PATH.read_bytes()
    data = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods: dict = data["modules"]
    entries: list = data["entries"]

    print("=" * 100)
    print(f"{'[DRY-RUN]' if not a.apply else '[APPLY]'} 模块几何改动")
    print("=" * 100)

    changed: list[str] = []

    # 1. 基准表
    for mid, patch in BASELINE_PATCH.items():
        mod = mods[mid]
        before = json.dumps(mod.get("read"), sort_keys=True)
        merge_read(mod, patch["read"])
        after = json.dumps(mod.get("read"), sort_keys=True)
        if before != after:
            changed.append(mid)
            print(f"\n[{mid}] read 补齐")
            print(f"    before: {before}")
            print(f"    after : {after}")

    # 2. 几何错误
    for mid, patch in GEOMETRY_PATCH.items():
        mod = mods[mid]
        print(f"\n[{mid}]")
        for k, v in patch.items():
            if k == "read":
                before = json.dumps(mod.get("read"), sort_keys=True)
                merge_read(mod, v)
                after = json.dumps(mod.get("read"), sort_keys=True)
                print(f"    read: {before}")
                print(f"       -> {after}")
            else:
                print(f"    {k}: {mod.get(k)!r}")
                mod[k] = v
                print(f"       -> {v!r}")
        changed.append(mid)

    # 3. 重抽几何变更模块的条目
    print()
    print("=" * 100)
    print("条目重抽（几何变更模块）")
    print("=" * 100)

    by_mod: dict[str, list] = defaultdict(list)
    for e in entries:
        by_mod[e.get("module")].append(e)

    # 旧条目索引：用于回填 translated
    old_lookup: dict[tuple[str, str, str], str] = {}
    for e in entries:
        key = (e.get("module"), e.get("address"), (e.get("original_hex") or ""))
        if e.get("translated"):
            old_lookup[key] = e["translated"]

    rebuilt: dict[str, list] = {}
    for mid in changed:
        if mid not in GEOMETRY_PATCH:
            continue
        mod = dict(mods[mid])
        mod["id"] = mid
        new = TP.extract_module(rom, mod, "AXVJ", filters=None)
        old = by_mod.get(mid, [])
        reused = 0
        for e in new:
            key = (mid, e.get("address"), e.get("original_hex") or "")
            if key in old_lookup:
                e["translated"] = old_lookup[key]
                reused += 1
        rebuilt[mid] = new
        print(f"\n  [{mid}] 旧 {len(old)} 条 -> 新 {len(new)} 条 "
              f"(回填译文 {reused})")
        print(f"     首条: {new[0]['original']!r} @{new[0]['address']}" if new else "     (空)")
        print(f"     末条: {new[-1]['original']!r} @{new[-1]['address']}" if new else "")

    # 4. 组装新 entries（保持原模块顺序）
    if rebuilt:
        order = [m for m in mods]  # 模块声明顺序
        new_entries: list = []
        idx = 0
        # 按原文件中条目出现顺序重建：遇到被重抽的模块，整段替换
        emitted: set[str] = set()
        for e in entries:
            mid = e.get("module")
            if mid in rebuilt:
                if mid not in emitted:
                    new_entries.extend(rebuilt[mid])
                    emitted.add(mid)
                continue
            new_entries.append(e)
        # 追加原本没有条目但被重抽出条目的
        for mid, lst in rebuilt.items():
            if mid not in emitted:
                new_entries.extend(lst)
        entries = new_entries

    data["entries"] = entries
    data["count"] = len(entries)

    print()
    print("=" * 100)
    print(f"改动模块: {changed}")
    print(f"条目总数: {len(entries)}")
    print("=" * 100)

    if a.apply:
        TEXTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
        print(f"[ok] 已写入 {TEXTS}")
    else:
        print("[dry-run] 未写入；加 --apply 生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
