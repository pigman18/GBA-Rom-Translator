#!/usr/bin/env python3
"""调研㉔ 反汇编火红的补丁代码，逐点确认它在做什么。

═══════════════════════════════════════════════════════════════════════════
【㉒ 发现的真补丁区】
═══════════════════════════════════════════════════════════════════════════
「函数指针被换掉」的 720 个 u32 槽位，新值集中在：
    0x08B0xxxx 126  0x08B1xxxx 120  0x08ECxxxx  86  0x08FFxxxx  72
    0x0874xxxx  69  0x08FExxxx  42  0x08E5xxxx  40  0x08E3xxxx  39
    0x08EDxxxx  38  0x08B4xxxx  34

注意：这些区**并不是**「原版全空」的区（㉒ 的「原版几乎空」探测得 0 个），
说明火红是把**原版已有的空闲缝**填上补丁代码，而不是开一整块新区。
（唯一整块可用的空区 0x6D0000 被拿去放文本了。）

⇒ 0x08B0xxxx / 0x08B1xxxx 其实在「文本区3」0xAF5000 之后不远，
  需要看清楚那里到底是代码还是文本。

本脚本：
  ① 对每个候选补丁区，判定内容性质（代码 / 文本 / 位图）
  ② 对判定为代码的，用 objdump 反汇编，人工可读
  ③ 对 11 个 `bx` hook 点，同时反汇编「原版该处」和「汉化该处」
  ④ 对 720 个被换掉的函数指针，反汇编新旧两个目标各 24 字节

用法：python scripts/research/firered/24_disasm_patches.py
"""
from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
TMP = ROOT / "work" / "_probe" / "dis"
BASE = 0x08000000

CAND = [0x8B00000, 0x8B10000, 0x8EC0000, 0x8FF0000, 0x8740000,
        0x8FE0000, 0x8E50000, 0x8E30000, 0x8ED0000, 0x8B40000]


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))
    TMP.mkdir(parents=True, exist_ok=True)
    objcopy, objdump = "arm-none-eabi-objcopy", "arm-none-eabi-objdump"

    def disasm(rom: bytes, off: int, size: int = 0x200,
               thumb: bool = True) -> list[str]:
        blob = rom[off:off + size]
        b = TMP / "s.bin"
        e = TMP / "s.elf"
        b.write_bytes(blob)
        subprocess.run([objcopy, "-I", "binary", "-O", "elf32-littlearm",
                        "-B", "arm", "--rename-section", ".data=.text",
                        str(b), str(e)], capture_output=True, check=False)
        args = [objdump, "-d", "--adjust-vma=" + hex(BASE + off)]
        if thumb:
            args += ["-M", "force-thumb"]
        r = subprocess.run(args, capture_output=True, text=True)
        return [ln for ln in r.stdout.splitlines()
                if ln.strip() and "file format" not in ln
                and not ln.endswith(">")]

    # ── ① 判定候选区性质 ────────────────────────────────────────────
    print("=" * 78)
    print("① 候选补丁区的性质")
    print("=" * 78)
    print(f"  {'区':>12} {'原版非零':>9} {'汉化非零':>9} {'F7占比':>7} "
          f"{'内容判定'}")
    for off in CAND:
        a = np.frombuffer(ja[off:off + 0x10000], dtype=np.uint8)
        b = np.frombuffer(zh[off:off + 0x10000], dtype=np.uint8)
        za, zb = (a != 0).mean(), (b != 0).mean()
        f7 = (b == 0xF7).mean()
        ff = (b == 0xFF).mean()
        if f7 > 0.02:
            kind = "含文本（F7>2%）"
        elif zb > 0.5:
            kind = "代码/数据（密集）"
        elif zb < 0.05:
            kind = "基本为空"
        else:
            kind = "稀疏（代码+填充）"
        print(f"  0x{BASE+off:08X} {za:>8.1%} {zb:>9.1%} {f7:>6.1%}  "
              f"{kind}   (FF={ff:.1%})")

    # ── ② 反汇编 0x8FF0000 与 0x8ED0000（最像补丁代码的）────────────
    print("\n" + "=" * 78)
    print("② 反汇编候选补丁代码")
    print("=" * 78)
    for off in (0x8FF7500, 0x8ED0000, 0x8E30000, 0x8B00000):
        print(f"\n---- 0x{BASE+off:08X} (Thumb) ----")
        for ln in disasm(zh, off, 0x140)[:26]:
            print("  " + ln)

    # ── ③ 11 个 bx hook 点：原版 vs 汉化 ─────────────────────────────
    print("\n" + "=" * 78)
    print("③ bx hook 点：原版与汉化对照")
    print("=" * 78)
    HOOKS = [
        (0x081DB3E4, 0x08005B2B), (0x087C0062, 0x08005D59),
        (0x087C0066, 0x08005D4D), (0x087C0080, 0x08005F6D),
        (0x087C0084, 0x08005E83), (0x087C0408, 0x080D98B1),
        (0x08E25E44, 0x080060CD), (0x08E25E7E, 0x080060ED),
        (0x08FF908A, 0x08FF753B),
    ]
    for site, tgt in HOOKS:
        so = site - BASE
        print(f"\n---- hook site 0x{site:08X} → 0x{tgt:08X} ----")
        print(f"  原版 site: {ja[so-4:so+12].hex(' ')}")
        print(f"  汉化 site: {zh[so-4:so+12].hex(' ')}")
        to = tgt - BASE
        print(f"  原版 目标内容: {ja[to:to+16].hex(' ')}")
        print(f"  汉化 目标内容: {zh[to:to+16].hex(' ')}")

    # ── ④ 720 个被换掉的函数指针：抽样对照 ───────────────────────────
    print("\n" + "=" * 78)
    print("④ 被换掉的函数指针（抽样 12 个）")
    print("=" * 78)
    m = n // 4 * 4
    pa = np.frombuffer(ja[:m], dtype=np.uint32).astype(np.uint64)
    pz = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)
    is_rom = (pa >= BASE) & (pa < BASE + n) & (pz >= BASE) & (pz < BASE + n)
    ch = np.flatnonzero((pa != pz) & is_rom)
    # 排除文本区
    def in_text(o):
        return (0x6D0000 <= o < 0x722000) or (0xAF5000 <= o < 0xAFB000)
    keep = []
    for s in ch.tolist():
        a = int(pa[s]) - BASE
        b = int(pz[s]) - BASE
        if not (in_text(a) or in_text(b)):
            keep.append((s, a, b))
    print(f"  候选 {len(keep):,} 个")
    # 只挑新值落在补丁区的
    patch_zones = [(0x8E30000, 0x8E40000), (0x8EC0000, 0x8EE0000),
                   (0x8FE0000, 0x9000000), (0x8B00000, 0x8B50000)]
    def in_patch(o):
        return any(lo <= o < hi for lo, hi in patch_zones)
    sel = [t for t in keep if in_patch(t[2])]
    print(f"  新值落在补丁区的：{len(sel):,} 个")
    for s, a, b in sel[:12]:
        print(f"\n  槽位 0x{BASE+s:08X}: 0x{BASE+a:08X} → 0x{BASE+b:08X}")
        print(f"    原版新目标处: {ja[a:a+16].hex(' ')}")
        print(f"    汉化新目标处: {zh[b:b+16].hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
