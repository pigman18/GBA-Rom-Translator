#!/usr/bin/env python3
"""调研㉒ 把火红的每个 hook 点反汇编出来 —— 逐点确认它打了什么补丁。

═══════════════════════════════════════════════════════════════════════════
【⑲ 的结果】
═══════════════════════════════════════════════════════════════════════════
只找到 11 个 `ldr rT,[pc,#imm]; bx rT` 且目标与原版不同的点，全部目标落在
0x08005xxx / 0x080D98xx / 0x080F91xx / 0x08FF75xx。

但这**不一定**是全部 hook —— 汉化可能用别的方式插桩：
  ① `bl` 长跳转（FF F7 xx F8）直接改原函数
  ② 直接把函数首几字节改成 `bl`
  ③ 改 GOT/函数指针表（我们看到很多 u32 被改成 0x08EDxxxx / 0x08FFxxxx）
  ④ 改 `bx` 目标（上面 11 个）

所以本脚本换更强的判据：**在被改动的 u32 字面量里找代码指针**。
   · 主文本区之外，汉化把 u32 改成 0x08EDxxxx / 0x08FFxxxx / 0x08E3xxxx 等
   · 这些是「新增代码区」，被 u32 引用的位置就是**函数指针/字面量池**
   · 原版这些 u32 指向原代码 ⇒ 汉化把某个回调整体换掉了

═══════════════════════════════════════════════════════════════════════════
【做法】
═══════════════════════════════════════════════════════════════════════════
1. 逐 u32 对齐比对 zh vs ja，找「原版指向代码区、汉化指向新区」的槽位
2. 这些槽位就是「被替换的函数入口」
3. 用 objdump 对两侧都反汇编，看原函数和补丁函数在做什么

用法：python scripts/research/firered/22_hook_sites_full.py
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
# 已确认的纯文本区（这些区里的 u32 是文本，不是指针）
NEW_TEXT = [(0x6D0000, 0x722000), (0xAF5000, 0xAFB000)]


def in_text(off: int) -> bool:
    return any(lo <= off < hi for lo, hi in NEW_TEXT)


def main() -> int:
    zh = np.frombuffer(FR_ZH.read_bytes(), dtype=np.uint8)
    ja = np.frombuffer(FR_JA.read_bytes(), dtype=np.uint8)
    n = min(len(zh), len(ja))

    m = n // 4 * 4
    pz = zh[:m].view(np.uint32).astype(np.uint64)
    pa = ja[:m].view(np.uint32).astype(np.uint64)

    def is_rom(p: np.ndarray) -> np.ndarray:
        return (p >= BASE) & (p < BASE + n)

    print("=" * 78)
    print("找「函数指针被换成新代码」的槽位")
    print("=" * 78)

    chg = np.flatnonzero(pa != pz)
    print(f"全 ROM u32 槽位 {len(pa):,}，其中值不同 {len(chg):,}")

    # 只看「旧值是 ROM 指针、新值也是 ROM 指针」
    ok = is_rom(pa[chg]) & is_rom(pz[chg])
    slots = chg[ok]
    print(f"  两侧都是 ROM 指针且值不同的：{len(slots):,}")

    old = (pa[slots] - BASE).astype(np.int64)
    new = (pz[slots] - BASE).astype(np.int64)

    # 排除「文本区里的 u32」（文本当成 u32 读出来也会像指针）
    keep = ~np.array([in_text(int(x)) or in_text(int(y))
                      for x, y in zip(old, new)])
    slots, old, new = slots[keep], old[keep], new[keep]
    print(f"  排除文本区里误当指针的：{len(slots):,}")

    # 新值落在哪些区
    print(f"\n  新值分布（按 64KB 格，只列 ≥3 个的）：")
    bins = new // 0x10000
    u, c = np.unique(bins, return_counts=True)
    pairs = sorted(zip(c.tolist(), u.tolist()), reverse=True)
    for cnt, b in pairs:
        if cnt < 3:
            break
        print(f"    0x{BASE+b*0x10000:08X}  {cnt:>5,} 个槽位")

    # 旧值落在哪（原代码区）
    print(f"\n  旧值分布（按 64KB 格，只列 ≥3 个的）：")
    bins_o = old // 0x10000
    uo, co = np.unique(bins_o, return_counts=True)
    pairso = sorted(zip(co.tolist(), uo.tolist()), reverse=True)
    for cnt, b in pairso:
        if cnt < 3:
            break
        print(f"    0x{BASE+b*0x10000:08X}  {cnt:>5,} 个槽位")

    # 关键：新值在「新增代码区」的（> 0x800000 且不在文本区）
    # 先看哪些 64KB 格是「原版基本为空、汉化有内容」
    print("\n" + "=" * 78)
    print("新增代码区探测：原版为空/填充，汉化有大量代码")
    print("=" * 78)
    seg = 0x10000
    nseg = n // seg
    zh_seg = zh[:nseg * seg].reshape(nseg, seg)
    ja_seg = ja[:nseg * seg].reshape(nseg, seg)
    zero_zh = (zh_seg != 0).mean(axis=1)
    zero_ja = (ja_seg != 0).mean(axis=1)
    cand = []
    for i in range(nseg):
        if zero_ja[i] < 0.02 and zero_zh[i] > 0.30:
            cand.append((i, zero_ja[i], zero_zh[i]))
    print(f"  「原版几乎空、汉化有内容」的 64KB 格：{len(cand)} 个")
    for i, zj, zz in cand:
        print(f"    0x{BASE+i*seg:08X}  原版非零 {zj:>5.1%} → 汉化 {zz:>5.1%}")

    # 统计这些格被多少 u32 引用
    newcode_bins = {i for i, _, _ in cand}
    is_newcode = np.array([int(x) // 0x10000 in newcode_bins for x in new])
    print(f"\n  指向这些新代码格的 u32 槽位：{int(is_newcode.sum()):,}")

    if is_newcode.any():
        sl = slots[is_newcode]
        o2 = old[is_newcode]
        n2 = new[is_newcode]
        print(f"\n  前 40 个「函数指针替换」槽位：")
        print(f"    {'槽位 ROM':>14} {'原指向':>12} {'新指向':>12}")
        for s, a, b in list(zip(sl.tolist(), o2.tolist(), n2.tolist()))[:40]:
            print(f"    0x{BASE+s:08X}  0x{BASE+a:08X}  0x{BASE+b:08X}")

    # ── 反汇编新代码区 ───────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("反汇编：新增代码区抽样")
    print("=" * 78)
    TMP.mkdir(parents=True, exist_ok=True)
    objdump = "arm-none-eabi-objdump"
    objcopy = "arm-none-eabi-objcopy"

    rom_bytes = FR_ZH.read_bytes()

    def disasm(off: int, size: int = 0x400, label: str = "") -> str:
        blob = rom_bytes[off:off + size]
        b = TMP / "s.bin"
        e = TMP / "s.elf"
        b.write_bytes(blob)
        subprocess.run([objcopy, "-I", "binary", "-O", "elf32-littlearm",
                        "-B", "arm", "--rename-section", ".data=.text",
                        str(b), str(e)], capture_output=True, check=False)
        r = subprocess.run([objdump, "-d", "--adjust-vma=" + hex(BASE + off),
                            "-M", "force-thumb", str(e)],
                           capture_output=True, text=True)
        return r.stdout

    for i, zj, zz in cand[:4]:
        off = i * seg
        print(f"\n---- 0x{BASE+off:08X} （原版非零 {zj:.1%}，汉化 {zz:.1%}）----")
        txt = disasm(off, 0x200)
        lines = [ln for ln in txt.splitlines()
                 if ln.strip() and not ln.startswith("work")]
        for ln in lines[3:35]:
            print("  " + ln)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
