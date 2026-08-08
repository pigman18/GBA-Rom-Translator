# -*- coding: utf-8 -*-
"""Dump PCS strings in summary/party UI band ~0x3EA000."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\code\GBA-Rom-Translator\src")
from meowth.jp_pcs import decode_pcs
from util.texts_patcher import scan_keyword

rom = Path(r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba").read_bytes()
# file offsets for VA 0x083Exxxx => FO = VA & 0x1FFFFFF
lo, hi = 0x3E9A00, 0x3EB800
data = rom[lo : hi + 1]

# split on FF
strings = []
i = 0
while i < len(data):
    if data[i] == 0xFF:
        i += 1
        continue
    start = i
    while i < len(data) and data[i] != 0xFF:
        i += 1
    chunk = data[start:i]
    if not chunk:
        continue
    # include terminator if present
    body = bytes(chunk) + (b"\xff" if i < len(data) and data[i] == 0xFF else b"")
    try:
        text = decode_pcs(body.rstrip(b"\xff") + b"\xff")
    except Exception:
        text = None
    if not text:
        i += 1
        continue
    # filter garbage-ish
    if len(text) > 80:
        continue
    addr = 0x08000000 + lo + start
    strings.append({"address": hex(addr), "original": text, "len": len(chunk)})

out = Path(r"C:\code\GBA-Rom-Translator\src\util\work\POKEMON_RUBY_AXVJ00\dump_summary_band.json")
out.write_text(json.dumps(strings, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {len(strings)} strings -> {out}")
for s in strings:
    print(f"{s['address']} {s['original']!r}")

# exact short labels we care about
print("\n--- exact keyword scans in band ---")
for kw in [
    "\u3053\u3046\u3052\u304d",
    "\u3064\u3088\u3055",
    "\u306a\u3057",
    "\u305b\u3064\u3081\u3044",
    "\u30ea\u30dc\u30f3",
    "\u3082\u3061\u3082\u306e",
    "\u3042\u3068",
    "\u306e\u3046\u308a\u3087\u304f",
]:
    hits = scan_keyword(
        Path(r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"),
        kw,
        start=lo,
        end=hi,
        max_hits=20,
    )
    exact = [h for h in hits if h.get("original") == kw]
    print(kw, "total", len(hits), "exact", len(exact), [h.get("address") for h in exact])
