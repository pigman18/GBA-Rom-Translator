#!/usr/bin/env python3
"""texts_13: 更严谨的伪文本判据（去掉上版误报）。

上一版把「！连发」「地图名 + CC 控制码」误判为乱码。这里改用
**只有在乱码数据里才会出现的**结构特征，逐条打分：

  S1 未知字形标记 <XX>：JP PCS 0x01-0xF6 全有字形，出现 <XX> 说明是真未知字节
     （decode_pcs 只在 b not in BYTE_TO_CHAR 时输出该标记）。
  S2 高控制码 F7/F8：JP 文本里 F7/F8 不是常规控制，脚本/数据里才有。
  S3 全角拉丁（ｌｍｎｒ等 0xBB-0xF6 区）占比 > 0.25：
     正常日文台词很少大段全角拉丁；数据被当文本解时才这样。
  S4 单字重复噪声：同一 2-gram 在该条内重复 ≥6 次且条目很长（数据自相似）。

判定：命中 S1 或 S2 或 (S3 且 S4) → 判为伪文本（数据/乱码）。
同时显式记录「！/？连发」「CC 控制码」不作为乱码证据。

用法: python scripts/research/ruby/texts_13_pseudo.py
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
OUT = ROOT / "work" / "_probe" / "texts_pseudo.json"

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import BYTE_TO_CHAR  # noqa: E402


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
    seq = []
    while i < len(body):
        b = body[i]
        if b == 0xFC:
            c["ctrl"] += 1
            i += 2
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
            c["high"] += 1
            seq.append(None)
            i += 1
            continue
        if b not in BYTE_TO_CHAR:
            unknown += 1
            seq.append(None)
            i += 1
            continue
        if 0x01 <= b <= 0x50:
            c["hira"] += 1
        elif 0x51 <= b <= 0xA0:
            c["kata"] += 1
        elif b == 0x00:
            c["space"] += 1
            seq.append(None)
            i += 1
            continue
        elif 0xA1 <= b <= 0xBA:
            c["punct"] += 1
        else:
            c["latin"] += 1
        seq.append(b)
        i += 1

    glyphs = c["hira"] + c["kata"] + c["punct"] + c["latin"]
    latin_ratio = c["latin"] / glyphs if glyphs else 0.0
    kana_ratio = (c["hira"] + c["kata"]) / glyphs if glyphs else 0.0

    # 2-gram 重复
    s = [x for x in seq if x is not None]
    grams = Counter(tuple(s[k:k + 2]) for k in range(len(s) - 1))
    max_gram = max(grams.values()) if grams else 0
    repetitive = max_gram >= 6 and len(s) >= 30

    reasons = []
    if unknown:
        reasons.append(f"未知字形<XX>×{unknown}")
    if c["high"]:
        reasons.append(f"F7/F8 高控制×{c['high']}")
    if latin_ratio > 0.25:
        reasons.append(f"全角拉丁占比 {latin_ratio:.0%}")
    if repetitive:
        reasons.append(f"2-gram 重复×{max_gram}")

    pseudo = bool(unknown or c["high"] or (latin_ratio > 0.25 and repetitive))
    return {
        "pseudo": pseudo, "reasons": reasons, "unknown": unknown,
        "high": c["high"], "latin_ratio": latin_ratio, "kana_ratio": kana_ratio,
        "glyphs": glyphs, "repetitive": repetitive, "max_gram": max_gram,
    }


def main() -> int:
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    by_mod: dict[str, list] = defaultdict(list)
    for e in d["entries"]:
        by_mod[e.get("module")].append(e)

    print("=" * 118)
    print("严格伪文本判据（S1 未知字形 / S2 F7-F8 / S3+S4 拉丁高且自相似）")
    print("=" * 118)

    report = {}
    for mod in ("剧情", "补漏剧情", "UI界面"):
        els = by_mod.get(mod, [])
        pseudo = []
        for e in els:
            try:
                raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
            except ValueError:
                continue
            a = analyze(raw)
            if a["pseudo"]:
                pseudo.append((e, a))
        print(f"\n--- {mod}  n={len(els)}   判为伪文本: {len(pseudo)} "
              f"({len(pseudo)/max(len(els),1):.1%})")
        reason_cnt = Counter()
        for e, a in pseudo:
            for r in a["reasons"]:
                key = r.split("×")[0] if "×" in r else r
                reason_cnt[key] += 1
        for r, c in reason_cnt.most_common():
            print(f"      {r:<28} {c}")
        print("      样本:")
        for e, a in pseudo[:6]:
            print(f"        0x{to_int(e.get('address')):08X} "
                  f"{(e.get('original') or '')[:52]!r}")
            print(f"          {', '.join(a['reasons'])}")
        report[mod] = {"n": len(els), "pseudo": len(pseudo),
                       "reasons": dict(reason_cnt),
                       "ratio": len(pseudo) / max(len(els), 1)}

    (ROOT / "work" / "_probe" / "texts_pseudo.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n" + "=" * 118)
    print("汇总")
    print("=" * 118)
    tot_p = tot_n = 0
    for m, r in report.items():
        print(f"  {m:<10} n={r['n']:>5}  伪文本={r['pseudo']:>5} ({r['ratio']:.1%})")
        tot_p += r["pseudo"]
        tot_n += r["n"]
    print(f"  {'合计':<10} n={tot_n:>5}  伪文本={tot_p:>5} ({tot_p/max(tot_n,1):.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
