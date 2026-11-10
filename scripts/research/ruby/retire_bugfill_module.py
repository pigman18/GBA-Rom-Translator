#!/usr/bin/env python3
"""补漏剧情模块收尾：废弃模块，内容并入 UI-符号单位。

背景（2026-11-04）：
  `补漏剧情` 靠 fallback 放行，原 1,561 条里 82.9% 是垃圾。
  TextAuditor1 逐条审完后建议整体废弃这条通道。
  清洗后剩 228 条，经查：
    - 22 条内容已在其它模块（剧情/属性名/图鉴分类名/训练家个人名…）→ 直接删
    - 206 条是 UI 单位词、状态词、键盘/音效资源标签 → 并入新建 `UI-符号单位`

处理：
  1. 删除 22 条重复
  2. 建 `UI-符号单位` 模块（type=scan，区间 = 这 206 条的地址包络）
  3. 把 206 条 module 改成 `UI-符号单位`
  4. 从 modules 里删掉 `补漏剧情` 定义

用法：
    python scripts/research/ruby/retire_bugfill_module.py --dry-run
    python scripts/research/ruby/retire_bugfill_module.py --write
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"

OLD_MOD = "补漏剧情"
NEW_MOD = "UI-符号单位"


def main() -> int:
    write = "--write" in sys.argv
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    entries = d["entries"]

    print("=" * 78)
    print(f"补漏剧情 → {NEW_MOD}  {'（写入）' if write else '（dry-run）'}")
    print("=" * 78)

    old = [e for e in entries if e.get("module") == OLD_MOD]
    other_texts: dict[str, list[str]] = defaultdict(list)
    for e in entries:
        if e.get("module") == OLD_MOD:
            continue
        t = (e.get("original") or "").strip()
        if t:
            other_texts[t].append(e.get("module"))

    keep: list[dict] = []
    dup_removed = 0
    moved: list[dict] = []
    for e in entries:
        if e.get("module") != OLD_MOD:
            keep.append(e)
            continue
        t = (e.get("original") or "").strip()
        if t in other_texts:
            dup_removed += 1
            continue
        moved.append(e)

    print(f"原 {OLD_MOD}: {len(old)} 条")
    print(f"  内容已在其它模块 → 删: {dup_removed}")
    print(f"  移入 {NEW_MOD}: {len(moved)}")

    if not moved:
        print("无可迁移条目，退出。")
        return 0

    addrs = []
    for e in moved:
        try:
            addrs.append(int(str(e.get("address") or "0x0").replace("0x", ""), 16))
        except ValueError:
            pass
    addrs.sort()

    # ⚠️ 不能用一个包络区间：这 206 条从 0x0816xxxx 散到 0x083Exxxx，
    #    跨度 2.6MB，用它做 scan 会把整片区域扫进来（内容太杂，全是垃圾）。
    #    正确做法：按地址临近聚簇，每簇单独一个窄区间。
    CLUSTER_GAP = 0x2000          # 相邻条目间隔 < 8KB 视为同一簇
    clusters: list[list[int]] = []
    for a in addrs:
        if clusters and a - clusters[-1][-1] <= CLUSTER_GAP:
            clusters[-1].append(a)
        else:
            clusters.append([a])
    # 只保留真正有密度的簇（>=3 条），单条散点并入最近簇
    bands = []
    for c in clusters:
        lo_a, hi_a = c[0], c[-1]
        bands.append((lo_a, hi_a, len(c)))

    print(f"  条目 {len(addrs)} 条，聚成 {len(bands)} 个簇 "
          f"(间隔阈值 0x{CLUSTER_GAP:X})")
    for lo_a, hi_a, n in bands:
        print(f"    0x{lo_a:08X}..0x{hi_a:08X}  {n} 条  "
              f"跨度 {(hi_a - lo_a) // 1024}KB")

    # 检查旧模块定义存在
    mods = d["modules"]
    if OLD_MOD not in mods:
        print(f"⚠️ modules 里没有 {OLD_MOD}")
    olddef = mods.get(OLD_MOD, {})
    print(f"  旧模块定义: start={olddef.get('start')} end={olddef.get('end')} "
          f"type={olddef.get('type')}")

    print()
    print("移入样例（前 15 条）:")
    for e in moved[:15]:
        print(f"  {e.get('address')}  {(e.get('original') or '')[:40]!r}")

    newdef = {
        "label": "UI·符号单位",
        "group": "UI",
        "default": True,
        "description": ("UI 单位词/状态词/资源标签（原『补漏剧情』模块清洗后的有效部分，"
                        "2026-11-04 由 TextAuditor1 逐条审查确认）"),
        "start": f"0x{lo - 0x08000000:06x}",
        "end": f"0x{hi - 0x08000000:06x}",
        "type": "scan",
    }

    if not write:
        print()
        print("将要新增模块定义:")
        print(json.dumps({NEW_MOD: newdef}, ensure_ascii=False, indent=2))
        print()
        print("dry-run 结束。加 --write 执行。")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = TEXTS.with_suffix(f".json.bak_{stamp}")
    shutil.copy2(TEXTS, bak)
    print(f"\n已备份: {bak.name}")

    for e in moved:
        e["module"] = NEW_MOD

    # 新模块定义插到 UI界面 之后（保持分组邻近）
    newmods: dict = {}
    for k, v in mods.items():
        if k == OLD_MOD:
            continue
        newmods[k] = v
        if k == "UI界面":
            newmods[NEW_MOD] = newdef
    if NEW_MOD not in newmods:
        newmods[NEW_MOD] = newdef

    d["modules"] = newmods
    d["entries"] = keep
    d["count"] = len(keep)
    TEXTS.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")

    print(f"已写入: {TEXTS}")
    print(f"新状态: {len(d['modules'])} 模块 / {d['count']} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
