#!/usr/bin/env python3
"""调研㊲ 从中文名表反查代码 —— 找到读取它的位置，从而定位原版名字来源。

═══════════════════════════════════════════════════════════════════════════
【思路转变】
═══════════════════════════════════════════════════════════════════════════
前面一直在 ROM 里「找原版 412×11 物种名表」，两次不同判据都是 0 命中。
⇒ 火红的物种名不是那个布局。继续猜布局是浪费。

**正确做法：从已知点反推。**
已知：中文名表在 ROM 的 0x0871F446（原版该区 100% FF，是汉化新增）。
⇒ 汉化的代码**必然**引用 0x0871F446 或它附近的地址。
⇒ 在 ROM 里搜这个地址的 u32 引用，找到代码，就知道整套名字机制。

同样，中文文本区 0x086D0000 的引用也能定位「文本加载」代码。

本脚本：
 ① 搜 ROM 里所有 u32 == 0x0871F446（及邻近，如名表基址、带偏移）
 ② 搜 u32 落在 0x0871F446..0x08722000 区间的位置
 ③ 对这些引用点反汇编，看它怎么用
 ④ 搜 0x086D0000（中文主文本区）的引用，看文本指针机制

用法：python scripts/research/firered/37_find_name_code.py
"""
from __future__ import annotations

import struct
import subprocess
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
TMP = ROOT / "work" / "_probe" / "dis"


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def dis(addr: int, rom: bytes, size: int = 0x80, width: int = 8) -> list[str]:
    off = addr - BASE
    TMP.mkdir(parents=True, exist_ok=True)
    b, e = TMP / "x.bin", TMP / "x.elf"
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
            and ln.strip()][:width]


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))
    m = n // 4 * 4

    pz = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)

    print("=" * 78)
    print("① 搜 ROM 里指向「中文名表区」的 u32")
    print("=" * 78)
    lo, hi = BASE + 0x71F446, BASE + 0x722000
    hit = np.flatnonzero((pz >= lo) & (pz < hi))
    print(f"  0x{lo:08X}..0x{hi:08X} 区间被引用：{len(hit):,} 处")
    sites = (hit * 4).tolist()
    vals = pz[hit].tolist()
    print(f"  前 20 个引用点：")
    print(f"    {'引用位置':>14} {'值':>14}  该位置原版值")
    for s, v in list(zip(sites, vals))[:20]:
        old = u32(ja, s)
        mark = "" if old == v else "  ← 汉化改的"
        print(f"    0x{BASE+s:08X} 0x{v:08X}  0x{old:08X}{mark}")

    # 找「汉化新加的」引用（原版不是这个值）
    new_refs = [s for s, v in zip(sites, vals) if u32(ja, s) != v]
    print(f"\n  其中「原版不是此值」= 汉化新增引用：{len(new_refs)} 处")
    for s in new_refs[:15]:
        print(f"    0x{BASE+s:08X}  原版值 0x{u32(ja,s):08X}")

    print("\n" + "=" * 78)
    print("② 精确搜名表基址 0x0871F446（含 ±0x100 偏移）")
    print("=" * 78)
    for delta in (0, 4, 8, 0x10):
        target = BASE + 0x71F446 + delta
        h = np.flatnonzero(pz == target)
        if len(h):
            print(f"  0x{target:08X}: {len(h)} 处 → "
                  f"{[f'0x{BASE+x*4:08X}' for x in h[:6]]}")

    # 也搜「0x71F446 但作为基址被 load 后加偏移」
    print(f"\n  放宽：搜 0x0871F4xx / 0x0871F5xx 下界")
    for base_try in (0x71F000, 0x71F246, 0x71F400, 0x71F446, 0x71F500):
        h = np.flatnonzero(pz == BASE + base_try)
        print(f"    0x{BASE+base_try:08X}: {len(h)} 处"
              + (f"  {[f'0x{BASE+x*4:08X}' for x in h[:5]]}" if len(h) else ""))

    # ── ③ 反汇编那几处引用 ─────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 反汇编名表引用点附近的代码")
    print("=" * 78)
    seen = set()
    for s in new_refs[:6]:
        # 反汇编该引用点前 0x40 字节（引用点通常在函数体内的字面量池之后）
        a = BASE + max(0, s - 0x40)
        if a in seen:
            continue
        seen.add(a)
        print(f"\n  ---- 引用点 0x{BASE+s:08X}，向上反汇编 ----")
        for ln in dis(a, zh, 0x80, 14):
            print("    " + ln)

    print("\n" + "=" * 78)
    print("④ 搜中文主文本区 0x086D0000 的引用（文本指针机制）")
    print("=" * 78)
    lo2, hi2 = BASE + 0x6D0000, BASE + 0x722000
    h2 = np.flatnonzero((pz >= lo2) & (pz < hi2))
    print(f"  引用数：{len(h2):,} 处")
    if len(h2):
        # 按引用位置分桶
        sc = Counter(((h2 * 4) // 0x10000).tolist())
        print(f"  引用点分布（64KB，前 10）：")
        for s, c in sc.most_common(10):
            print(f"    0x{BASE+s*0x10000:08X}  {c:>5} 处")
        # 这些引用点是不是「指针表」？
        print(f"\n  前 10 个引用点：")
        for x in h2[:10]:
            s = int(x) * 4
            print(f"    0x{BASE+s:08X} → 0x{pz[x]:08X}"
                  f"  (原版 0x{u32(ja,s):08X})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
