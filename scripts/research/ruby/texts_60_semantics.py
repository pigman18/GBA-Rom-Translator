#!/usr/bin/env python3
"""texts_60: 0x3B3E64 表的语义判定 —— 22 项是「按 ID 索引」还是「按假名索引」。

关键观察（texts_59）：
  [0]  ''                (0x3B2670，是数据区不是词条)
  [1]  'きみにきめた！'
  [2]  'あく'
  [3]  'あいしょう'
  ...
  [20] '４６４９'

这 22 项**不是按假名排序的**（「きみにきめた！」在最前，「あく」在其后）。
而词库本体 926 条是**按假名排序**的。

所以这张表 = 「某功能的选项列表」，从按假名排序的词库里挑了 22 个点。

本脚本验证「按 ID 索引」假设：
  · 把 22 项的词序与词库本体顺序对比
  · 看 22 项的地址是否单调递增（若是，说明是按词库顺序挑的连续段）
  · 判断 22 的语义规模（对照已知表）

用法: python scripts/research/ruby/texts_60_semantics.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000
TABLE = 0x3B3E64

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402


def read_str(rom: bytes, off: int, limit: int = 64) -> str:
    for i in range(off, min(len(rom), off + limit)):
        if rom[i] == 0xFF:
            return decode_pcs(rom[off:i + 1])
    return ""


def main() -> int:
    rom = ROM_PATH.read_bytes()

    items = []
    for k in range(22):
        v = struct.unpack_from("<I", rom, TABLE + k * 4)[0]
        if not (BASE <= v < BASE + len(rom)):
            break
        t = v - BASE
        items.append((k, t, read_str(rom, t)))

    print("=" * 112)
    print("22 项明细（看地址是否单调递增）")
    print("=" * 112)
    prev = None
    mono = True
    for k, t, s in items:
        arrow = ""
        if prev is not None:
            if t > prev:
                arrow = f"  +0x{t-prev:X}"
            else:
                arrow = f"  -0x{prev-t:X}  ← 非递增"
                mono = False
        print(f"  [{k:>2}] 0x{t:06X} {arrow:<14} {s!r}")
        prev = t
    print(f"\n  地址单调递增: {'是' if mono else '否'}")

    print()
    print("=" * 112)
    print("「按词库顺序连续取段」假设检验")
    print("=" * 112)
    addrs = sorted(t for _, t, _ in items)
    gaps = [addrs[i + 1] - addrs[i] for i in range(len(addrs) - 1)]
    print(f"  排序后相邻间隔: {[hex(g) for g in gaps]}")
    uniform = len(set(gaps)) == 1
    print(f"  间隔是否等距: {'是，步长 ' + hex(gaps[0]) if uniform else '否 —— 不是等距数组'}")

    print()
    print("=" * 112)
    print("内容语义（按词性归类）")
    print("=" * 112)
    import re
    cats = {"短词/称呼": [], "句子": [], "单字/符号": [], "空/无效": []}
    for k, t, s in items:
        if not s or not s.strip("！？　 "):
            cats["单字/符号" if s else "空/无效"].append(s)
        elif "！" in s or "。" in s or len(s) >= 6:
            cats["句子"].append(s)
        else:
            cats["短词/称呼"].append(s)
    for c, v in cats.items():
        print(f"  {c}: {len(v)}  {v}")

    print()
    print("=" * 112)
    print("对照：22 这个数字与已知表规模")
    print("=" * 112)
    known = {"性格": 25, "华丽大赛属性": 4, "属性": 18, "图鉴分类": 386,
             "特性": 77, "招式": 354, "训练家 class": 60}
    for k, v in known.items():
        print(f"  {k:<14} {v}")
    print(f"  本表 22 项 —— 与「属性 18」和「性格 25」都不吻合")
    print()
    print("  内容混合度很高（句子 + 短词 + 单字 + 数字'４６４９'）")
    print("  → 更像「调试/测试用的样本集合」或「某种通用词表的取样索引」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
