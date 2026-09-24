#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lz77_ctx.py — 逐站反汇编 `bl LZ77UnCompVram/Wram` 前 5 条指令，看清取参模式。"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = (sys.argv[1] if len(sys.argv) > 1 else
       os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"))
LZ_VRAM, LZ_WRAM = 0x081B1298, 0x081B129C
BACK = 28
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 30
OBJDUMP = (r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi"
           r"\14.2 rel1\bin\arm-none-eabi-objdump.exe")
TMP = os.path.join(ROOT, ".tmp")


def blx_targets(rom: bytes):
    out = []
    for i in range(0, len(rom) - 3, 2):
        h1 = rom[i] | (rom[i + 1] << 8)
        h2 = rom[i + 2] | (rom[i + 3] << 8)
        if (h1 & 0xF800) == 0xF000 and (h2 & 0xD000) == 0xD000:
            S = (h1 >> 10) & 1
            imm10 = h1 & 0x3FF
            J1 = (h2 >> 13) & 1
            J2 = (h2 >> 11) & 1
            imm11 = h2 & 0x7FF
            I1 = (~(J1 ^ S)) & 1
            I2 = (~(J2 ^ S)) & 1
            o = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
            if o & 0x01000000:
                o -= 0x02000000
            site = 0x08000000 + i
            out.append((site, (site + 4 + o) & 0xFFFFFFFF))
    return out


def dis(blob: bytes, vma: int):
    os.makedirs(TMP, exist_ok=True)
    f = os.path.join(TMP, "ctx.bin")
    io.open(f, "wb").write(blob)
    out = subprocess.run(
        [OBJDUMP, "-D", "-b", "binary", "-m", "arm", "-M", "force-thumb",
         "--adjust-vma=0x%08X" % vma, f],
        capture_output=True, text=True, errors="replace")
    res = []
    for ln in out.stdout.splitlines():
        parts = ln.split("\t")
        if len(parts) < 2 or not re.match(r"\s*[0-9a-fA-F]+:", parts[0]):
            continue
        res.append(parts[0].strip().rstrip(":") + "  " +
                   " ".join(p.strip() for p in parts[1:] if p.strip()))
    return res


def main() -> int:
    rom = io.open(ROM, "rb").read()
    sites = [(s, t) for s, t in blx_targets(rom) if t in (LZ_VRAM, LZ_WRAM)]
    print("共 %d 站；下面打印前 %d 站的前 5 条指令\n" % (len(sites), LIMIT))
    for site, tgt in sites[:LIMIT]:
        which = "Vram" if tgt == LZ_VRAM else "Wram"
        lines = dis(rom[site - 0x08000000 - BACK: site - 0x08000000 + 4],
                    site - BACK)
        print("---- %08X  %s ----" % (site, which))
        for ln in lines[-6:]:
            print("   " + ln)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
