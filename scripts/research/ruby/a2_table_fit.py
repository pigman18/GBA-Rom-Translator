#!/usr/bin/env python3
"""查各定长表的译文能否保持 stride。

auto_layout 把所有表都判成 fixed，但需要真实译文长度来确认。
本脚本用真实译文编码后统计塞不塞得下。

用法：
    python scripts/research/ruby/a2_table_fit.py
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

BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"

TABLES = {
    "招式名":         (0x1CACFC, 8,  0, 354),
    "特性名":         (0x1CBC44, 8,  0, 77),
    "属性名":         (0x1CBB0C, 5,  0, 18),
    "道具名":         (0x39A648, 40, 0, 348),
    "图鉴分类名":     (0x38474C, 28, 6, 386),
    "秘密基地装饰名": (0x3C2A44, 28, 13, 120),
    "树果名":         (0x3A1034, 56, 0, 21),
}


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import encode_body

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    print(f"{'表':<16} {'cap':>4} {'条数':>5} {'塞得下':>7} {'超长':>5} {'最长':>5}")
    print("-" * 52)
    grand_over = 0
    for name, (base, stride, noff, n) in TABLES.items():
        cap = stride - noff
        fits = over = 0
        longest = 0
        over_samples = []
        for e in d.get("entries") or []:
            if e.get("module") != name:
                continue
            if e.get("type") != "replace" or e.get("phrase_code") is None:
                continue
            text = e.get("translated") or ""
            if not text:
                continue
            body = encode_body(cm, text)
            longest = max(longest, len(body))
            if len(body) <= cap:
                fits += 1
            else:
                over += 1
                if len(over_samples) < 3:
                    over_samples.append((text, len(body)))

        grand_over += over
        print(f"{name:<16} {cap:>4} {fits+over:>5} {fits:>7} {over:>5} {longest:>5}")
        for t, ln in over_samples:
            print(f"      超长样本: {t!r} = {ln}B")

    print("-" * 52)
    print(f"总超长: {grand_over} 条")

    print()
    print("=== 结论 ===")
    if grand_over == 0:
        print("✅ 全部塞得下 → 全部走 fixed，只改字面量，不改机器码")
    else:
        print(f"⚠️ {grand_over} 条超长 → 这些表需要 varlen 或缩句")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
