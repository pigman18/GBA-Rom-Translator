#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
15-0b / 缺口①：枚举 InitTextPrinter(0x08002C68) 的全部调用点，并回溯 r2(tile_base)。

目的
----
InitTextPrinter(win, text, tile_base, cur_x, cur_y) —— tile_base 直接写进
win[0x16]（反汇编 0x08002CA2 `strh r2,[r0,#22]`）。所以**每一个调用点都要
自己给一个基址**。如果游戏本身给不同窗口传了互不重叠的基址，那么「位置定号」
根本不需要我们再发明分配器 —— 直接沿用调用者的常量即可。

方法
----
1. 全 ROM 扫 BL 到 0x08002C68（Thumb T1 编码，pc = a+4，**不做 &~3**；
   本仓铁律：曾因 pc&~3 漏报全部调用点）。
2. 从调用点向前回溯最多 24 条指令，找最近一次写 r2 的操作：
     movs/adds r2,#imm   |  movs r2,rN (再回溯 rN)  |  ldr r2,[pc,#imm]
     movs r2,#0 / mov r2,r3 ...
3. 自证闸门：已知的 3 个段内调用点（0x08002CDE / 0x08002D10 / 0x08002D52）
   必须全部被找到，否则判据错，直接报错退出。

零 ROM 风险（只读）。
"""
import sys
import os
import re
import subprocess

ROM = "roms/origin/POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000
# 默认目标 = InitTextPrinter 本体；可用 argv[1] 指定（如 0x08002D1C 主包装）
TARGET = 0x08002C68
OBJDUMP = r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin\arm-none-eabi-objdump.exe"
# 已知调用点（本次基线反汇编实测，见 .tmp/txt.asm 行 1585/1608/1640）
# 自证闸门：仅当 TARGET 为 InitTextPrinter 本体时校验
KNOWN = [0x08002CDE, 0x08002D10, 0x08002D52]


def objdump_range(lo: int, hi: int) -> str:
    """把 [lo,hi) 反汇编成 objdump 文本。"""
    rom = open(ROM, "rb").read()
    o0, o1 = lo - BASE, hi - BASE
    data = rom[o0:o1]
    tmp = os.path.join(".tmp", "scan_range.bin")
    os.makedirs(".tmp", exist_ok=True)
    with open(tmp, "wb") as f:
        f.write(data)
    r = subprocess.run(
        [OBJDUMP, "-D", "-b", "binary", "-m", "armv4t", "-M", "force-thumb",
         "--adjust-vma=0x%08X" % lo, tmp],
        capture_output=True, text=True)
    return r.stdout


def find_bl_sites(target: int, lo: int, hi: int):
    """全区间扫 BL 到 target。Thumb BL/BLX T1：hw1=11110..., hw2=111xx..."""
    rom = open(ROM, "rb").read()
    hi = min(hi, BASE + len(rom) - 4)      # 留 4 字节取 hw2
    out = []
    for a in range(lo, hi, 2):
        o = a - BASE
        hw1 = rom[o] | (rom[o + 1] << 8)
        hw2 = rom[o + 2] | (rom[o + 3] << 8)
        if (hw1 & 0xF800) != 0xF000:
            continue
        if (hw2 & 0xD000) != 0xD000:
            continue
        S = (hw1 >> 10) & 1
        imm10 = hw1 & 0x3FF
        J1 = (hw2 >> 13) & 1
        J2 = (hw2 >> 11) & 1
        imm11 = hw2 & 0x7FF
        I1 = 1 - J1 if S == 0 else J1
        I2 = 1 - J2 if S == 0 else J2
        d = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
        # 🔴🔴 25 位数必须**符号扩展**（bit24 = 符号位）。漏了它会算出天文数字，
        #      表现为「一个调用点都找不到」—— 2026-09-20 本脚本闸门 1 当场抓住。
        #      也正因为如此，位移必须统一写成 pc + d（d 自带符号），
        #      不能再按 S 分两支去加/减。
        if d & 0x1000000:
            d -= 0x2000000
        pc = a + 4                     # 🔴 不做 &~3（本仓血案）
        if pc + d == target:
            out.append(a)
    return out


def main() -> int:
    global TARGET, KNOWN
    if len(sys.argv) > 1:
        TARGET = int(sys.argv[1], 0)
        KNOWN = []                     # 换目标后原闸门不再适用
    # ---- 自证闸门 1：段内已知调用点必须全找到（仅对 InitTextPrinter 本体）----
    if KNOWN:
        got = find_bl_sites(TARGET, 0x08002000, 0x08003000)
        miss = [hex(a) for a in KNOWN if a not in got]
        if miss:
            print("❌ 自证闸门 1 失败：段内已知调用点未找到 = %s（实际找到 %s）"
                  % (miss, [hex(a) for a in got]))
            return 2
        print("✅ 自证闸门 1：段内 3 个已知调用点全部命中")

    # ---- 全 ROM 扫描 ----
    sites = find_bl_sites(TARGET, 0x08000000, 0x08800000)
    print("目标 0x%08X 全 ROM 调用点 = %d 个" % (TARGET, len(sites)))
    print()
    if not sites:
        return 1

    # ---- 反汇编覆盖区（每点前 0x50 字节）----
    lo = min(sites) - 0x60
    hi = max(sites) + 0x20
    asm = objdump_range(lo, hi)
    lines = {}
    for ln in asm.splitlines():
        m = re.match(r"^\s*([0-9a-f]{6,8}):\t([0-9a-f ]{4,})\t(.*)$", ln)
        if m:
            lines[int(m.group(1), 16)] = (m.group(2).strip(), m.group(3).strip())

    def backtrace_r2(site: int):
        """从 site 向前回溯，找最近一次写 r2 的指令及其解释。

        🔴 2026-09-21 修 bug：原正则 `^(movs|mov|adds|subs|ldr|adr)\\s+r2\\b`
        **不含移位/逻辑类**，于是
            movs r2, #188
            lsls r2, r2, #2      ← 不被匹配 ⇒ 继续往前走 ⇒ 报成 188（真值 752）
        造成 `docs/15-0b` §三 的 TILE_BASE 表整列偏低。
        ⚠ 即便修了正则，本函数**只报「最近一次写」的原文，不做常量折算**；
        需要真值请用 `scripts/itp_site_table.py`（带折算 + a4/a5 + 自证闸门）。
        """
        a = site - 2
        steps = 0
        while a >= lo and steps < 30:
            if a in lines:
                raw, txt = lines[a]
                # 写 r2 的形式（含移位/逻辑/乘，缺一个就会出现「停在更早的写」的假值）
                if re.match(r"^(movs|mov|adds|subs|lsls|lsrs|asrs|ands|orrs|eors|muls|negs|ldr|ldrh|ldrb|adr)\s+r2\b", txt):
                    return a, txt
            a -= 2
            steps += 1
        return None, "(回溯失败)"

    def context(site: int, n=4):
        out = []
        a = site - 2 * n
        while a <= site:
            if a in lines:
                raw, txt = lines[a]
                mark = "  <== BL InitTextPrinter" if a == site else ""
                out.append("      0x%08X: %-26s %s%s" % (a, raw, txt, mark))
            a += 2
        return out

    print("%-12s  %-34s  %s" % ("call site", "写入 r2 的指令", "地址"))
    print("-" * 78)
    recs = []
    for s in sites:
        wa, wt = backtrace_r2(s)
        recs.append((s, wa, wt))
        print("%-12s  %-34s  %s" % (hex(s), wt, hex(wa) if wa else "-"))

    print()
    print("== 展开：每个调用点的上下文（含回溯到的 r2 赋值）==")
    for s, wa, wt in recs:
        print("--- call site 0x%08X ---" % s)
        for l in context(s, 3):
            print(l)
        if wa:
            raw, txt = lines.get(wa, ("", ""))
            print("      → r2 = %s   (0x%08X)" % (txt, wa))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
