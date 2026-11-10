#!/usr/bin/env python3
"""texts_15: 开发残留 / 调试串 专项检索。

宝可梦工程里可判定的开发残留特征（每条都从 ROM 原始字节解出）：
  K1 全角拉丁为主的短串（ＢＰ．／Ｐｏｋ／ＯＢＪ…）—— 工程调试标记
  K2 含 "O B J" / "TEXT" / "TEST" / "DUMMY" / "DEBUG" 的日文假名拼音串
  K3 纯数字/编号型占位（如 ＢＰ．）
  K4 连续同字形填充（ーーーー／？？？？）—— 空槽占位

输出：候选清单 + 命中理由，供文档引用。

用法: python scripts/research/ruby/texts_15_devresidue.py
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
OUT = ROOT / "work" / "_probe" / "texts_devresidue.json"

# 全角拉丁 / 全角数字区（JP PCS 0xA1-0xBA 数字与标点, 0xBB-0xF6 全角拉丁）
FULLWIDTH_LATIN = set("ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
                      "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ")
FULLWIDTH_DIGIT = set("０１２３４５６７８９")
DEV_KEYWORDS = ["ＯＢＪ", "Ｏｂｊ", "ｏｂｊ", "Ｐｏｋ", "ｐｏｋ", "ＢＰ", "ｂｐ",
                "ＴＥＸＴ", "Ｔｅｘｔ", "ｔｅｘｔ", "ＴＥＳＴ", "ＤＵＭＭＹ",
                "ＤＥＢＵＧ", "ＳＡＭＰＬＥ", "ダミー", "テスト", "デバッグ"]


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
    by_mod: dict[str, list] = defaultdict(list)
    for e in d["entries"]:
        by_mod[e.get("module")].append(e)

    print("=" * 116)
    print("开发残留 / 调试串 检索")
    print("=" * 116)

    findings = []
    kw_hits = []
    for e in d["entries"]:
        orig = e.get("original") or ""
        core = core_text(orig)
        if not core:
            continue
        reasons = []
        # K2 关键词
        for kw in DEV_KEYWORDS:
            if kw in core:
                reasons.append(f"含调试关键词 {kw}")
                break
        # K1 全角拉丁为主
        fw = sum(1 for ch in core if ch in FULLWIDTH_LATIN)
        fwd = sum(1 for ch in core if ch in FULLWIDTH_DIGIT)
        if core and (fw + fwd) / len(core) >= 0.60 and len(core) <= 20:
            reasons.append(f"全角拉丁/数字占比 {(fw+fwd)/len(core):.0%}")
        if reasons:
            findings.append({
                "module": e.get("module"), "address": e.get("address"),
                "original": orig, "core": core, "reasons": reasons,
            })
            if any("调试关键词" in r for r in reasons):
                kw_hits.append(findings[-1])

    print(f"\n合计候选: {len(findings)}")
    bymod = Counter(f["module"] for f in findings)
    for m, c in bymod.most_common():
        print(f"  {m:<20} {c:>5}")

    print("\n" + "=" * 116)
    print("A. 含调试关键词（最像开发残留）")
    print("=" * 116)
    for f in kw_hits[:40]:
        print(f"  0x{to_int(f['address']):08X} [{f['module']}] {f['core']!r}")
        print(f"        {f['reasons']}")

    print("\n" + "=" * 116)
    print("B. 全角拉丁/数字为主的短串（前 40）")
    print("=" * 116)
    shown = 0
    for f in findings:
        if any("调试关键词" in r for r in f["reasons"]):
            continue
        if shown >= 40:
            break
        print(f"  0x{to_int(f['address']):08X} [{f['module']}] {f['core']!r}")
        shown += 1

    (ROOT / "work" / "_probe" / "texts_devresidue.json").write_text(
        json.dumps(findings, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
