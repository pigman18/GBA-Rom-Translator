#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Disasm-verify pokeruby_jp.sym candidates (UNVERIFIED code spans only)."""
import capstone
import collections

ROM_PATH = r"roms/origin/POKEMON_RUBY_AXVJ00.gba"
SYM_JP = r"configs/POKEMON_RUBY_AXVJ00/symbols/pokeruby_jp.sym"

rom = open(ROM_PATH, "rb").read()
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
md.detail = False


def hint(addr, n=4):
    off = addr & 0x01FFFFFF
    ins = list(md.disasm(rom[off:off + n * 2], addr))
    return " | ".join("%s %s" % (i.mnemonic, i.op_str) for i in ins[:n]).strip()


def fn_head_score(addr):
    off = addr & 0x01FFFFFF
    if off + 2 > len(rom):
        return 0
    ins = list(md.disasm(rom[off:off + 16], addr))
    if not ins:
        return 0
    first = ins[0]
    m = first.mnemonic
    if m.startswith("push"):
        return 2
    if m == "mov" and "lr" in first.op_str:
        return 2
    if m in ("svc",):
        return 2
    if m in ("ldr", "lsls", "lsrs", "cmp"):
        return 1
    return 0


rows = []
for line in open(SYM_JP, encoding="utf-8", errors="replace"):
    if line.startswith(";") or not line.strip():
        continue
    m = line.split(" ; ")
    if len(m) != 2:
        continue
    body, comment = m
    p = body.split()
    if len(p) < 4:
        continue
    jp = int(p[0], 16)
    status = comment.strip()
    if status.startswith("US=") and "UNVERIFIED" in status:
        status = "UNVERIFIED(" + status.split("UNVERIFIED(")[1].rstrip(")")
    elif "VERIFIED" in status and "UNVERIFIED" not in status:
        status = "VERIFIED(...)"
    else:
        status = "KEEP-US"
    rows.append((jp, p[3], p[2], status))

unv = [r for r in rows if r[3].startswith("UNVERIFIED")]
ver = [r for r in rows if r[3].startswith("VERIFIED")]

print("UNVERIFIED rows:", len(unv), " VERIFIED rows:", len(ver))

stats = collections.Counter()
strong = []
weak = []
junk = []
for (jp, name, size, status) in unv:
    sc = fn_head_score(jp)
    stats[sc] += 1
    if sc == 2:
        strong.append((jp, name, size, status))
    elif sc == 1:
        weak.append((jp, name, size, status))
    else:
        junk.append((jp, name, size, status))

print("UNVERIFIED head-score: 2=strong %d  1=plausible %d  0=junk %d" % (stats[2], stats[1], stats[0]))
print()
print("== STRONG candidates (look like fn heads) %d ===" % len(strong))
for (jp, name, size, status) in strong[:60]:
    print("  0x%08X %-42s size=%-8s %s | %s" % (jp, name, size, status.replace("UNVERIFIED(", "").rstrip(")"), hint(jp, 3)))
print()
print("== JUNK samples (first 20) ==")
for (jp, name, size, status) in junk[:20]:
    print("  0x%08X %-42s size=%-8s %s" % (jp, name, size, status))