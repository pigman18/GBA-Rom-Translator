#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计 9 张定长表：stride 放大后，结构体内固定偏移会不会错位。

## 为什么必须做这件事（2026-11-05）

实测踩到的硬故障：`bag` 场景 translated 侧在第 2 步后彻底卡死
（`[ERR] 输入回调停摆 fr=7946 last_tick=4945 idx=36/138`）。

根因不在文本编码，而在表结构：

    原版 entry0 @0x0839A648  (stride 40)
      +00  ac ac ac ac ac ac ac ac   ← 名字 8B
      +08  ff                        ← EOS
      +09  00 00 00 00 00 00 00      ← 填充
      +10  3f a6 39 08               ← ★ 指针字段（指向名字）
      +14  00 00 01 04
      +18  79 56 0c 08               ← ★ 另一个指针字段
      +20  ~

    新表 @0x09EB80B0          (new_stride 80)
      +00  ac ac ac ac ac ac ac ac
      +08  ff ff ff ... ff ×48       ← 名字可用区被撑到 49B
      +38  ...                       ← 元数据整体后移 0x30
      +48  3f a6 39 08

游戏代码按**硬编码偏移**读这些字段：

    080A53FC  ldrb r0, [r1, #0xe]
    080A5420  ldrb r0, [r1, #0xf]
    080A538E（×40 遍历）后 +0x10 取名字指针

stride 放大后 `[r1, #0x10]` 读到的是 FF FF FF FF（名字填充区），
游戏把它当指针解引用 ⇒ 卡死在读输入的循环里。

⇒ **只有「纯名字表」（整条 entry 就是名字 + EOS，没有其它字段）才允许
   原地扩大 stride。带元数据的结构体，放大 stride 必然砸坏字段偏移。**

本脚本按 ROM 字节独立核实每张表属于哪一类，输出可执行结论。

用法：
    python scripts/research/ruby/audit_table_meta.py
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
GAME = "POKEMON_RUBY_AXVJ00"
ROM = ROOT / "roms" / "origin" / f"{GAME}.gba"

# 与 scripts/research/ruby/emit_table_data.py 的 TABLES 保持一致
TABLES = [
    # name,          base,      stride, n,   name_offset, usable
    ("招式名",        0x1CAD04,  8,  354,  0,  8),
    ("图鉴分类名",     0x384746, 28,  386,  6,  6),
    ("道具名",        0x39A648, 40,  348,  0,  9),
    ("秘密基地装饰名",  0x3C2A44, 28,  120, 13, 10),
    ("特性名",        0x1CBC44,  8,   77,  0,  8),
    ("属性名",        0x1CBB0C,  5,   18,  0,  5),
    ("宝可梦名",       0x1CA354,  6,  412,  0,  6),
    ("特性说明",       0x1CBEB4, 19,   78,  0, 19),
    ("树果名",        0x3A1034, 28,   43,  0, 10),
]


def classify(rom: bytes, base: int, stride: int, n: int,
             noff: int, usable: int) -> dict:
    """判断这张表是「纯名字表」还是「带元数据的结构体」。

    判据（全部基于 ROM 字节，不采信配置）：
      · meta 区 = [noff+usable, stride) 的字节；
      · 若 meta 区**在任何一项里出现过指针形态的 u32**（0x08xxxxxx），
        或出现过非 EOS 填充的语义数据，则视为结构体字段 ⇒ 不可扩大 stride。
      · 若 meta 区在所有项里恒为 EOS/0x00 填充 ⇒ 纯名字表，可扩。
    """
    meta_len = stride - noff - usable
    ptr_hits = 0
    nonzero_hits = 0
    eos_vals = {0x00, 0xFF}
    samples = []

    for i in range(min(n, 400)):
        off = base + i * stride + noff + usable
        meta = rom[off:off + meta_len]
        if not meta:
            continue
        if len(meta) >= 4:
            for k in range(0, len(meta) - 3, 2):
                v = struct.unpack_from("<I", meta, k)[0]
                if 0x08000000 <= v < 0x0A000000:
                    ptr_hits += 1
                    if len(samples) < 3:
                        samples.append((i, k, f"0x{v:08X}"))
                    break
        if any(b not in eos_vals for b in meta):
            nonzero_hits += 1

    kind = "PURE_NAME" if (ptr_hits == 0 and nonzero_hits == 0) else "STRUCT_META"
    return {
        "name_offset": noff, "usable": usable, "meta_len": meta_len,
        "kind": kind, "ptr_hits": ptr_hits, "nonzero_hits": nonzero_hits,
        "samples": samples,
    }


def main() -> int:
    if not ROM.is_file():
        print(f"[ERR] ROM 不存在: {ROM}")
        return 3
    rom = ROM.read_bytes()

    print(f"{'表':<16}{'stride':>7}{'n':>5}{'meta':>6}  {'类型':<12}"
          f"{'指针命中':>8}{'非填充':>7}  结论")
    print("-" * 92)
    rows = []
    for name, base, stride, n, noff, usable in TABLES:
        r = classify(rom, base, stride, n, noff, usable)
        if r["kind"] == "PURE_NAME":
            verdict = "可扩 stride"
        else:
            verdict = "★ 禁止扩 stride（改元数据偏移会砸坏字段）"
        print(f"{name:<16}{stride:>7}{n:>5}{r['meta_len']:>6}  "
              f"{r['kind']:<12}{r['ptr_hits']:>8}{r['nonzero_hits']:>7}  {verdict}")
        rows.append({"name": name, "base": f"0x{base:X}", "stride": stride,
                     "n": n, **r, "verdict": verdict})

    print()
    bad = [r for r in rows if r["kind"] == "STRUCT_META"]
    if bad:
        print("★ 带元数据、禁止原地扩 stride 的表：")
        for r in bad:
            print(f"  · {r['name']}  (stride {r['stride']}, meta {r['meta_len']}B)")
            for sample in r["samples"]:
                print(f"      entry[{sample[0]}] +{sample[1]}: {sample[2]}")
        print()
        print("  这些表如果必须容纳更长的中文名，只能走：")
        print("    a) 整表换成「指针数组 + 变长串」（火红做法，需改 index×stride 代码）；")
        print("    b) 保持 stride 不变，名字区用原长（译文必须放得下）；")
        print("    c) 只扩「纯名字表」的 stride，结构体表另想办法。")
    else:
        print("9 张表全部为纯名字表，可安全扩 stride。")

    out = ROOT / "work" / "table_meta_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[out] {out}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
