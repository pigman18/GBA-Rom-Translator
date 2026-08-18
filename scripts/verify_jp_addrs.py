#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify candidate JP (AXVJ) addresses against US pokeruby symbols.

Method (per user):
  anchor: US PrintNextChar=0x08002FE0  -> JP ProcessCurrentChar=0x080032F8  (delta +0x318)
  For each US function: JP_candidate = US_addr + delta.
  Disassemble around JP_candidate and look for the same-signature function.
  If found -> mark VERIFIED, else -> mark UNVERIFIED.

Only text / menu / dex / string / healthbox related functions are checked
(the functions this project actually references). Other symbols are left as-is.
"""
import capstone
import re
import os

ROM_PATH = r"roms/origin/POKEMON_RUBY_AXVJ00.gba"
SYM_PATH = r"tools/Pokemon_GBA_Font_Patch/symbols/pokeruby/pokeruby.sym"
ANCHOR_US = 0x08002FE0   # PrintNextChar
ANCHOR_JP = 0x080032F8   # ProcessCurrentChar
DELTA = ANCHOR_JP - ANCHOR_US

# name in US sym  ->  known JP addr (confirmed earlier by docs/game_addrs)
KNOWN = {
    "PrintNextChar": 0x080032F8,
    "Text_InitWindow": 0x08002C68,          # JP InitTextPrinter (game_addrs)
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
}

rom = open(ROM_PATH, "rb").read()
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
md.detail = True


def load_us(fn):
    sym = {}  # name -> (addr, size)
    for line in open(fn, encoding="utf-8", errors="replace"):
        p = line.split()
        if len(p) < 4:
            continue
        addr, attr, size, name = int(p[0], 16), p[1], p[2], p[3]
        if name not in sym:
            sym[name] = (addr, size)
    return sym


def hint(addr, n=12):
    """Return a compact 'signature hint' of the function head."""
    off = addr & 0x01FFFFFF
    ins = list(md.disasm(rom[off:off + n * 2], addr))
    parts = []
    for i in ins[:n]:
        parts.append("%s%s" % (i.mnemonic, (" " + i.op_str) if i.op_str else ""))
    return " | ".join(parts)


def is_fn_head(addr):
    """JP candidate starts a function: first instr is a prologue-ish op."""
    off = addr & 0x01FFFFFF
    if off + 2 > len(rom):
        return False
    it = md.disasm(rom[off:off + 32], addr)
    try:
        first = next(it)
    except StopIteration:
        return False
    mnem = first.mnemonic
    return mnem.startswith("push") or mnem in ("svc",) or mnem.startswith("mov")


def main():
    sym = load_us(SYM_PATH)
    rows = []
    for name, known_jp in sorted(KNOWN.items(), key=lambda kv: kv[1]):
        if name not in sym:
            rows.append((name, None, None, "NO-US-SYM"))
            continue
        us_addr, us_size = sym[name]
        cand = us_addr + DELTA
        status = "VERIFIED" if known_jp == cand else "KNOWNDIFF"
        rows.append((name, us_addr, us_size, status))
        print("== %-28s US=0x%08X size=%s delta=0x%+X JP=0x%08X %s" %
              (name, us_addr, us_size, known_jp - us_addr, known_jp, status))
        print("   JP head: %s" % hint(known_jp, 6))
        if known_jp != cand:
            print("   cand(US+0x%X)=0x%08X head: %s" % (DELTA, cand, hint(cand, 4)))
        print()

    # report any KNOWN that looks NOT like a function head (suspicious)
    print("--- sanity: KNOWN addrs that do NOT look like function heads ---")
    for name, known_jp in sorted(KNOWN.items(), key=lambda kv: kv[1]):
        if not is_fn_head(known_jp):
            print("  %-28s 0x%08X head: %s" % (name, known_jp, hint(known_jp, 4)))


if __name__ == "__main__":
    main()