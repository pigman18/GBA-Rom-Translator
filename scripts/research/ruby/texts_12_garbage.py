#!/usr/bin/env python3
"""texts_12: 剧情/补漏剧情 的「伪文本」识别（乱码 vs 真台词）。

判据（不靠感觉，用可量化的语言特征）：
  真日文台词：需要含足够多的平假名（0x01–0x50），且假名/字形比高、
             不含 F7/F8/F9 等非常规控制码、不含连续的 <XX> 未知字节。
  乱码/数据：假名极少、被全角拉丁/符号占据、或含大量未知字节标记。

用 JP PCS 表的码位区间做统计：
  hiragana 0x01-0x50, katakana 0x51-0xA0, punct/digit 0xA1-0xBA,
  latin 0xBB-0xF6. 控制 FE/FA/FB/FC/FD/FF.

用法: python scripts/research/ruby/texts_12_garbage.py
"""
from __future__ import annotations

import json
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
OUT = ROOT / "work" / "_probe" / "texts_garbage.json"


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


def classify_raw(raw: bytes) -> dict:
    """按 JP PCS 码位区间统计一行的构成。"""
    body = raw[:-1] if raw and raw[-1] == 0xFF else raw
    c = Counter()
    i = 0
    while i < len(body):
        b = body[i]
        if b == 0xFC:
            c["ctrl"] += 1
            i += 2  # 简化：FC + 1 参
            continue
        if b in (0xFE, 0xFA, 0xFB):
            c["ctrl"] += 1
            i += 1
            continue
        if b == 0xFD:
            c["ctrl"] += 1
            i += 2
            continue
        if b >= 0xF7:
            c["high"] += 1  # F7 F8 F9 —— 非常规，JP 表里无对应字形
            i += 1
            continue
        if 0x01 <= b <= 0x50:
            c["hira"] += 1
        elif 0x51 <= b <= 0xA0:
            c["kata"] += 1
        elif b == 0x00:
            c["space"] += 1
        elif 0xA1 <= b <= 0xBA:
            c["punct"] += 1
        elif 0xBB <= b <= 0xF6:
            c["latin"] += 1
        i += 1
    return c


def main() -> int:
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    entries = d["entries"]
    by_mod: dict[str, list] = defaultdict(list)
    for e in entries:
        by_mod[e.get("module")].append(e)

    print("=" * 116)
    print("剧情 / 补漏剧情 / UI界面：按语言特征区分真台词与乱码")
    print("=" * 116)

    report = {}
    for mod in ("剧情", "补漏剧情", "UI界面"):
        els = by_mod.get(mod, [])
        good = bad = ambiguous = 0
        bad_samples = []
        for e in els:
            try:
                raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
            except ValueError:
                continue
            c = classify_raw(raw)
            glyphs = c["hira"] + c["kata"] + c["punct"] + c["latin"]
            if glyphs == 0:
                ambiguous += 1
                continue
            kana = c["hira"] + c["kata"]
            # 真台词：假名占字形比 >= 0.6，且无大量 F7-F9
            if kana / glyphs >= 0.60 and c["high"] == 0:
                good += 1
            else:
                bad += 1
                if len(bad_samples) < 6:
                    bad_samples.append(
                        (e.get("address"), (e.get("original") or "")[:44],
                         f"hira={c['hira']} kata={c['kata']} latin={c['latin']} "
                         f"punct={c['punct']} high={c['high']}"))
        report[mod] = {
            "n": len(els), "clean": good, "garbage": bad, "no_glyph": ambiguous,
            "garbage_ratio": bad / max(good + bad, 1),
        }
        print(f"\n--- {mod}  n={len(els)}")
        print(f"    像真台词 : {good:>5}")
        print(f"    像乱码   : {bad:>5}  ({bad/max(good+bad,1):.1%})")
        print(f"    无字形   : {ambiguous:>5}")
        print("    乱码样本:")
        for a, o, why in bad_samples:
            print(f"      0x{a}  {o!r}")
            print(f"        {why}")

    (ROOT / "work" / "_probe" / "texts_garbage.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n" + "=" * 116)
    print("汇总")
    print("=" * 116)
    for m, r in report.items():
        print(f"  {m:<10} n={r['n']:>5}  真台词={r['clean']:>5}  "
              f"乱码={r['garbage']:>5} ({r['garbage_ratio']:.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
