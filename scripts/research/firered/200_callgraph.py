#!/usr/bin/env python3
"""调研(200) 调用图追踪：谁调用字宽函数 0x081DB630，r4 从哪来。

═══════════════════════════════════════════════════════════════════════════
【为什么走这条路】
═══════════════════════════════════════════════════════════════════════════
(192) 已确证字宽函数：
    0x081DB630  ldr  r1,[pc,#0x14]   ; r1 = 0x08B64A40
    0x081DB632  subs r1, r4, r1      ; r1 = r4 - 0x08B64A40   ← r4 是关键
    0x081DB634  cmp  r1, #0xA0       ; 160
    0x081DB636  bhi  → 12
    0x081DB638  beq  → 2
    0x081DB63A  movs r0,#0xA         ; 否则 10

r4 是什么？
  · 若是「当前字符在 0x08B64A40 缓冲里的指针」⇒ 字宽由**偏移**决定
  · 若是「字形码」⇒ 字宽由**码值**决定
两者含义完全不同，必须靠调用者确定。

【本脚本】
 S1 全 ROM 扫 Thumb BL（4 字节 F000 F8xx 编码），建「目标 → 调用者」索引
 S2 列出所有调用 0x081DB630 / 0x081DB660 的位置
 S3 对每个调用者，反汇编其函数体（向前找 push {..,lr} 作为函数头），
    打印调用前的寄存器准备代码
 S4 从调用者继续往上追一层（谁调用调用者）
 S5 在整个调用链里收集所有 PC 字面量，标注指向 ROM 且原版为 FF 的（汉化新增数据）

【BL 解码（Thumb-1 范围 ±16MB）】
  指令1 = 11110 S imm10     指令2 = 11 J1 1 J2 imm11
  目标 = PC + 4 + (S:I1:I2:imm10:imm11:0) 符号扩展

用法：python scripts/research/firered/200_callgraph.py
"""
from __future__ import annotations

import json
import struct
from collections import defaultdict
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "callgraph200"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000

WIDTH_FN = 0x081DB630
TRANS_FN = 0x081DB660


def build_callers(rom: bytes) -> dict[int, list[int]]:
    """扫全 ROM 的 Thumb BL，返回 {目标地址: [调用点地址, ...]}。"""
    callers: dict[int, list[int]] = defaultdict(list)
    N = len(rom)
    for off in range(0, N - 4, 2):
        hw1 = rom[off] | (rom[off + 1] << 8)
        if (hw1 & 0xF800) != 0xF000:
            continue
        hw2 = rom[off + 2] | (rom[off + 3] << 8)
        if (hw2 & 0xF800) != 0xF800:
            continue
        s = (hw1 >> 10) & 1
        imm10 = hw1 & 0x03FF
        j1 = (hw2 >> 13) & 1
        j2 = (hw2 >> 11) & 1
        imm11 = hw2 & 0x07FF
        i1 = 1 - (j1 ^ s)
        i2 = 1 - (j2 ^ s)
        val = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
        if s:
            val -= (1 << 25)
        pc = BASE + off + 4
        target = (pc + val) & 0xFFFFFFFF
        callers[target].append(BASE + off)
    return callers


def find_func_start(rom: bytes, addr: int, back: int = 0x600) -> int:
    """向前找最近的 push {..., lr} 作为函数入口（启发式）。"""
    off = addr - BASE
    best = None
    for o in range(max(0, off - back), off, 2):
        hw = rom[o] | (rom[o + 1] << 8)
        # push {...,lr} = 1011 010 R list, 要求 list 含 lr(bit8)
        if (hw & 0xFE00) == 0xB400 and (hw & 0x0100):
            best = o
    return BASE + best if best is not None else addr


def disasm(rom: bytes, start: int, length: int) -> list[str]:
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    out = []
    off = start - BASE
    for ins in md.disasm(rom[off:off + length], start):
        raw = rom[ins.address - BASE:ins.address - BASE + ins.size]
        out.append(f"0x{ins.address:08X}  {raw.hex():<8} "
                   f"{ins.mnemonic:<8} {ins.op_str}")
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    zh = ROM_ZH.read_bytes()
    ja = ROM_OR.read_bytes()

    print("=" * 78)
    print("S1 建立全 ROM BL 调用索引")
    print("=" * 78)
    callers = build_callers(zh)
    print(f"  不同调用目标：{len(callers):,}")
    total = sum(len(v) for v in callers.values())
    print(f"  BL 指令总数：{total:,}")

    for name, fn in (("字宽函数", WIDTH_FN), ("转码函数", TRANS_FN)):
        print("\n" + "=" * 78)
        print(f"S2 调用 {name} 0x{fn:08X} 的位置")
        print("=" * 78)
        cs = callers.get(fn, [])
        print(f"  调用者 {len(cs)} 个：")
        for c in cs[:20]:
            # 该调用点是否被汉化改过
            o = c - BASE
            same = (ja[o:o + 4] == zh[o:o + 4]) if o + 4 <= len(ja) else False
            print(f"    0x{c:08X}  {'（原版相同）' if same else '（汉化新增/改动）'}")

        # S3 反汇编每个调用者的函数体
        for c in cs[:4]:
            fs = find_func_start(zh, c)
            print(f"\n  ── 调用者 0x{c:08X} 所在函数（起点估计 0x{fs:08X}）──")
            for ln in disasm(zh, fs, c - fs + 32):
                marker = " <<< 调用这里" if f"0x{c:08X}" in ln else ""
                print("    " + ln + marker)

    # ── S4 往上追一层 ────────────────────────────────
    print("\n" + "=" * 78)
    print("S4 追两层：字宽函数的调用者，又有谁调用")
    print("=" * 78)
    level1 = callers.get(WIDTH_FN, [])
    seen = set()
    for c in level1[:6]:
        fs = find_func_start(zh, c)
        if fs in seen:
            continue
        seen.add(fs)
        up = callers.get(fs, [])
        print(f"  0x{fs:08X}（含调用 0x{c:08X}）← 被 {len(up)} 处调用")
        for u in up[:8]:
            print(f"      0x{u:08X}")
            if len(up) <= 3:
                for ln in disasm(zh, u - 0x40, 0x80):
                    print("        " + ln)

    (OUT / "callers.json").write_text(
        json.dumps({"width_fn": callers.get(WIDTH_FN, []),
                    "trans_fn": callers.get(TRANS_FN, []),
                    "n_targets": len(callers), "n_bl": total},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'callers.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
