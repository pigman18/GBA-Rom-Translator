#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
15-0c / 缺口①：把 0x08002D1C 的 60 个调用点按「宿主函数」归组，
            回答「同一个 TILE_BASE 是否被同屏的多个窗口共用」。

方法
----
1. 复用 scan_inittp_sites.py 的 BL 扫描 + r2 回溯。
2. 对每个调用点，向前找最近的函数序言（push 指令且其后能识别为 Thumb 函数头），
   作为「宿主函数地址」。
3. 按 (宿主函数, TILE_BASE) 归组，报告：
   - 每个宿主函数里有几个调用点、用了几个 TILE_BASE
   - 同一 TILE_BASE 出现在几个宿主函数里（跨场景共享 ⇒ 不同屏，安全）
   - 同一宿主函数内是否有 >1 个调用点用同一 TILE_BASE（⇒ 同屏风险，需 15-3）

零 ROM 风险（只读）。
"""
import sys
import os
import re
import subprocess
import collections

# 本脚本内联全部扫描逻辑（不与 CLI 版 scan_inittp_sites.py 耦合）
ROM = "roms/origin/POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000
WRAPPER = 0x08002D1C
OBJDUMP = r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin\arm-none-eabi-objdump.exe"


def read_rom():
    return open(ROM, "rb").read()


def find_bl_sites_inline(target, lo=0x08000000, hi=0x08800000):
    rom = read_rom()
    hi = min(hi, BASE + len(rom) - 4)
    out = []
    for a in range(lo, hi, 2):
        o = a - BASE
        hw1 = rom[o] | (rom[o + 1] << 8)
        hw2 = rom[o + 2] | (rom[o + 3] << 8)
        if (hw1 & 0xF800) != 0xF000 or (hw2 & 0xD000) != 0xD000:
            continue
        S = (hw1 >> 10) & 1
        imm10 = hw1 & 0x3FF
        J1 = (hw2 >> 13) & 1
        J2 = (hw2 >> 11) & 1
        imm11 = hw2 & 0x7FF
        I1 = 1 - J1 if S == 0 else J1
        I2 = 1 - J2 if S == 0 else J2
        d = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
        if d & 0x1000000:
            d -= 0x2000000
        if a + 4 + d == target:
            out.append(a)
    return out


def objdump(lo, hi):
    rom = read_rom()
    os.makedirs(".tmp", exist_ok=True)
    p = ".tmp/_15c.bin"
    open(p, "wb").write(rom[lo - BASE:hi - BASE])
    r = subprocess.run([OBJDUMP, "-D", "-b", "binary", "-m", "armv4t",
                        "-M", "force-thumb", "--adjust-vma=0x%08X" % lo, p],
                       capture_output=True, text=True)
    return r.stdout


def parse(asm):
    d = {}
    for ln in asm.splitlines():
        m = re.match(r"^\s*([0-9a-f]{6,8}):\t([0-9a-f ]{4,})\t(.*)$", ln)
        if m:
            d[int(m.group(1), 16)] = (m.group(2).strip(), m.group(3).strip())
    return d


def host_function(site, lines, floor):
    """向前找最近的函数序言。判据：push 且该地址前一条是 bx lr / pop {..,pc} / 对齐空洞。"""
    a = site - 2
    while a > floor:
        if a in lines:
            raw, txt = lines[a]
            if txt.startswith("push") and "lr" in txt:
                return a, txt
        a -= 2
    return None, "(未找到)"


def main():
    sites = find_bl_sites_inline(WRAPPER)
    print("0x%08X 调用点 = %d" % (WRAPPER, len(sites)))
    if not sites:
        return 1

    lo = min(sites) - 0x2000
    hi = max(sites) + 0x40
    # 分段反汇编（跨度 ~1.5MB，一次做完）
    lines = {}
    step = 0x10000
    a = lo
    while a < hi:
        b = min(a + step, hi)
        lines.update(parse(objdump(a, b)))
        a = b
    print("反汇编指令数 = %d" % len(lines))
    print()

    # 自证：#1 已知调用点 0x0802B8FE 的 r2 必须是 0x90
    def bt_r2(site):
        for k in range(1, 16):
            aa = site - 2 * k
            if aa in lines:
                raw, txt = lines[aa]
                m = re.match(r"^(movs|mov|adds|subs|ldr|adr)\s+r2,", txt)
                if m:
                    return aa, txt
        return None, "(回溯失败)"

    rec = []
    for s in sites:
        ha, ht = host_function(s, lines, lo)
        wa, wt = bt_r2(s)
        base_val = None
        if wt:
            m = re.match(r"^(?:movs|mov|adds)\s+r2, #(\d+)", wt)
            if m:
                base_val = int(m.group(1))
            m2 = re.match(r"^adds\s+r2, #(\d+)", wt)
            if m2:
                base_val = int(m2.group(1))
        rec.append((s, ha, wt, base_val))

    # 自证闸门
    chk = [r for r in rec if r[0] == 0x0802B8FE]
    if not chk or chk[0][3] != 0x90:
        print("❌ 自证失败：0x0802B8FE 的 r2 期望 0x90，实得 %s" % (chk[0][3] if chk else None))
        return 2
    print("✅ 自证：0x0802B8FE 的 TILE_BASE 回溯 = 0x%02X" % chk[0][3])
    print()

    # ---- 归组 ----
    by_host = collections.defaultdict(list)
    for s, ha, wt, bv in rec:
        by_host[ha].append((s, bv, wt))

    print("== 宿主函数 → 其内的调用点 / TILE_BASE ==")
    print("%-12s %-4s %-34s" % ("host func", "#bl", "TILE_BASE 列表"))
    print("-" * 64)
    for ha in sorted(by_host, key=lambda x: (x is None, x)):
        lst = by_host[ha]
        vals = [b for _, b, _ in lst]
        shown = ["0x%02X" % b if b is not None else "?" for b in vals]
        print("%-12s %-4d %s" % (hex(ha) if ha else "-", len(lst), ", ".join(shown)))

    print()
    print("== TILE_BASE 值 → 出现在几个宿主函数 / 几个调用点 ==")
    by_val = collections.defaultdict(lambda: (set(), 0))
    for ha, lst in by_host.items():
        for _, bv, _ in lst:
            hosts, n = by_val[bv]
            hosts.add(ha)
            by_val[bv] = (hosts, n + 1)
    for bv in sorted(by_val, key=lambda x: (x is None, x)):
        hosts, n = by_val[bv]
        tag = "0x%02X" % bv if bv is not None else "?"
        print("  TILE_BASE %-6s : %2d 个调用点，分布在 %2d 个宿主函数" % (tag, n, len(hosts)))

    print()
    print("== 🔴 同屏风险：同一宿主函数内有 >1 个调用点用同一 TILE_BASE ==")
    risky = 0
    for ha, lst in by_host.items():
        c = collections.Counter(b for _, b, _ in lst)
        for bv, n in c.items():
            if n > 1 and bv is not None:
                risky += 1
                print("  宿主 0x%08X : TILE_BASE 0x%02X 出现 %d 次" % (ha, bv, n))
    if not risky:
        print("  （无）—— 所有宿主函数内 TILE_BASE 唯一")
    return 0


if __name__ == "__main__":
    sys.exit(main())
