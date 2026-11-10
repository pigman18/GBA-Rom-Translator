#!/usr/bin/env python3
"""调研㊺ 纠正：火红不止 F7，还有 F8 —— 并据此定位解码/字模逻辑。

═══════════════════════════════════════════════════════════════════════════
【㊹ 的发现（关键纠正）】
═══════════════════════════════════════════════════════════════════════════
反汇编 0x081DB800 处的函数：

    81db800: b5f0        push  {r4,r5,r6,r7,lr}
    81db802: 0004        movs  r4, r0
    81db804: 000d        movs  r5, r1
    81db806: 4f15        ldr   r7, [pc,#84]      ; 取字模基址/上下文
    81db808: 7828        ldrb  r0, [r5,#0]       ; ch = *p
    81db80a: 28ff        cmp   r0, #0xFF
    81db80c: d021        beq   → 结束
    81db80e: 28f7        cmp   r0, #0xF7        ; ★ F7
    81db810: d011        beq   → 0x81DB836
    81db812: 28f8        cmp   r0, #0xF8        ; ★★ F8！
    81db814: d10b        bne   → 0x81DB82E      ; 普通单字节
    81db816: 7869        ldrb  r1, [r5,#1]
    81db818: 29f7        cmp   r1, #0xF7        ; ★★★ F8 F7 组合

⇒ **我前面说「火红只用 F7」是错的。它还有 F8，且 F8 F7 是一个特殊组合。**

这是一个必须立即纠正的结论。之前所有「只用 F7」的判断都基于字节频次，
而 F8 频次在原版里本来就高（0xFE/0xF8 类是假名区），差异被淹没了。

本脚本：
 ① 统计 F8 在汉化里的用法：单独出现 / F8 F7 / F8 其他
 ② 反汇编 F7 分支（0x81DB836）和 F8 分支，看各自跳去哪
 ③ 结合 0x081DB672 处「movs r0,#12 / bx lr」—— #12 极可能是**字形宽度**

用法：python scripts/research/firered/45_f8_discovery.py
"""
from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
TMP = ROOT / "work" / "_probe" / "dis"


def dis(rom: bytes, addr: int, size: int = 0x120) -> list[str]:
    off = addr - BASE
    TMP.mkdir(parents=True, exist_ok=True)
    b, e = TMP / "r2.bin", TMP / "r2.elf"
    b.write_bytes(rom[off:off + size])
    subprocess.run(["arm-none-eabi-objcopy", "-I", "binary", "-O",
                    "elf32-littlearm", "-B", "arm",
                    "--rename-section", ".data=.text", str(b), str(e)],
                   capture_output=True)
    r = subprocess.run(["arm-none-eabi-objdump", "-d",
                        "--adjust-vma=" + hex(addr), "-M", "force-thumb",
                        str(e)], capture_output=True, text=True)
    return [ln.rstrip() for ln in out if False] if False else [
        ln.rstrip() for ln in r.stdout.splitlines()
        if "file format" not in ln and "Disassembly" not in ln and ln.strip()]


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("① F8 的用法统计")
    print("=" * 78)
    for name, rom in (("原版", ja), ("汉化", zh)):
        c = Counter()
        i = rom.find(b"\xf8")
        while i >= 0:
            nxt = rom[i + 1] if i + 1 < n else 0
            if nxt == 0xF7:
                c["F8 F7"] += 1
            elif nxt == 0xF8:
                c["F8 F8"] += 1
            elif nxt == 0xFF:
                c["F8 FF"] += 1
            else:
                c["F8 其他"] += 1
            i = rom.find(b"\xf8", i + 1)
        print(f"  {name}: {dict(c)}  总计 {sum(c.values()):,}")

    # F8 F7 的位置
    print(f"\n  F8 F7 组合出现位置（汉化）：")
    pos = []
    i = zh.find(b"\xf8\xf7")
    while i >= 0:
        pos.append(i)
        i = zh.find(b"\xf8\xf7", i + 1)
    print(f"    共 {len(pos):,} 处")
    newp = [p for p in pos if ja[p:p + 2] != b"\xf8\xf7"]
    print(f"    其中原版不是 F8 F7：{len(newp):,} 处（汉化新增）")
    for p in newp[:10]:
        print(f"      0x{BASE+p:08X}  原 {ja[p-1:p+8].hex(' ')}  "
              f"汉 {zh[p-1:p+8].hex(' ')}")

    # ── ② 反汇编 F7 分支与 F8 分支 ────────────────────────────────
    print("\n" + "=" * 78)
    print("② 反汇编 0x081DB800 整个函数（F7/F8 分派处）")
    print("=" * 78)
    for ln in dis(zh, 0x081DB800, 0x120):
        print("  " + ln)

    print("\n" + "=" * 78)
    print("③ 反汇编 F7 分支 0x081DB836")
    print("=" * 78)
    for ln in dis(zh, 0x081DB830, 0xA0):
        print("  " + ln)

    print("\n" + "=" * 78)
    print("④ 反汇编 0x081DB660 那个函数（含 movs r0,#12）")
    print("=" * 78)
    for ln in dis(zh, 0x081DB640, 0xB0):
        print("  " + ln)

    # ── ⑤ 0x081DB672 里的 #12 是不是字宽 ──────────────────────────
    print("\n" + "=" * 78)
    print("⑤ 0x081DB640 附近函数返回的常量（可能是字宽/字高）")
    print("=" * 78)
    for ln in dis(zh, 0x081DB620, 0x60):
        print("  " + ln)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
