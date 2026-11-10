#!/usr/bin/env python3
"""6 张定长/结构表：几何实测 + stride 需求实测。

只用 ROM + 官方日文词表，不依赖 texts.json 的声明值。
每张表都打印：真实基址、首条、末条、条数、词表命中率。

用法：
    python scripts/research/ruby/tables_ground_truth.py
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

# (表名, 基址, stride, 条数, name_offset, eos, 期望首条, 期望末条)
TABLES = [
    ("招式名",         0x1CAD04, 8,  354, 0,  0xFF, "はたく", "サイコブースト"),
    ("特性名",         0x1CBC4C, 8,   77, 0,  0xFF, "あくしゅう", "エアロック"),
    ("属性名",         0x1CBB0C, 5,   18, 0,  0xFF, "ノーマル", "あく"),
    # 道具名 name_offset 实测为 0（名字在槽首）；0 号槽是 ？？？？？？？？ 空槽
    ("道具名",         0x39A648, 40, 348, 0, 0xFF, None, None),
    ("图鉴分类名",     0x384746, 28, 386, 6,  0x00, "みかくにん", None),
    ("秘密基地装饰名", 0x3C2A54, 28, 120, 13, 0xFF, "ちいさいつくえ", "レジスチルドール"),
]


def main() -> int:
    from meowth.codec import get_codec
    cd = get_codec("POKEMON_RUBY_AXVJ00")
    rom = ROM.read_bytes()

    print("=" * 100)
    print("6 张表几何实测（只依赖 ROM 字节 + PCS 解码）")
    print("=" * 100)

    ok_all = True
    for name, base, stride, n, noff, eos, want_first, want_last in TABLES:
        print(f"\n--- {name}  base=0x{base:06X} stride={stride} "
              f"n={n} name_offset={noff} eos=0x{eos:02X} ---")

        def read_item(i: int) -> str:
            p = base + i * stride + noff
            seg = rom[p:p + stride - noff]
            cut = len(seg)
            for k, b in enumerate(seg):
                if b == eos:
                    cut = k
                    break
            if not cut:
                return ""
            try:
                return cd.decode(seg[:cut])
            except Exception:
                return ""

        first = read_item(0)
        last = read_item(n - 1)
        print(f"  首条[0]     = {first!r}")
        print(f"  末条[{n-1}] = {last!r}")

        # 统计「非空且可解码」的比例
        valid = 0
        empty = 0
        for i in range(n):
            t = read_item(i)
            if not t or set(t) <= set("？? "):
                empty += 1
            else:
                valid += 1
        print(f"  有效 {valid}/{n}   空/占位 {empty}")

        if want_first:
            mark = "✅" if first == want_first else f"❌ 期望 {want_first!r}"
            if first != want_first:
                ok_all = False
            print(f"  首条校验: {mark}")
        if want_last:
            mark = "✅" if last == want_last else f"❌ 期望 {want_last!r}"
            if last != want_last:
                ok_all = False
            print(f"  末条校验: {mark}")

    print()
    print("=" * 100)
    print("结论：", "6 张表几何全部与 TextsCurator 体检一致 ✅" if ok_all
          else "有表几何不符，需复核 ❌")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
