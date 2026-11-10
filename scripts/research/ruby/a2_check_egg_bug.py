#!/usr/bin/env python3
"""排查：队伍界面多个宝可梦名都显示「蛋」。

现象（010.png）：
  origin:      ラグラージ / ジュカイン / サナギラス / キノココ / タマゴ
  translated:  蛋 / 蛋 / 蛋 / 蛋 / 蛋

可能原因：
  A. 宝可梦名模块的 SLT2 表映射错乱（多个日文名映射到同一个中文）
  B. 本次改动引入了地址冲突（新表覆盖了 SLT2 表或字库）
  C. 原本就如此（基线即有问题）

排查顺序：
  1. 查 build.json 里宝可梦名模块的译文，看是否多个都译成「蛋」
  2. 查 SLT2 表是否被本次新表覆盖
  3. 对比基线产物（改前的 translated.gba 是否也有此问题）

用法：
    python scripts/research/ruby/a2_check_egg_bug.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000

# 日文原名 → 期望中文
LOOKUP = {
    "ラグラージ": "巨沼怪",
    "ジュカイン": "蜥蜴王",
    "サナギラス": "沙基拉",
    "キノココ": "蘑蘑菇",
    "タマゴ": "蛋",
}


def main() -> int:
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []

    # 1. 宝可梦名模块的译文
    print("=== 1. 宝可梦名模块译文检查 ===")
    poke = [e for e in entries if e.get("module") == "宝可梦名"]
    print(f"  条目 {len(poke)} 条")

    found = {}
    for e in poke:
        orig = e.get("original") or ""
        if orig in LOOKUP:
            found[orig] = {
                "translated": e.get("translated"),
                "type": e.get("type"),
                "addr": e.get("address"),
                "phrase_code": e.get("phrase_code"),
                "target_hex": (e.get("target_hex") or "")[:40],
            }

    print(f"  目标宝可梦命中 {len(found)}/{len(LOOKUP)}")
    for k, v in LOOKUP.items():
        f = found.get(k)
        if not f:
            print(f"    {k}: ❌ 未在 build.json 中")
            continue
        ok = "✅" if f["translated"] == v else "⚠️"
        print(f"    {k} → {f['translated']!r} (期望 {v!r}) {ok}")
        print(f"        type={f['type']} addr={f['addr']} "
              f"ph={f['phrase_code']}")
        print(f"        target_hex={f['target_hex']}")

    # 2. 检查是否有大量宝可梦名都译成「蛋」
    print()
    print("=== 2. 译文重复检查（宝可梦名模块）===")
    cnt = Counter(e.get("translated") for e in poke
                  if (e.get("translated") or "").strip())
    dup = [(t, c) for t, c in cnt.most_common(10) if c > 1]
    if dup:
        print("  重复译文（次数>1）:")
        for t, c in dup:
            print(f"    {t!r} × {c}")
    else:
        print("  ✅ 无重复译文")

    # 3. 「蛋」出现几次
    egg = cnt.get("蛋", 0)
    print(f"\n  「蛋」出现 {egg} 次")

    # 4. 检查所有模块里「蛋」
    print()
    print("=== 3. 全库「蛋」的条目 ===")
    all_egg = [e for e in entries if (e.get("translated") or "") == "蛋"]
    print(f"  共 {len(all_egg)} 条")
    for e in all_egg[:10]:
        print(f"    {e.get('module')} {e.get('address')} "
              f"orig={e.get('original')!r} type={e.get('type')} "
              f"ph={e.get('phrase_code')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
