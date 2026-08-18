#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate pokeruby_jp.sym — AXVJ (JP Ruby) symbol table from US pokeruby.sym.

Method (per user):
  anchor: US PrintNextChar=0x08002FE0 -> JP ProcessCurrentChar=0x080032F8 (delta +0x318)
  All other functions get JP = US + delta of the nearest verified anchor at/below it
  (same-segment anchors keep a constant offset within that segment, per AGENTS.md rule
   "cross-segment offsets are not a constant — use the same-file anchor").
  Verified anchors come from game_addrs.asm / docs (already disasm-confirmed).

Output line:  <jp_addr> <attr> <size> <name> ; US=0x... STATUS
  STATUS: VERIFIED   = real JP addr (KNOWN map, disasm-confirmed)
          UNVERIFIED  = offset-computed candidate, needs disasm confirmation
          KEEP-US     = data / EWRAM / IWRAM symbol, no offset applied
"""
import collections

US_SYM = r"tools/Pokemon_GBA_Font_Patch/symbols/pokeruby/pokeruby.sym"
OUT = r"configs/POKEMON_RUBY_AXVJ00/symbols/pokeruby_jp.sym"

ANCHOR_US = 0x08002FE0   # PrintNextChar
ANCHOR_JP = 0x080032F8   # ProcessCurrentChar
INIT_DELTA = ANCHOR_JP - ANCHOR_US  # +0x318

# US symbol name -> real JP addr (verified by game_addrs/docs/disasm)
VERIFIED = {
    "PrintNextChar": 0x080032F8,
    "Text_InitWindow": 0x08002C68,       # game_addrs InitTextPrinter
    "GetGlyphTilePointers": 0x08003730,
    "GetCursorTilemapPointer": 0x08003708,
    "UpdateTilemap": 0x080036DC,
    "Text_GetWindowPaletteNum": 0x08003728,
    "GetBlankTileNum": 0x080041BC,
    "Text_ClearWindow": 0x08003BA8,
    "DrawInitialDownArrow": 0x08003F4C,
    "DrawDownArrow": 0x08003DAC,
    "StringCopy": 0x080042E8,
    "StringAppend": 0x08004308,
    "StringLength": 0x0800436C,
    "StringExpandPlaceholders": 0x08004530,
    "UnusedPrintMonName": 0x0808DD60,
    "Menu_PrintText": 0x0806F16C,
    "DrawOptionMenuChoice": 0x080889F0,
    "RedrawMenuCursor": 0x0806F41C,
    "DrawMapNamePopup": 0x0809F654,
    "GetBattlerPosition": 0x08075860,
    "sub_8097F58": 0x08097EF0,
    "CpuSet": 0x081B1294,
    "gDexText_UnknownPoke": 0x083E9688,  # docs POKEDEX_CATEGORY_HOOK_PLAN
}

# read US sym (keep first occurrence per name)
rows = []
name_first = {}
for line in open(US_SYM, encoding="utf-8", errors="replace"):
    p = line.split()
    if len(p) < 4:
        continue
    addr, attr, size, name = int(p[0], 16), p[1], p[2], p[3]
    if name not in name_first:
        name_first[name] = len(rows)
    rows.append((addr, attr, size, name))

# verified anchors: (us_addr, jp_addr, name)
anchors = []
for name, jp in VERIFIED.items():
    if name in name_first:
        us = rows[name_first[name]][0]
        anchors.append((us, jp, name))
anchors.sort(key=lambda t: t[0])

def nearest_seg(us_addr):
    """Return anchor with largest us_addr <= us_addr, else None."""
    seg = None
    for (a_us, a_jp, a_name) in anchors:
        if a_us <= us_addr:
            seg = (a_us, a_jp, a_name)
        else:
            break
    return seg

def is_code(us_addr):
    return 0x08000000 <= us_addr <= 0x081FFFFF

out = []
out.append("; pokeruby_jp.sym — AXVJ (Pocket Monsters Ruby JP) symbol table")
out.append("; derived from US pokeruby.sym by same-segment offset from verified anchors")
out.append("; anchor: US PrintNextChar=0x%08X -> JP ProcessCurrentChar=0x%08X (delta +0x%X)"
           % (ANCHOR_US, ANCHOR_JP, INIT_DELTA))
out.append("; STATUS: VERIFIED=disasm-confirmed  UNVERIFIED=offset candidate  KEEP-US=data/no-offset")
out.append(";")

out2 = []
for (us_addr, attr, size, name) in rows:
    if name in VERIFIED:
        out2.append("%08X %s %s %s ; US=0x%08X VERIFIED" % (VERIFIED[name], attr, size, name, us_addr))
        continue
    if is_code(us_addr):
        seg = nearest_seg(us_addr)
        if seg:
            jp = us_addr + (seg[1] - seg[0])
        else:
            jp = us_addr + INIT_DELTA
        segname = seg[2] if seg else "PrintNextChar(global)"
        out2.append("%08X %s %s %s ; US=0x%08X UNVERIFIED(seg=%s)" % (jp, attr, size, name, us_addr, segname))
    else:
        out2.append("%08X %s %s %s ; US=0x%08X KEEP-US" % (us_addr, attr, size, name, us_addr))

open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(out + out2) + "\n")
print("wrote", OUT, "rows:", len(out2))
c = collections.Counter(l.split(";")[-1].strip().split()[0] for l in out2)
print(c)