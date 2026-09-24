# -*- coding: utf-8 -*-
"""xtract2.py -- 在 texts_translated.json 里找选项菜单的串。"""
import json
from pathlib import Path

p = Path(r"C:/code/GBA-Rom-Translator/configs/POKEMON_RUBY_AXVJ00/translate/texts_translated.json")
d = json.loads(p.read_text(encoding="utf-8"))

needles = ["ふつう", "はやい", "おそい", "テキスト", "せんとう", "スタイル",
           "エフェクト", "かたむき", "サウンド", "フレーム", "オプション"]
seen = set()
for it in d:
    o = it.get("original", "")
    t = it.get("translated", "")
    for n in needles:
        if n in o:
            k = (o, t)
            if k in seen:
                break
            seen.add(k)
            print("%-30r -> %r" % (o, t))
            break

print("\n---- 含「普通/快/慢」的译文 ----")
for it in d:
    t = it.get("translated", "")
    if any(x in t for x in ("普通", "快", "慢")) and len(t) <= 8:
        print("%-24r -> %r" % (it.get("original", ""), t))
