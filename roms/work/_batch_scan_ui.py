# -*- coding: utf-8 -*-
"""Batch texts_patcher scan for party/summary UI JP gaps."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\code\GBA-Rom-Translator\src")
from util.texts_patcher import scan_keyword

rom = Path(r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba")
out_dir = Path(r"C:\code\GBA-Rom-Translator\src\util\work\POKEMON_RUBY_AXVJ00")
out_dir.mkdir(parents=True, exist_ok=True)

# unicode escapes so file encoding cannot break keywords
KEYWORDS = [
    "\u306a\u3089\u3073\u304b\u3048",  # ならびかえ
    "\u3064\u3088\u3055\u3092\u307f\u308b",  # つよさをみる
    "\u3064\u3088\u3055\u3092\u307f\u307e\u3059\u304b\uff1f",  # つよさをみますか？
    "\u3064\u3088\u3055\u3092 \u307f\u307e\u3059\u304b\uff1f",  # つよさを みますか？
    "\u30d1\u30fc\u30bd\u30ca\u30eb",  # パーソナル
    "\u3068\u304f\u305b\u3044",  # とくせい
    "\u3053\u3046\u3052\u304d",  # こうげき
    "\u306a\u3057",  # なし
    "\u305b\u3064\u3081\u3044",  # せつめい
    "\u304a\u307c\u3048\u3066\u3044\u308b\u308f\u3056",  # おぼえているわざ
    "\u30c8\u30ec\u30fc\u30ca\u30fc\u30e1\u30e2",  # トレーナーメモ
    "\u30bf\u30a4\u30d7\uff0f",  # タイプ／
    "\u30bf\u30a4\u30d7/",  # タイプ/
    "\u306a\u305b\u3044\u304b\u304f",  # なせいかく
    "\u3067\u3042\u3063\u305f\u3088\u3046\u3060",  # であったようだ
    "\u3051\u3044\u3051\u3093\u3061",  # けいけんち
    "\u306e\u3046\u308a\u3087\u304f",  # のうりょく
    "\u3042\u3068",  # あと
    "\u3082\u3061\u3082\u306e",  # もちもの
    "\u304d\u308a\u304b\u3048",  # きりかえ
    "\u30ea\u30dc\u30f3",  # リボン
    "\u30dd\u30b1\u30e2\u30f3\u3058\u3087\u3046\u307b\u3046",  # ポケモンじょうほう
    "\u30dd\u30b1\u30e2\u30f3\u306e\u3046\u308a\u3087\u304f",  # ポケモンのうりょく
]

all_hits: dict[str, list] = {}
for kw in KEYWORDS:
    hits = scan_keyword(rom, kw, max_hits=40, output=None)
    # keep compact
    compact = [
        {
            "address": h.get("address"),
            "original": h.get("original"),
            "end": h.get("end"),
        }
        for h in hits
    ]
    all_hits[kw] = compact
    print(f"=== {kw!r}: {len(compact)} ===")
    for h in compact[:12]:
        print(f"  {h['address']} {h['original']!r}")

out_path = out_dir / "scan_party_summary_ui.json"
out_path.write_text(json.dumps(all_hits, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[ok] {out_path}")
