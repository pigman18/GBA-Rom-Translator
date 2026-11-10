#!/usr/bin/env python3
"""用「100% 合规」的可用宽度，重算 7 张表的处理方案。

可用宽度（a2_width_by_decode.py 实测，全部 100% 合规）：
  招式名        8 / stride 8
  特性名        8 / stride 8
  属性名        5 / stride 5
  道具名        9 / stride 40   ← 名字只占前 9B，后面是元数据
  图鉴分类名    6 / stride 28
  秘密基地装饰名 10 / stride 28
  树果名        4 / stride 28

注意：道具名 stride=40 但名字只用 9B，剩余 31B 是元数据。
      所以「放大 stride」对道具名无意义 —— 名字需要更长时，
      要么用剩余空间（若元数据结构允许），要么换结构。

用法：
    python scripts/research/ruby/a2_plan_v2.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"

# (表名, base, stride, usable, n, eos)
TABLES = [
    ("招式名",         0x1CACFC, 8,  8,  354, 0xFF),
    ("特性名",         0x1CBC44, 8,  8,  77,  0xFF),
    ("属性名",         0x1CBB0C, 5,  5,  18,  0xFF),
    ("道具名",         0x39A648, 40, 9,  348, 0xFF),
    ("图鉴分类名",     0x38474C, 28, 6,  386, 0x00),
    ("秘密基地装饰名", 0x3C2A44, 28, 10, 120, 0xFF),
    ("树果名",         0x3A1050, 28, 4,  43,  0xFF),
]


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import encode_body

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    by_mod: dict[str, list] = {}
    for e in d.get("entries") or []:
        if e.get("type") != "replace" or e.get("phrase_code") is None:
            continue
        by_mod.setdefault(e.get("module") or "", []).append(e)

    print(f"{'表':<16} {'stride':>6} {'可用':>5} {'条数':>5} {'最长':>5} "
          f"{'塞得下':>7} {'方案'}")
    print("-" * 78)

    for name, base, stride, usable, n, eos in TABLES:
        items = by_mod.get(name) or []
        if not items:
            print(f"{name:<16} {stride:>6} {usable:>5}  无 F980 条目")
            continue

        bodies = []
        for e in items:
            t = e.get("translated") or ""
            if not t:
                continue
            b = encode_body(cm, t)
            # 该表用 eos 结尾，把 FF 换成 eos
            if eos != 0xFF and b.endswith(b"\xFF"):
                b = b[:-1] + bytes([eos])
            bodies.append(b)

        if not bodies:
            print(f"{name:<16} {stride:>6} {usable:>5}  无译文")
            continue

        fit = sum(1 for b in bodies if len(b) <= usable)
        longest = max(len(b) for b in bodies)

        # 方案
        if fit == len(bodies):
            plan = "FIXED"
        else:
            # 放大 stride 是否有效？看名字区能否扩展
            # 若 usable < stride，说明名字区后面是元数据，
            # 放大 stride 可以按比例扩大名字区
            meta = stride - usable
            need = longest
            plan = None
            for k in (2, 4, 8):
                new_stride = stride * k
                new_usable = new_stride - meta
                if need <= new_usable:
                    pow2 = (new_stride & (new_stride - 1)) == 0
                    plan = (f"SWAP ×{k}→{new_stride}"
                            f"（可用{new_usable}B,{'2幂' if pow2 else '非2幂'}）")
                    break
            if plan is None:
                plan = "VARLEN"

        print(f"{name:<16} {stride:>6} {usable:>5} {len(bodies):>5} "
              f"{longest:>5} {fit:>7}  {plan}")

    print()
    print("=== 关键观察 ===")
    print("  道具名 stride=40 但名字只用 9B（余 31B 元数据）")
    print("  → 可考虑「不放大 stride，改用剩余空间」：")
    print("    若元数据只在 +9..+40 的固定位置，名字最多可扩到 31B 而不冲突")
    print("    这需要反汇编确认元数据的确切布局")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
