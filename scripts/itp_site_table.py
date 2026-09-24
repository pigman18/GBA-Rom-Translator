#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InitTextPrinter 调用点参数表：(TILE_BASE, a4=X, a5=Y)

背景
----
主包装 `0x08002D1C` 的签名 = `(r0=win, r1=text, r2=TILE_BASE, r3=a4, [sp,#0]=a5)`，
它只对 r2 做 `lsls #16 / lsrs #16`（**截断成 u16，不改值**）、对 r3 与 a5 做
`lsls #24 / lsrs #24`（截断成 u8），然后原样转发给 `InitTextPrinter 0x08002C68`。
⇒ **调用点的 r2 就是最终 `win[0x16]`（TILE_BASE）**。

🔴 为什么不用 `scripts/scan_inittp_sites.py` 的结论
    它的回溯正则只认 `movs|mov|adds|subs|ldr|adr`，
    而 `0x080A76xx` 族是
        movs r2, #188
        lsls r2, r2, #2      ← 不被正则匹配 ⇒ 回溯继续往前走 ⇒ 报成 188
    真值是 **752**。这正是「TILE_BASE 表漏 lsls」的现场。
    本脚本把写入链整条取出来并**折算出数值**，且对折不出来的一律标 `?`（不猜）。

只读 ROM。用法：
    python scripts/itp_site_table.py [目标地址=0x08002D1C]
