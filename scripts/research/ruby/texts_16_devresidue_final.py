#!/usr/bin/env python3
"""texts_16: 开发残留终判（去掉「コンテスト」误命中）。

「テスト」是「コンテスト」的子串，造成大量误报（比赛场景全是正常内容）。
本版：
  - 关键词改用整词/独立出现判定，且排除被更长正常词包含的情况
  - 只保留真正像调试标记的形态，逐条给 ROM 证据

用法: python scripts/research/ruby/texts_16_devresidue_final.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"

FULLWIDTH_LATIN = set("ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
                      "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ")
FULLWIDTH_DIGIT = set("０１２３４５６７８９")

# 真正只可能是调试/工程用的串（不含会被正常词包含的）
DEV_EXACT = ["ＯＢＪ", "Ｏｂｊ", "Ｐｏｋ", "ＢＰ．", "ＴＥＸＴ", "ＴＥＳＴ",
             "ＤＵＭＭＹ", "ＤＥＢＵＧ", "ＳＡＭＰＬＥ", "デバッグプレイ",
             "デバッグ", "テストプレイ", "ダミー"]


def to_int(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    try:
        return int(s, 16) if s.lower().startswith("0x") else int(s, 10)
    except ValueError:
        return None


def core_text(s: str) -> str:
    s = re.sub(r"\\CC[0-9A-Fa-f]+", "", s)
    s = re.sub(r"\\btn[0-9A-Fa-f]{2}", "", s)
    s = re.sub(r"\\\?[0-9A-Fa-f]{2}", "", s)
    s = re.sub(r"\\[0-9A-Fa-f]{2}", "", s)
    s = re.sub(r"\[[^\]]*\]", "", s)
    return s.replace("\n", "").replace("\r", "").replace("\\l", "").strip()


def main() -> int:
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    print("=" * 116)
    print("开发残留终判（整词匹配，排除「コンテスト」干扰）")
    print("=" * 116)

    hits = []
    for e in d["entries"]:
        orig = e.get("original") or ""
        core = core_text(orig)
        if not core:
            continue
        reasons = []
        for kw in DEV_EXACT:
            if kw in core:
                reasons.append(f"含工程标记 {kw}")
                break
        fw = sum(1 for ch in core if ch in FULLWIDTH_LATIN)
        fwd = sum(1 for ch in core if ch in FULLWIDTH_DIGIT)
        if core and len(core) <= 16 and (fw + fwd) / len(core) >= 0.80:
            reasons.append(f"全角拉丁/数字占 {(fw+fwd)/len(core):.0%}")
        if reasons:
            hits.append({"module": e.get("module"), "address": e.get("address"),
                         "original": orig, "core": core, "reasons": reasons})

    print(f"\n命中 {len(hits)} 条")
    bymod = Counter(h["module"] for h in hits)
    for m, c in bymod.most_common():
        print(f"  {m:<20} {c:>5}")
    print()
    for h in hits[:80]:
        print(f"  0x{to_int(h['address']):08X} [{h['module']}] {h['core']!r}")
        print(f"        {h['reasons']}")

    (ROOT / "work" / "_probe" / "texts_devresidue_final.json").write_text(
        json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
