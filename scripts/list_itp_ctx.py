#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对 BL 到 0x08002D1C（主包装 = InitTextPrinter 转发器）的每个调用点，
打印其**前 8 条指令**的原始反汇编，供人工判定 (tileBase, a4, a5)。

为什么要人工判定：0x080A76xx 族是 `movs r2,#188; lsls r2,r2,#2` ⇒ 真值 752，
而 scripts/scan_inittp_sites.py 的回溯只认 `movs r2,#imm`，**会漏掉紧跟的 lsls**
（= 报成 188）。本脚本不回溯，只把现场摊开。

只读 ROM。用法：
  python scripts/list_itp_ctx.py [目标地址=0x08002D1C] [前后条数=8]
"""
import re
import subprocess
import sys

ROM = "roms/origin/POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000
OBJDUMP = r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin\arm-none-eabi-objdump.exe"
TARGET = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x08002D1C
NCTX = int(sys.argv[2]) if len(sys.argv) > 2 else 8


def dis(lo, hi):
    p = subprocess.run(
        [OBJDUMP, "-D", "-b", "binary", "-m", "armv4t", "-M", "force-thumb",
         "--adjust-vma=0x%08X" % BASE,
         "--start-address=0x%08X" % lo, "--stop-address=0x%08X" % hi, ROM],
        capture_output=True)
    txt = p.stdout.decode("utf-8", "replace")
    ins = []
    for line in txt.splitlines():
        m = re.match(r"\s*([0-9a-f]{6,8}):\t([0-9a-f ]{4,})\t(.*)$", line)
        if m:
            ins.append((int(m.group(1), 16), m.group(3).strip()))
    return ins


def scan_calls(bl_target):
    """全 ROM 扫 BL 到 bl_target 的调用点（Thumb T1，pc=a+4，不 &~3）"""
    data = open(ROM, "rb").read()
    out = []
    for a in range(0, len(data) - 4, 2):
        hw1 = data[a] | (data[a + 1] << 8)
        if (hw1 & 0xF800) != 0xF000:
            continue
        hw2 = data[a + 2] | (data[a + 3] << 8)
        if (hw2 & 0xC000) != 0xC000:
            continue
        s = (hw1 >> 10) & 1
        imm10 = hw1 & 0x3FF
        j1 = (hw2 >> 13) & 1
        j2 = (hw2 >> 11) & 1
        imm11 = hw2 & 0x7FF
        i1 = (~(j1 ^ s)) & 1
        i2 = (~(j2 ^ s)) & 1
        v = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
        if v & (1 << 24):
            v -= 1 << 25
        pc = BASE + a + 4
        if pc + v == bl_target:
            out.append(BASE + a)
    return out


def main():
    sites = scan_calls(TARGET)
    print("目标 0x%08X 调用点 = %d 个（前 %d 条指令现场）\n" % (TARGET, len(sites), NCTX))
    # 批量取反汇编：把调用点按簇合并，减少 objdump 次数
    sites_sorted = sorted(sites)
    clusters = []
    for s in sites_sorted:
        if clusters and s - clusters[-1][1] <= 0x400:
            clusters[-1][1] = s
        else:
            clusters.append([s, s])
    cache = {}
    for lo, hi in clusters:
        for addr, txt in dis(lo - 0x80, hi + 4):
            cache[addr] = txt
    for s in sites_sorted:
        print("--- 0x%08X ---" % s)
        addrs = [a for a in sorted(cache) if a < s][-NCTX:]
        for a in addrs:
            print("     0x%08X: %s" % (a, cache[a]))
        print("     0x%08X: %s  <== BL" % (s, cache.get(s, "?")))
        print()


if __name__ == "__main__":
    main()
