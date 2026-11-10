#!/usr/bin/env python3
"""调研⑲ 枚举火红的**全部 hook 点** —— 这就是「汉化的全部逻辑」的入口清单。

═══════════════════════════════════════════════════════════════════════════
【为什么这就是答案】
═══════════════════════════════════════════════════════════════════════════
已知火红几乎没重写引擎（低地址差异 0.4%）。它做汉化的方式就是
在关键函数入口插一个跳转，跳到 ROM 尾部的新代码。

实测到的补丁形态（Thumb）：

    0x080494A0  汉化: ff e7 | 03 48 31 1c 03 4a 7e f1 ee fa | 2e e0 ...
                ↑自跳转      ↑ r0=... r1=...  ↑ call 新代码

    0x0809DBE0  汉化: 01 4b | 21 1c | 02 e0 | c0 46 | 2b d8 ff 08 | 6b f0 b7 fb
                     └┬┘  └r1=r4┘ └b.n ┘ └nop ┘ └─ 字面量 ─┘ └── bl 新代码 ──┘
                  ldr r3,[pc,#4]; bx r3 → 跳到 0x08FFD82B

更常见的是 inline 补丁：`01 4b 18 47 c0 46 <u32>`
    = ldr r3,[pc,#4] ; blx r3 ; nop ; .word <目标>

⇒ 只要把全 ROM 的 `18 47`（bx/blx r3）前的 `ldr r3,[pc,#imm]` 都解出来，
  再过滤「目标落在新增代码区」的，就是**全部 hook 点**。

═══════════════════════════════════════════════════════════════════════════
【输出】
═══════════════════════════════════════════════════════════════════════════
  · 每个 hook 点：site 地址 / 目标地址
  · 目标按区聚合（看新增代码分布在哪些段）
  · 对每个目标，dump 前 32 字节，供后续反汇编

用法：python scripts/research/firered/19_hook_sites.py
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

BASE = 0x08000000
TEXT_LO, TEXT_HI = 0x6D0000, 0x722000      # 已确认纯文本区（含区2）


def u32(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "little")


def decode_ldr_bx(rom: bytes, o: int) -> list[tuple[int, int, str]]:
    """从偏移 o 起找 `ldr rX,[pc,#imm]` + `bx/blx` 模式。

    Thumb: LDR(rt) = 0100 1 Rt:3 imm8   → bytes: [imm8, 0x48|Rt]
           BX Rm    = 010001 11 000 Rm:3 → bytes: [0x70|Rm, 0x47]
           BLX Rm   = 010001 11 100 Rm:3 → bytes: [0x80|Rm, 0x47]
    我们只关心 Rm == 3（r3），因为编译器把函数指针放 r3 时最常见，
    但为了不漏，全扫。
    """
    out = []
    n = len(rom)
    i = o
    while i + 6 < n:
        b0, b1 = rom[i], rom[i + 1]
        if (b0 & 0xF8) == 0x48 and (b1 & 0xFF) == 0x47:
            rt = b0 & 0x07
            imm = b1  # 实际是 b0 的高 5 位… 纠正见下
            pass
        i += 1
    return out


def scan_hooks(zh: bytes, ja: bytes) -> list[dict]:
    """扫 `[imm8, 0x48|Rt] [0x70|Rm,0x47]` 或 `[imm8,0x48|Rt]` 后跟 bx rN。"""
    hooks = []
    n = len(zh)
    for i in range(0, n - 8):
        # ldr rT,[pc,#imm4] : 0x4800 | T:3 | imm:8  → low byte = imm8, high = 0x48|T
        lo, hi_ = zh[i], zh[i + 1]
        if not (0x48 <= hi_ <= 0x4F):
            continue
        rt = hi_ - 0x48
        imm = lo * 4
        # 下一条必须是 bx/bxl rT（0x47xx, low nibble = 0x0 for bx, 0x8 for blx?）
        nxt_lo, nxt_hi = zh[i + 2], zh[i + 3]
        if nxt_hi != 0x47:
            continue
        rm = nxt_lo & 0x07
        kind = "blx" if nxt_lo & 0x08 else "bx"
        if rm != rt:
            continue
        # 字面量地址 = ALIGN4(i+4) + imm
        lit = ((i + 4) // 4) * 4 + imm
        if lit + 4 > n:
            continue
        tgt = u32(zh, lit)
        if not (BASE <= tgt < 0x0A000000):
            continue
        toff = tgt - BASE
        # 只保留「目标与原版不同」的——原版里这也是合法跳转（引擎自己的）
        old = u32(ja, lit)
        hooks.append({
            "site": i, "lit": lit, "tgt": tgt, "toff": toff,
            "old": old, "kind": kind, "changed": old != tgt,
        })
    return hooks


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    print("=" * 76)
    print("火红全部 indirect 跳转（ldr rT,[pc,#imm] ; bx/blx rT）")
    print("=" * 76)

    hooks = scan_hooks(zh, ja)
    print(f"扫到 {len(hooks):,} 个跳转点")

    chg = [h for h in hooks if h["changed"]]
    print(f"其中**字面量与目标与原版不同**：{len(chg):,} 个  ← 这些是汉化加的")

    # 目标落在哪
    print(f"\n--- 汉化新增跳转的目标分布（按 64KB 段）---")
    seg = Counter(h["toff"] // 0x10000 for h in chg)
    for s, n in sorted(seg.items()):
        lo = s * 0x10000
        mark = ""
        if TEXT_LO <= lo < TEXT_HI:
            mark = "  ← 纯文本区（假跳转，字面量被当文本读到）"
        print(f"  ROM 0x{BASE+lo:08X}  {n:>4} 个{mark}")

    # 排除落在文本区的（那些是文本里恰好出现的字节模式）
    real = [h for h in chg if not (TEXT_LO <= h["toff"] < TEXT_HI)]
    print(f"\n排除文本区后，**真正的 hook 点：{len(real):,} 个**")

    print(f"\n--- 真 hook 的目标按 64KB 段 ---")
    seg2 = Counter(h["toff"] // 0x10000 for h in real)
    for s, n in sorted(seg2.items()):
        lo = s * 0x10000
        end = lo + 0x10000
        print(f"  0x{BASE+lo:08X}..0x{BASE+end:08X}  {n:>4} 个")

    print(f"\n--- 前 60 个 hook 点（site → 目标）---")
    print(f"  {'hook site':>12} {'跳转':>5} {'目标地址':>12}  目标前 24 字节")
    for h in real[:60]:
        t = h["toff"]
        blob = zh[t:t + 24].hex(' ')
        print(f"  0x{BASE+h['site']:08X} {h['kind']:>5} 0x{BASE+t:08X}  {blob}")

    # 目标区间聚合：连着的一批目标说明是一大块新代码
    tgts = sorted(h["toff"] for h in real)
    if tgts:
        runs = []
        s = p = tgts[0]
        for x in tgts[1:]:
            if x - p <= 0x1000:
                p = x
            else:
                runs.append((s, p))
                s = p = x
        runs.append((s, p))
        print(f"\n--- 目标聚集区（间隔 ≤4KB 合并）：{len(runs)} 个 ---")
        for s, e in runs:
            cnt = sum(1 for x in tgts if s <= x <= e)
            print(f"  0x{BASE+s:08X}..0x{BASE+e:08X}  {cnt:>3} 个目标  "
                  f"跨度 {(e-s)//1024+1}KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
