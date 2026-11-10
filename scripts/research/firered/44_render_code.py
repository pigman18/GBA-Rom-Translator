#!/usr/bin/env python3
"""调研㊹ 渲染协议②：从 F7 的**解码代码**反推字模位置（不再靠统计猜）。

═══════════════════════════════════════════════════════════════════════════
【为什么放弃统计法】
═══════════════════════════════════════════════════════════════════════════
渲染调研已失败 5 次，全部是「用统计特征猜字模区」：
  ㊳ 墨量变异系数       → 随 tile 变大单调下降，假象
  ㊴ 相邻块相关性       → 候选区全 00/FF，无信号
  ㊵ 画点阵看           → 画到的是 00/FF 区
  ㊶ (顺带) 中密度扫描   → 密集区里 orig_mid 与汉化相同
  ㊷ 钟形行墨量         → 文本区 38.0% vs 代码区 34.2%，无区分度

**统计法在这个问题上不可靠。改用代码路径。**

═══════════════════════════════════════════════════════════════════════════
【思路】
═══════════════════════════════════════════════════════════════════════════
中文码位是 `F7 hi lo`。渲染时必然有这样一段代码：
    if (ch == 0xF7) { hi = *p++; lo = *p++; idx = decode(hi, lo); }
    glyph = fontBase + idx * glyphSize;

⇒ 在 ROM 里搜这个常量：
   · `0xF7` 作为立即数参与比较（Thumb: `cmp r0, #0xF7` = `28 F7`）
   · 且附近有「乘 glyphSize」「加 fontBase」

判据：搜字节序列 `28 f7`（cmp rN, #0xF7）和 `f7 28`，统计命中位置，
      再在这些位置附近找「ldr rX,[pc,#imm] 指向某个基址」的指令。

这样能直接拿到 fontBase 和 glyphSize，不需要猜。

用法：python scripts/research/firered/44_render_code.py
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


def dis(rom: bytes, addr: int, size: int = 0xA0) -> list[str]:
    off = addr - BASE
    TMP.mkdir(parents=True, exist_ok=True)
    b, e = TMP / "r.bin", TMP / "r.elf"
    b.write_bytes(rom[off:off + size])
    subprocess.run(["arm-none-eabi-objcopy", "-I", "binary", "-O",
                    "elf32-littlearm", "-B", "arm",
                    "--rename-section", ".data=.text", str(b), str(e)],
                   capture_output=True)
    r = subprocess.run(["arm-none-eabi-objdump", "-d",
                        "--adjust-vma=" + hex(addr), "-M", "force-thumb",
                        str(e)], capture_output=True, text=True)
    return [ln.rstrip() for ln in r.stdout.splitlines()
            if "file format" not in ln and "Disassembly" not in ln
            and ln.strip()]


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("① 搜「与 0xF7 比较」的指令（Thumb cmp rN,#0xF7 = 28 F7）")
    print("=" * 78)
    # cmp r0..r7, #0xF7 : 001 01 Rd(3) imm8  → 0x28F7 | Rd
    pats = {}
    for rd in range(8):
        pats[f"cmp r{rd},#0xF7"] = bytes([0xF7, 0x28 | rd])
    for name, pat in pats.items():
        pos = []
        i = zh.find(pat)
        while i >= 0:
            pos.append(i)
            i = zh.find(pat, i + 1)
        if pos:
            print(f"  {name}: {len(pos)} 处")
            # 只保留「汉化新增」的（原版同位置不同）
            new = [p for p in pos if ja[p:p + 2] != pat]
            print(f"    其中汉化新增：{len(new)} 处")
            for p in new[:8]:
                print(f"      0x{BASE+p:08X}  "
                      f"原 {ja[p-2:p+6].hex(' ')}  汉 {zh[p-2:p+6].hex(' ')}")

    # ── ② 更宽：搜任何引用 0xF7 常量的位置 ────────────────────────
    print("\n" + "=" * 78)
    print("② 搜「字面量池里出现 0x000000F7」的位置（代码里比较 0xF7）")
    print("=" * 78)
    m = n // 4 * 4
    pz = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)
    pa = np.frombuffer(ja[:m], dtype=np.uint32).astype(np.uint64)
    hit = np.flatnonzero(pz == 0xF7)
    print(f"  u32 == 0xF7 的位置：{len(hit)} 处")
    for h in hit.tolist()[:20]:
        o = h * 4
        same = pa[h] == pz[h]
        print(f"    0x{BASE+o:08X}  {'（原版相同）' if same else '★汉化新增'}")

    # ── ③ 反汇编「汉化新增的 cmp #0xF7」附近 ──────────────────────
    print("\n" + "=" * 78)
    print("③ 反汇编汉化新增的 F7 比较点附近")
    print("=" * 78)
    shown = 0
    for rd in range(8):
        pat = bytes([0xF7, 0x28 | rd])
        i = zh.find(pat)
        while i >= 0 and shown < 4:
            if ja[i:i + 2] != pat:
                a = BASE + max(0, i - 0x30)
                print(f"\n  ---- cmp r{rd},#0xF7 @0x{BASE+i:08X} ----")
                for ln in dis(zh, a, 0xA0)[:16]:
                    print("    " + ln)
                shown += 1
            i = zh.find(pat, i + 1)
        if shown >= 4:
            break

    print("\n" + "=" * 78)
    print("④ 已知的 11 个 bx hook 点，逐个反汇编（这些可能就是渲染补丁）")
    print("=" * 78)
    HOOKS = [(0x081DB3E4, 0x08005B2B), (0x087C0062, 0x08005D59),
             (0x087C0066, 0x08005D4D), (0x087C0080, 0x08005F6D),
             (0x087C0084, 0x08005E83), (0x087C0408, 0x080D98B1),
             (0x08E25E44, 0x080060CD), (0x08E25E7E, 0x080060ED),
             (0x08FF908A, 0x08FF753B)]
    for site, tgt in HOOKS[:5]:
        so = site - BASE
        print(f"\n  ---- site 0x{site:08X} ----")
        print(f"    汉化 site 字节: {zh[so-2:so+14].hex(' ')}")
        print(f"    原版 site 字节: {ja[so-2:so+14].hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
