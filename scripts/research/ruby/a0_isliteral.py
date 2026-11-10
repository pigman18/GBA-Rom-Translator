#!/usr/bin/env python3
"""A0.2 最终定性：0xB80xx 这些「指针站点」是不是代码字面量池？

观察：
  站点 0xB80A8: +0:0x181086  +1:0xD1032801  +2:0xE02C4800
  站点 0xB80B4: +0:0x18128B  +1:0xD1032802  +2:0xE0264800

0xD1032801 / 0xE02C4800 是典型 Thumb 指令编码。
若站点位于代码段，且邻近字节是合法 Thumb 指令，则这就是 ldr 的字面量池 ——
也就是说，这些指针是游戏代码真正使用的（ldr rX,[pc,#n] 加载），是合法指针。

关键：判断这些站点是否真的被 ldr 引用。

用法：
    python scripts/research/ruby/a0_isliteral.py
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter
from pathlib import Path

import capstone

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)


def find_ldr_for(rom: bytes, lit: int, back: int = 4096) -> list[int]:
    hits = []
    for off in range(max(0, lit - back), lit, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit:
            hits.append(off)
    return hits


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []

    from meowth.policy import collect_entry_text_spans, ptr_site_in_text_body
    text_spans = collect_entry_text_spans(entries)

    f980 = [e for e in entries
            if e.get("type") == "replace" and e.get("phrase_code") is not None
            and (e.get("module") or "") == "剧情"]

    idx: dict[int, list[int]] = {}
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            idx.setdefault(v - GBA_BASE, []).append(off)

    stats: Counter = Counter()
    confirmed = []
    not_confirmed = []

    for e in f980:
        a = e.get("address") or "0x0"
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        sites = [s for s in (idx.get(addr) or []) if not (s & 3)]
        usable = [s for s in sites if not ptr_site_in_text_body(s, text_spans)]
        if not usable:
            continue

        hit = False
        for s in usable:
            ldrs = find_ldr_for(rom, s)
            if ldrs:
                hit = True
                if len(confirmed) < 10:
                    confirmed.append((e, s, ldrs[0]))
                break
        if hit:
            stats["被 ldr 确认（真指针）"] += 1
        else:
            stats["无 ldr 引用"] += 1
            if len(not_confirmed) < 10:
                not_confirmed.append((e, usable[0]))

    print("=== 剧情 1,103 条：指针站点是否被 ldr 引用 ===")
    for k, v in stats.most_common():
        print(f"  {k:<24} {v:>5}")
    print()

    print("=== 被 ldr 确认的样本 ===")
    for e, s, ldr in confirmed:
        print(f"  文本 0x{int(str(e.get('address')).replace('0x',''),16):06X}"
              f"  站点 0x{s:X} ← ldr @ 0x{ldr:X}")
        code = rom[ldr - 4:ldr + 12]
        for ins in md.disasm(code, ldr - 4):
            pass
        insns = list(md.disasm(rom[ldr:ldr + 16], ldr))
        for ins in insns[:4]:
            print(f"     0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}")
    print()

    print("=== 无 ldr 引用的样本 ===")
    for e, s in not_confirmed:
        print(f"  文本 0x{int(str(e.get('address')).replace('0x',''),16):06X}  站点 0x{s:X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
