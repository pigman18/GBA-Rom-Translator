# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, r"C:\code\GBA-Rom-Translator\src")
from meowth.charmap import Charmap

cm = Charmap(Path(r"C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\charmap.txt"))
rom = Path(r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba").read_bytes()


def find_all(enc: bytes, limit: int = 40) -> list[int]:
    hits: list[int] = []
    start = 0
    while True:
        i = rom.find(enc, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
        if len(hits) >= limit:
            break
    return hits


want = [
    "ならびかえ",
    "つよさをみる",
    "つよさをみますか？",
    "つよさを みますか？",
    "パーソナル",
    "とくせい",
    "もちもの",
    "こうげき",
    "きりかえ",
    "なし",
    "せつめい",
    "おぼえているわざ",
    "トレーナーメモ",
    "タイプ／",
    "タイプ/",
    "あと",
    "つよさ",
    "なせいかく",
    "であったようだ",
    "けいけんち",
    "のうりょく",
    "リボン",
    "やめる",
]

for w in want:
    try:
        enc = bytes(cm.encode_string(w)) + b"\xff"
    except Exception as e:
        print("ENCODE FAIL", repr(w), e)
        continue
    if len(enc) < 3:
        print("TOO SHORT", repr(w), enc.hex())
        continue
    hits = find_all(enc)
    # also without terminator for multi-hit
    hits_nt = find_all(enc[:-1], limit=20)
    print(
        f"{w!r}: enc={enc.hex()} term_hits={len(hits)} "
        f"offs={[hex(h) for h in hits[:12]]} bare={[hex(h) for h in hits_nt[:8]]}"
    )
