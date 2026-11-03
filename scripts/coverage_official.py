#!/usr/bin/env python3
"""统计「正式场景」（排除探针/工具脚本）的覆盖情况。

排除规则：
  · 名字以 `_` 开头（探针）
  · 工具类：font_*, images_dump, ref_probe, page_sweep, shop 等历史脚本
  · 窗口数 < 5 的（多数是没有可对话 NPC 的房间）

用法：python scripts/coverage_official.py [--low]
  --low  额外列出窗口数 < 5 的场景（便于决定是否值得继续救）
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOTRUNS = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"

# 历史遗留的工具/诊断脚本，不算「场景覆盖」
TOOLS = {
    "font_capture", "font_dump", "font_probe", "font_talk",
    "images_dump", "ref_probe", "page_sweep", "shop",
    "fr_menu", "fr_pair", "fr_pair2", "fr_text",
    "_diag", "_diag2", "selfcheck", "title_menu",
}


def win_count(run: Path) -> int:
    log = run / "origin" / "scene.log"
    if not log.is_file():
        return -1
    return len(re.findall(r"^\[win\]", log.read_text(encoding="utf-8",
                                                    errors="replace"), re.M))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--low", action="store_true")
    a = ap.parse_args()

    rows = []
    for d in sorted(BOTRUNS.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        if d.name in TOOLS:
            continue
        runs = sorted([x for x in d.iterdir() if x.is_dir()], key=lambda x: x.name)
        if not runs:
            continue
        w = win_count(runs[-1])
        # 取最大的一帧数
        idx = runs[-1] / "origin" / "index.csv"
        n = 0
        if idx.is_file():
            n = sum(1 for l in idx.read_text(encoding="utf-8",
                                             errors="replace").splitlines()
                    if l.split(",")[0].isdigit())
        rows.append((d.name, w, n))

    ok = [r for r in rows if r[1] >= 5]
    low = [r for r in rows if 0 <= r[1] < 5]
    print(f"正式场景 {len(rows)} 个")
    print(f"  覆盖良好（窗口≥5）: {len(ok)}")
    print(f"  窗口不足（<5）   : {len(low)}")
    print(f"\n总帧数 {sum(r[2] for r in rows)}，"
          f"含窗口行 {sum(r[1] for r in rows)}")

    if a.low and low:
        print("\n窗口不足的场景（可能是没有可对话 NPC 的房间）：")
        for name, w, n in low:
            print(f"  {name:<28} win={w:<4} 帧={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
