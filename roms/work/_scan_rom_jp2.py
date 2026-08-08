# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, r'C:\code\GBA-Rom-Translator\src')
from meowth.charmap import Charmap

cm = Charmap(Path(r'C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\charmap.txt'))
rom = Path(r'C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba').read_bytes()
print('sample char', repr(cm.encode_char('\u306a')), 'map size', len(cm.char_to_bytes))

want = [
    '\u306a\u3089\u3073\u304b\u3048',  # narabikae
    '\u3064\u3088\u3055\u3092\u307f\u308b',  # tsuyosa wo miru
    '\u3064\u3088\u3055\u3092\u307f\u307e\u3059\u304b\uff1f',  # tsuyosa wo mimasuka?
    '\u30d1\u30fc\u30bd\u30ca\u30eb',  # personal
    '\u3068\u304f\u305b\u3044',  # tokusei
    '\u3053\u3046\u3052\u304d',  # kougeki
    '\u306a\u3057',  # nashi
    '\u305b\u3064\u3081\u3044',  # setsumei
    '\u304a\u307c\u3048\u3066\u3044\u308b\u308f\u3056',  # oboeteiru waza
    '\u30bf\u30a4\u30d7\uff0f',  # type/
    '\u306a\u305b\u3044\u304b\u304f',  # na seikaku
    '\u3067\u3042\u3063\u305f\u3088\u3046\u3060',  # deatta you da
    '\u3051\u3044\u3051\u3093\u3061',  # keikenchi
    '\u306e\u3046\u308a\u3087\u304f',  # nouryoku
    '\u3042\u3068',  # ato
]
for w in want:
    try:
        enc = bytes(cm.encode_string(w)) + b'\xff'
    except Exception as e:
        print('FAIL', w, e)
        continue
    hits=[]
    start=0
    while True:
        i=rom.find(enc, start)
        if i<0: break
        hits.append(i); start=i+1
        if len(hits)>=25: break
    print(repr(w), 'len', len(enc), 'hits', len(hits), [hex(h) for h in hits[:12]])
