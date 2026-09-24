#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ROM 区间反汇编（Thumb）—— 唯一的地址核对入口。

用法:
    python scripts/dis_rom.py <start_hex> [len_hex] [rom]

铁律 14：手算 Thumb 指令边界必错，一律走本脚本（底层是 arm-none-eabi-objdump）。
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 0x08000000
OBJDUMP = os.environ.get(
    "OBJDUMP",
    r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1"
    r"\bin\arm-none-eabi-objdump.exe")


def dis(start: int, length: int, rom: str = None) -> int:
    rom = rom or os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
    data = open(rom, "rb").read()
    o = start - BASE
    if o < 0 or o + length > len(data):
        print("❌ 区间越界: %#x+%#x (rom=%d)" % (start, length, len(data)))
        return 2
    tmp = os.path.join(tempfile.gettempdir(), "dis_rom.bin")
    open(tmp, "wb").write(data[o:o + length])
    r = subprocess.run(
        [OBJDUMP, "-D", "-b", "binary", "-m", "armv4t", "-M", "force-thumb",
         "--adjust-vma=0x%08X" % start, tmp],
        capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr)
        return r.returncode
    # 去掉 objdump 的文件头/尾，只留指令行
    for ln in r.stdout.splitlines():
        if "\t" in ln and ":" in ln:
            print(ln)
    return 0


if __name__ == "__main__":
    s = int(sys.argv[1], 16)
    n = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x40
    rom = sys.argv[3] if len(sys.argv) > 3 else None
    sys.exit(dis(s, n, rom))