"""
import os
import re
import subprocess
import sys

ROM = "roms/origin/POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000
OBJDUMP = r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin\arm-none-eabi-objdump.exe"
TARGET = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x08002D1C

WRITE_RE = r"^(movs|mov|ldr|adr|adds|subs|lsls|lsrs|asrs|ands|orrs|eors|muls|negs|strh|strb|str)\s+%s\b"
ORIGIN_RE = r"^(movs|mov|ldr|adr)\s+%s\b"


def find_bl_sites(target):
    rom = open(ROM, "rb").read()
    out = []
    for a in range(0, len(rom) - 4, 2):
        hw1 = rom[a] | (rom[a + 1] << 8)
        if (hw1 & 0xF800) != 0xF000:
            continue
        hw2 = rom[a + 2] | (rom[a + 3] << 8)
        if (hw2 & 0xC000) != 0xC000:
            continue
        s = (hw1 >> 10) & 1
        imm10 = hw1 & 0x3FF
        j1 = (hw2 >> 13) & 1
        j2 = (hw2 >> 11) & 1
        imm11 = hw2 & 0x7FF
        i1 = (~(j1 ^ s)) & 1
        i2 = (~(j2 ^ s)) & 1
        d = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
        if d & 0x1000000:
            d -= 0x2000000          # 🔴 25 位符号扩展
        if BASE + a + 4 + d == target:   # 🔴 pc = a+4，不 &~3
            out.append(BASE + a)
    return out


def objdump_range(lo, hi):
    data = open(ROM, "rb").read()[lo - BASE:hi - BASE]
    os.makedirs(".tmp", exist_ok=True)
    tmp = os.path.join(".tmp", "itp_table_range.bin")
    with open(tmp, "wb") as f:
        f.write(data)
    r = subprocess.run([OBJDUMP, "-D", "-b", "binary", "-m", "armv4t",
                        "-M", "force-thumb", "--adjust-vma=0x%08X" % lo, tmp],
                       capture_output=True, text=True)
    out = {}
    for ln in r.stdout.splitlines():
        m = re.match(r"^\s*([0-9a-f]{6,8}):\t([0-9a-f ]{4,})\t(.*)$", ln)
        if m:
            out[int(m.group(1), 16)] = (m.group(2).strip(), m.group(3).strip())
    return out


def norm(txt):
    return re.sub(r"\s+", " ", txt.replace("\t", " ")).strip()


def trace(lines, lo, reg, site, maxsteps=14):
    """取 site 之前最后一条写 reg 的「起源」，并沿路把可折算的常量链折出来。
    返回 (值或None, 描述, 起源地址, 链长度)。值折不出来 ⇒ None（标 ?）。"""
    chain = []
    a = site - 2
    steps = 0
    while a >= lo and steps < maxsteps:
        if a in lines:
            raw, txt = lines[a]
            t = norm(txt)
            if re.match(WRITE_RE % re.escape(reg), t):
                chain.append((a, t))
                if re.match(ORIGIN_RE % re.escape(reg), t):
                    break
        a -= 2
        steps += 1
    chain.reverse()
    v = None
    for _addr, t in chain:
        m = re.match(r"^movs %s, #(\d+)" % reg, t)
        if m:
            v = int(m.group(1))
            continue
        m = re.match(r"^mov %s, #(\d+)" % reg, t)
        if m:
            v = int(m.group(1))
            continue
        m = re.match(r"^adds %s, #(\d+)" % reg, t)
        if m and v is not None:
            v += int(m.group(1))
            continue
        m = re.match(r"^subs %s, #(\d+)" % reg, t)
        if m and v is not None:
            v -= int(m.group(1))
            continue
        m = re.match(r"^lsls %s, %s, #(\d+)" % (reg, reg), t)
        if m and v is not None:
            v <<= int(m.group(1))
            continue
        m = re.match(r"^lsrs %s, %s, #(\d+)" % (reg, reg), t)
        if m and v is not None:
            v >>= int(m.group(1))
            continue
        if re.match(r"^ldr %s, \[pc" % reg, t) or re.match(r"^ldrh? %s, \[" % reg, t):
            v = None            # 运行期取值
            continue
        if re.match(r"^movs? %s, r\d+" % reg, t) or re.match(r"^adds %s, r\d+" % reg, t):
            v = None            # 来自别的寄存器
            continue
    desc = " ; ".join(t for _, t in chain) if chain else "(未找到写 %s 的指令)" % reg
    origin = chain[0][0] if chain else None
    return v, desc, origin


def trace_stack0(lines, lo, site):
    """取 `str rX, [sp, #0]`（= 第 5 参 a5），并折算 rX 的常量。"""
    a = site - 2
    steps = 0
    while a >= lo and steps < 20:
        if a in lines:
            t = norm(lines[a][1])
            m = re.match(r"^str (r\d+), \[sp, #0\]", t)
            if m:
                reg = m.group(1)
                v, desc, _ = trace(lines, lo, reg, a)
                return v, "%s  ←  %s" % (t, desc)
        a -= 2
        steps += 1
    return None, "(未找到 str rX,[sp,#0])"


def main():
    sites = find_bl_sites(TARGET)
    print("目标 0x%08X 全 ROM 调用点 = %d 个\n" % (TARGET, len(sites)))
    if not sites:
        return 1
    lo = min(sites) - 0x60
    hi = max(sites) + 0x10
    lines = objdump_range(lo, hi)

    # ---- 自证闸门：0x080A7634 必须折出 752（本脚本存在的唯一理由）----
    probe = 0x080A7634
    if probe in sites:
        v, desc, _ = trace(lines, lo, "r2", probe)
        ok = (v == 752)
        print("自证闸门：0x080A7634 的 TILE_BASE 折算 = %s  (期望 752)  %s"
              % (v, "✅" if ok else "❌"))
        print("      链 = %s" % desc)
        if not ok:
            print("❌ 自证失败 ⇒ 本表不可信，先修脚本")
            return 2
        print()

    print("%-12s %-8s %-6s %-6s  %s" % ("call site", "TILE_BASE", "a4(X)", "a5(Y)", "TILE_BASE 写入链"))
    print("-" * 118)
    rows = []
    for s in sites:
        tb, tbd, _ = trace(lines, lo, "r2", s)
        a4, a4d, _ = trace(lines, lo, "r3", s)
        a5, a5d = trace_stack0(lines, lo, s)
        rows.append((s, tb, a4, a5))
        print("%-12s %-8s %-6s %-6s  %s"
              % (hex(s), tb if tb is not None else "?", a4 if a4 is not None else "?",
                 a5 if a5 is not None else "?", tbd))

    print()
    tbs = sorted({r[1] for r in rows if r[1] is not None})
    print("TILE_BASE 取值集合 = %s" % ([hex(v) for v in tbs]))
    print("TILE_BASE 未折出（运行期取值）的调用点 = %d 个"
          % sum(1 for r in rows if r[1] is None))
    print()
    print("🔴 容量判据：TILE_BASE + 屏幕格号 必须 < 1024（tilemap 项 10 位）")
    for v in tbs:
        print("    TILE_BASE=%-5d(0x%03X) ⇒ 该窗口预算 %4d 格" % (v, v, 1024 - v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
