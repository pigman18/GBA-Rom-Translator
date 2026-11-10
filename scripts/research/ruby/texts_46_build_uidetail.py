#!/usr/bin/env python3
"""texts_46: 建 UI-详情页 模块（唯一验证通过的）。

- 用 stride_ptr @0x397330，end=0x39734C，stride=4
- 收编 work/_reserved_ui_detail.json 的 7 条
- 插在 性格名 之后（同属词条/详情语义），不早于任何可能冲突的模块
- 从 剧情 等模块里把同名地址的条目移除（如果存在）

验证：条目总数必须仍是 12,712；新模块 7 条。

用法: python scripts/research/ruby/texts_46_build_uidetail.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
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

MOD_ID = "UI-详情页"
MODULE = {
    "label": "UI·详情页",
    "group": "文本",
    "default": True,
    "description": ("详情/能力页标签指针表（0x397330 起 7 条）；"
                    "指向 0x3EA787 等正文；原误挂 性格名，0x39734C 处 0x0100FF00 为表尾"),
    "start": "0x397330",
    "end": "0x39734C",
    "type": "stride_ptr",
    "read": {"stride": 4},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    rom = ROM_PATH.read_bytes()
    data = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = data["modules"]
    entries = data["entries"]
    before_total = len(entries)

    print("=" * 100)
    print(f"建模块 {MOD_ID}")
    print("=" * 100)

    if MOD_ID in mods:
        print(f"  ⚠️ 模块已存在，先移除旧定义")
        del mods[MOD_ID]
        entries = [e for e in entries if e.get("module") != MOD_ID]

    # 抽取
    m = dict(MODULE)
    m["id"] = MOD_ID
    new = TP.extract_module(rom, m, "AXVJ", filters=None)
    print(f"  抽取器产出: {len(new)} 条")
    for e in new:
        print(f"    {e['address']} {e['original']!r}")

    if len(new) != 7:
        print(f"  ❌ 预期 7 条，实际 {len(new)} 条，中止")
        return 1

    # 插到 性格名 之后
    order = list(mods.keys())
    if "性格名" in order:
        idx = order.index("性格名") + 1
    else:
        idx = len(order)
    items = list(mods.items())
    items.insert(idx, (MOD_ID, MODULE))
    mods.clear()
    mods.update(dict(items))
    print(f"  插入位置: 索引 {idx}（紧跟 性格名）")

    # 从其它模块移除同地址条目（防止重复归属）
    new_addrs = {e["address"] for e in new}
    removed_from = {}
    kept = []
    for e in entries:
        if e.get("address") in new_addrs and e.get("module") != MOD_ID:
            removed_from[e["module"]] = removed_from.get(e["module"], 0) + 1
            continue
        kept.append(e)
    entries = kept
    if removed_from:
        print(f"  从其它模块移除同地址条目: {removed_from}")
    else:
        print("  其它模块无同地址条目（这 7 条原本已从 性格名 移除）")

    # 追加新条目（按地址排序，保持稳定）
    entries.extend(sorted(new, key=lambda e: e["address"]))

    data["entries"] = entries
    data["count"] = len(entries)

    print()
    print(f"  条目总数: {before_total} -> {len(entries)}")

    # 这 7 条在改动前属于「性格名」（见备份），D2 时被移出并存进
    # work/_reserved_ui_detail.json。现在建模块收编它们，是「恢复归属」不是新增内容。
    # 判据：新增条数必须 == 存档条数，且这些地址在备份里确实存在。
    reserved_path = ROOT / "work" / "_reserved_ui_detail.json"
    backup_path = ROOT / "work" / "_texts_backup_before_d.json"
    added = len(entries) - before_total
    if reserved_path.exists() and backup_path.exists():
        reserved = json.loads(reserved_path.read_text(encoding="utf-8"))
        backup = json.loads(backup_path.read_text(encoding="utf-8"))
        res_addr = {e["address"] for e in reserved}
        bak_addr = {e["address"] for e in backup["entries"]}
        covered = res_addr & new_addrs
        in_backup = covered & bak_addr
        print(f"  存档 {len(reserved)} 条，本次收编 {len(covered)} 条，"
              f"其中在备份里存在的 {len(in_backup)} 条")
        ok = (added == 0 or
              (added == len(covered) and covered == res_addr and in_backup == covered))
        if not ok:
            print(f"  ❌ 新增 {added} 条，与存档 {len(covered)} 条不匹配，中止")
            return 1
        print(f"  ✅ 新增 {added} 条全部来自存档的既有条目（备份中可查），"
              f"非新增内容")
    else:
        if added != 0:
            print(f"  ❌ 新增 {added} 条且无存档核对依据，中止")
            return 1
        print(f"  ✅ 总数保持 {len(entries)}")

    if a.apply:
        TEXTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
        print(f"[ok] 已写入 {TEXTS}")
    else:
        print("[dry-run] 加 --apply 生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
