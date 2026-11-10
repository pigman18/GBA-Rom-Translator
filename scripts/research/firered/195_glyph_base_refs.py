#!/usr/bin/env python3
"""调研(195) 从「字形码 → 位图」的取用函数反推字库。

═══════════════════════════════════════════════════════════════════════════
【(192)(193) 已解读清楚的部分】
═══════════════════════════════════════════════════════════════════════════
0x081DB660 是**文本转码器**（把 F6/F7 压缩码展开成线性字节流），不是字库：

  0x081DB698（F7 分支）:
      adds r5,#1 ; ldrb r0,[r5]     ; r0 = F7 后的 hi
      lsls r0,r0,#2                 ; hi * 4
      adds r0,r0,r7                 ; r7 = 0x0203F2C0
      ldr  r1,[r0]                  ; r1 = 表[hi]  ← EWRAM 里的指针表
      ; 然后把这串字节复制到输出直到 0xFF

  ⇒ 0x0203F2C0 是「hi 页 → 字符串」的映射表（11 项，因 hi 只用 0x00-0x0A）

0x081DB6C0（另一段）:
      cmp r1,#0x58 ; subs r1,#0x58 ; cmp r1,#0x6C ; bhi
      ldr r2,[pc,#0x10]  ; r2 = 0x08FE5100
      lsls r1,r1,#2
      ldr  r1,[r2,r1]    ; 108 项分派表 → 0x08FE5100
  ⇒ 0x08FE5100 我已 dump 过：**每项指向一段 F7 文本**（不是字形）

结论：**这两条路径处理的是文本，不是字形。**

【现在要找的是「字形码 → 位图地址」】
必须先知道「一个字形码在字库里的偏移公式」。
从 0x081DB630 已知：
      ldr r1,[pc]        ; r1 = 0x08B64A40
      subs r1, r4, r1    ; r1 = glyph_ptr - 0x08B64A40
      cmp r1,#0xA0  →  12 / 10 / 2 分档

⇒ **r4 是一个指向 0x08B64A40+offset 的指针**，该 offset 决定字宽。
   字库的地址公式必然与 0x08B64A40 有关。

【本脚本】
 S1 全 ROM 找所有「把 0x08B64A40 当基址」的代码（字面量 0x08B64A40）
 S2 找所有引用 0x08B64A40 附近区间（±0x20000）的字面量
 S3 对这些引用点反汇编，看加减乘除的常数（stride）
 S4 把 0x08B64A40 起 64KB 按「已知字宽 10/2/12」推断的行结构渲染
 S5 用已知 8x16 字形去该区**按不同起点**做模糊匹配（允许 1~2 字节差异）

用法：python scripts/research/firered/195_glyph_base_refs.py
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "base195"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
GLYPH_BASE = 0x08B64A40
SCREEN_BASE = 0xF000


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def entry(vr: bytes, r: int, c: int) -> int:
    return struct.unpack_from("<H", vr, SCREEN_BASE + (r * 32 + c) * 2)[0]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    zh = ROM_ZH.read_bytes()
    ja = ROM_OR.read_bytes()
    N = len(zh)

    # ── S1 谁引用了 0x08B64A40（含附近 ±0x40000 的基址类常量）──
    print("=" * 78)
    print("S1 全 ROM 里作为 u32 出现的「0x08B64A40 附近」常量")
    print("=" * 78)
    m = N // 4 * 4
    words = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)
    lo, hi = GLYPH_BASE - 0x20000, GLYPH_BASE + 0x80000
    idx = np.flatnonzero((words >= lo) & (words < hi))
    print(f"  命中 {len(idx)} 处（0x{lo:08X}..0x{hi:08X}）")
    vals = Counter()
    for i in idx.tolist()[:2000]:
        vals[int(words[i])] += 1
    print("  出现的常量值（Top 20）：")
    for v, n in vals.most_common(20):
        off = v - BASE
        nf = sum(1 for b in ja[off:off + 64] if b == 0xFF) if 0 <= off < N - 64 else -1
        print(f"    0x{v:08X}  x{n}   原版该处 64B 中 FF={nf}")

    # ── S2 精确引用 GLYPH_BASE 的位置 ────────────────────
    print("\n" + "=" * 78)
    print(f"S2 精确引用 0x{GLYPH_BASE:08X} 的位置")
    print("=" * 78)
    needle = struct.pack("<I", GLYPH_BASE)
    pos = zh.find(needle)
    hits = []
    while pos >= 0:
        hits.append(pos)
        pos = zh.find(needle, pos + 1)
    print(f"  {len(hits)} 处：")
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    for h in hits[:20]:
        addr = BASE + h
        print(f"    0x{addr:08X}")
        # 反汇编周边（往前 32 字节开始，找用法）
        s = max(0, h - 40)
        for ins in md.disasm(zh[s:h + 8], BASE + s):
            mark = " <<" if ins.address == addr else ""
            print(f"        0x{ins.address:08X}  {ins.mnemonic:<8} "
                  f"{ins.op_str}{mark}")

    # ── S3 GLYPH_BASE 区域的整体画像 ─────────────────────
    print("\n" + "=" * 78)
    print(f"S3 0x{GLYPH_BASE:08X} 起 64KB 的分段画像")
    print("=" * 78)
    off0 = GLYPH_BASE - BASE
    for k in range(0, 0x10000, 0x800):
        seg = zh[off0 + k:off0 + k + 0x800]
        if len(seg) < 0x800:
            break
        c = Counter(seg)
        nf = c.get(0xFF, 0) / 0x800
        ent = -sum((v / 0x800) * np.log2(v / 0x800) for v in c.values())
        # nibble 集中度
        hi4 = set(v for v, _ in Counter(b >> 4 for b in seg).most_common(4))
        lo4 = set(v for v, _ in Counter(b & 0x0F for b in seg).most_common(4))
        j = sum(1 for b in seg if (b >> 4) in hi4 and (b & 0x0F) in lo4) / 0x800
        print(f"    +0x{k:05X}  FF={nf:>5.1%} ent={ent:>4.1f} "
              f"joint={j:.3f} 值种类={len(c):>3}")

    # ── S4 模糊匹配：允许每块有少量字节不同 ───────────────
    print("\n" + "=" * 78)
    print("S4 模糊匹配：VRAM 已知 8x8 块 vs GLYPH_BASE 区（允许 <=4 字节差异）")
    print("=" * 78)
    vr = (SNAP / "vram.bin").read_bytes()
    text_rows = [r for r in range(20)
                 if any(((entry(vr, r, c) >> 12) & 0xF) == 15 for c in range(30))]
    known = []
    for r in range(text_rows[0], 19, 2):
        for c in range(30):
            et = entry(vr, r, c)
            if ((et >> 12) & 0xF) != 15:
                continue
            eb = entry(vr, r + 1, c)
            for e in (et, eb):
                t = e & 0x3FF
                blob = vr[t * 32:t * 32 + 32]
                if len(blob) < 32:
                    continue
                mm = tile_nibs(blob)
                if int((mm == 12).sum()) + int((mm == 11).sum()) >= 4:
                    known.append(blob)
    known = list(dict.fromkeys(known))
    print(f"  已知字形块 {len(known)} 个（去重）")

    zone = zh[off0:off0 + 0x10000]
    best = []
    for gi, blob in enumerate(known):
        for o in range(0, len(zone) - 32, 4):
            same = 0
            diff = 0
            for k in range(32):
                if zone[o + k] == blob[k]:
                    same += 1
                else:
                    diff += 1
                    if diff > 4:
                        break
            if diff <= 4:
                best.append((gi, o, 32 - diff))
    print(f"  模糊命中 {len(best)} 处")
    for gi, o, sc in best[:30]:
        print(f"    字形#{gi} @ 0x{GLYPH_BASE + o:08X}  相同 {sc}/32")

    (OUT / "base.json").write_text(
        json.dumps({"refs": [BASE + h for h in hits],
                    "const_vals": [[v, n] for v, n in vals.most_common(60)],
                    "fuzzy": [[g, o, s] for g, o, s in best[:200]]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'base.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
