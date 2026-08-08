# -*- coding: utf-8 -*-
import json
from pathlib import Path

root = Path(r"C:\code\GBA-Rom-Translator")
texts = json.loads(
    (root / "configs/POKEMON_RUBY_AXVJ00/translate/texts.json").read_text(encoding="utf-8")
)
tr_raw = json.loads(
    (root / "configs/POKEMON_RUBY_AXVJ00/translate/texts_translated.json").read_text(
        encoding="utf-8"
    )
)
if isinstance(tr_raw, list):
    tmap = {e["id"]: e.get("translated") for e in tr_raw if isinstance(e, dict) and "id" in e}
elif isinstance(tr_raw, dict) and "entries" in tr_raw:
    tmap = {e["id"]: e.get("translated") for e in tr_raw["entries"]}
elif isinstance(tr_raw, dict) and "translations" in tr_raw:
    tmap = tr_raw["translations"]
else:
    tmap = tr_raw if isinstance(tr_raw, dict) else {}

want = [
    "ならびかえ",
    "つよさをみる",
    "つよさをみますか？",
    "パーソナル",
    "とくせい",
    "もちもの",
    "こうげき",
    "きりかえ",
    "ポケモンのうりょく",
    "ポケモンじょうほう",
    "なし",
    "リボン",
    "あと",
    "せつめい",
    "おぼえているわざ",
    "トレーナーメモ",
    "タイプ／",
    "おや／",
    "レベルアップまで",
    "げんざいのけいけんち",
    "やめる",
    "ぼうぎょ",
    "とくこう",
    "とくぼう",
    "すばやさ",
    "つよさ",
]

print("=== exact in texts.json ===")
for w in want:
    hits = [e for e in texts["entries"] if e.get("original") == w]
    print(f"{w!r}: {len(hits)}")
    for e in hits[:6]:
        tid = e["id"]
        tr = tmap.get(tid) or e.get("translated") or ""
        print(f"  mod={e.get('module')} addr={e.get('address')} tr={tr!r}")

print("\n=== contains つよさを / ならび / みますか？ (UI-ish) ===")
for e in texts["entries"]:
    o = e.get("original") or ""
    if any(k in o for k in ("つよさを", "ならびかえ", "ならびがえ")):
        tid = e["id"]
        tr = tmap.get(tid) or e.get("translated") or ""
        print(e.get("module"), e.get("address"), repr(o)[:80], "=>", repr(tr)[:40])

# mis-module
print("\n=== UI labels wrongly under 性格名 ===")
ui_labels = {
    "ポケモンのうりょく",
    "きりかえ",
    "やめる",
    "パーソナル",
    "とくせい",
    "もちもの",
    "つよさをみる",
    "せつめい",
}
for e in texts["entries"]:
    if e.get("original") in ui_labels and e.get("module") != "UI界面":
        print(e.get("module"), e.get("original"), e.get("address"), e.get("id"))

# lexicon check
lex_dir = root / "configs/POKEMON_RUBY_AXVJ00/translate/lexicon"
lex = {}
for p in lex_dir.glob("*.json"):
    lex.update(json.loads(p.read_text(encoding="utf-8")))
print("\n=== lexicon missing among want ===")
for w in want:
    if w not in lex:
        print(" missing", repr(w))
    else:
        print(" ok", repr(w), "->", repr(lex[w]))
