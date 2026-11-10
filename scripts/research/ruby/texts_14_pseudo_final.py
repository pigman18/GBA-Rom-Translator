#!/usr/bin/env python3
"""texts_14: 伪文本终判（修正 F7/F8 误报）。

texts_13 把 `\CC0CF7`（FC 0C F7 —— FC 控制码的参数字节）误当成「F7 高控制」。
事实：FC 后面紧跟的参数里出现 F7/F8 是完全正常的（方向箭头等）。

本版只统计 **非 FC 参数位置** 的 F7/F8，并保留 S1 未知字形判据。
产出：每个 scan 模块的伪文本候选清单（带理由），写入 JSON 供清理提案引用。

用法: python scripts/research/ruby/texts_14_pseudo_final.py
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
OUT = ROOT / "work" / "_probe" / "texts_pseudo_final.json"

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import BYTE_TO_CHAR  # noqa: E402
from meowth.pcs_codes import fc_arg_count  # noqa: E402


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


def analyze(raw: bytes) -> dict:
    body = raw[:-1] if raw and raw[-1] == 0xFF else raw
    c = Counter()
    unknown = 0
    i = 0
    seq: list[int | None] = []
    while i < len(body):
        b = body[i]
        if b == 0xFC:
            # FC + 命令 + 参数：整段跳过，不把参数算进「高控制」
            if i + 1 >= len(body):
                break
            narg = fc_arg_count(body[i + 1])
            i += 2 + narg
            c["ctrl"] += 1
            continue
        if b == 0xFD:
            i += 2
            c["ctrl"] += 1
            continue
        if b in (0xFE, 0xFA, 0xFB):
            i += 1
            c["ctrl"] += 1
            continue
        if b >= 0xF7:
            c["high"] += 1
            seq.append(None)
            i += 1
            continue
        if b not in BYTE_TO_CHAR:
            unknown += 1
            seq.append(None)
            i += 1
            continue
        if b == 0x00:
            c["space"] += 1
            seq.append(None)
            i += 1
            continue
        if 0x01 <= b <= 0x50:
            c["hira"] += 1
        elif 0x51 <= b <= 0xA0:
            c["kata"] += 1
        elif 0xA1 <= b <= 0xBA:
            c["punct"] += 1
        else:
            c["latin"] += 1
        seq.append(b)
        i += 1

    glyphs = c["hira"] + c["kata"] + c["punct"] + c["latin"]
    latin_ratio = c["latin"] / glyphs if glyphs else 0.0
    kana_ratio = (c["hira"] + c["kata"]) / glyphs if glyphs else 0.0

    s = [x for x in seq if x is not None]
    grams = Counter(tuple(s[k:k + 2]) for k in range(len(s) - 1))
    max_gram = max(grams.values()) if grams else 0
    repetitive = max_gram >= 6 and len(s) >= 30

    reasons = []
    if unknown:
        reasons.append(f"未知字形<XX>×{unknown}")
    if c["high"]:
        reasons.append(f"裸F7/F8×{c['high']}")
    if latin_ratio > 0.30 and repetitive:
        reasons.append(f"全角拉丁{latin_ratio:.0%}+自相似")
    elif latin_ratio > 0.55:
        reasons.append(f"全角拉丁{latin_ratio:.0%}")

    pseudo = bool(reasons)
    return {"pseudo": pseudo, "reasons": reasons, "glyphs": glyphs,
            "kana_ratio": kana_ratio, "latin_ratio": latin_ratio,
            "max_gram": max_gram}


def main() -> int:
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    by_mod: dict[str, list] = defaultdict(list)
    for e in d["entries"]:
        by_mod[e.get("module")].append(e)

    print("=" * 116)
    print("伪文本终判（FC 参数内的 F7/F8 不计入）")
    print("=" * 116)

    report = {}
    for mod in ("剧情", "补漏剧情", "UI界面"):
        els = by_mod.get(mod, [])
        hits = []
        for e in els:
            try:
                raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
            except ValueError:
                continue
            a = analyze(raw)
            if a["pseudo"]:
                hits.append({
                    "id": e.get("id"),
                    "address": e.get("address"),
                    "original": e.get("original"),
                    "reasons": a["reasons"],
                })
        print(f"\n--- {mod}  n={len(els)}  伪文本={len(hits)} "
              f"({len(hits)/max(len(els),1):.1%})")
        rc = Counter()
        for h in hits:
            for r in h["reasons"]:
                rc[r.split("×")[0].split("＋")[0].split("%")[0]] += 1
        for r, cnt in rc.most_common(6):
            print(f"      {r:<24} {cnt}")
        for h in hits[:5]:
            print(f"      0x{to_int(h['address']):08X} "
                  f"{(h['original'] or '')[:50]!r}  {h['reasons']}")
        report[mod] = {"n": len(els), "pseudo": len(hits),
                       "ratio": len(hits) / max(len(els), 1), "hits": hits}

    (ROOT / "work" / "_probe" / "texts_pseudo_final.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n" + "=" * 116)
    for m, r in report.items():
        print(f"  {m:<10} n={r['n']:>5}  伪文本={r['pseudo']:>5} ({r['ratio']:.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
