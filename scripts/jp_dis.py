#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""jp_dis.py — 日版 AXVJ00 ROM 拇指指令反汇编小工具（2026-09-12）

为什么需要：pokeruby_jp.sym 里的地址全是 **UNVERIFIED**（按最近锚点偏移推算），
不能直接拿来打桩（用户教训：「hook 错函数 ⇒ 分配器一下子把 cb 占满」）。
本工具把「取字节 + objdump 反汇编」做成一次调用，用来**逐指令核指纹**。

用法：
    python scripts/jp_dis.py 0x08070A4C 92 [更多 addr nbytes ...]
    python scripts/jp_dis.py --rom roms/origin/xxx.gba 0x081B1298 16
    python scripts/jp_dis.py --word 0x08070A4C 8      # 顺带列出 32-bit 字（找字面量池）

说明：
  · ROM 文件内偏移 = 地址 - 0x08000000（32MB 卡带直映射，无重定位）。
  · objdump 是 Windows 程序，看不到 MSYS /tmp ⇒ 中间文件落在项目内 .tmp/。
  · 输出带真实地址（按 force-thumb 逐 2 字节解码）。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBJDUMP = (r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi"
           r"\14.2 rel1\bin\arm-none-eabi-objdump.exe")
TMPDIR = os.path.join(ROOT, ".tmp")
ROM_BASE = 0x08000000


def dis(rom: bytes, addr: int, nbytes: int, word: bool = False) -> None:
    off = addr - ROM_BASE
    blob = rom[off:off + nbytes]
    if not blob:
        print("  !! 超出 ROM 范围")
        return

    os.makedirs(TMPDIR, exist_ok=True)
    binf = os.path.join(TMPDIR, "jp_dis.bin")
    with open(binf, "wb") as f:
        f.write(blob)

    print("=" * 78)
    print("0x%08X  (%d bytes, file off 0x%X)" % (addr, len(blob), off))
    print("字节: " + " ".join("%02x" % b for b in blob[:32])
          + (" ..." if len(blob) > 32 else ""))
    if word:
        print("word:")
        for k in range(0, len(blob) - 3, 4):
            w = int.from_bytes(blob[k:k + 4], "little")
            note = ""
            if 0x08000000 <= w < 0x0A000000:
                note = "   <== ROM 指针"
            elif 0x02000000 <= w < 0x03000000:
                note = "   <== EWRAM 指针"
            elif 0x03000000 <= w < 0x04000000:
                note = "   <== IWRAM 指针"
            elif 0x06000000 <= w < 0x06020000:
                note = "   <== VRAM 指针"
            print("  +%02X: %08X%s" % (k, w, note))
    print("-" * 78)

    cmd = [OBJDUMP, "-D", "-b", "binary", "-m", "arm", "-M", "force-thumb",
           "--adjust-vma=0x%08X" % addr, binf]
    out = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    lines = out.stdout.splitlines()
    started = False
    for ln in lines:
        if ln.startswith("Disassembly"):
            started = True
            continue
        if not started or not ln.strip():
            continue
        if ":" in ln:
            a, rest = ln.split(":", 1)
            # objdump 已按 --adjust-vma 输出真实地址
            print("  %s: %s" % (a.strip(), rest.strip()))
    if out.returncode != 0:
        print("  !! objdump rc=%d: %s" % (out.returncode, out.stderr.strip()[:200]))
    print()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=os.path.join(
        "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"))
    ap.add_argument("--word", action="store_true", help="顺带列出 32-bit 字")
    ap.add_argument("spec", nargs="+", help="addr nbytes [addr nbytes ...]")
    args = ap.parse_args(argv)

    rompath = args.rom if os.path.isabs(args.rom) else os.path.join(ROOT, args.rom)
    with open(rompath, "rb") as f:
        rom = f.read()
    print("ROM: %s  (%d bytes)" % (rompath, len(rom)))
    print()

    vals = args.spec
    if len(vals) % 2:
        print("参数必须成对：addr nbytes", file=sys.stderr)
        return 2
    for i in range(0, len(vals), 2):
        addr = int(vals[i], 16) if not vals[i].startswith("0x") else int(vals[i], 16)
        dis(rom, addr, int(vals[i + 1], 0), args.word)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
