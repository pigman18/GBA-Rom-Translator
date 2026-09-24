# -*- coding: utf-8 -*-
"""xtract.py -- 找出「设置页/选项菜单」相关的原始日文串与中文译文。"""
import json
import re
from pathlib import Path

base = Path(r"C:/code/GBA-Rom-Translator/configs/POKEMON_RUBY_AXVJ00/translate")
p = base / "texts_translated.json"
d = json.loads(p.read_text(encoding="utf-8"))
print("type=%s len=%d" % (type(d).__name__, len(d)))
if isinstance(d, dict):
    for k in list(d)[:3]:
        print("  key=%r val=%r" % (k, str(d[k])[:150]))
    items = d.items()
else:
    print("  item0=%r" % (str(d[0])[:200],))
    items = None

keys = ("速度", "と", "オプション", "せんとう", "ふつう", "はやい", "おそい",
        "フレーム", "サウンド", "エフェクト", "普通", "快", "慢")
if items:
    for k, v in items:
        s = str(v)
        if any(t in str(k) or t in s for t in keys):
            print("  %-40r -> %r" % (str(k)[:40], s[:80]))
