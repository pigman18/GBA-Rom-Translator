#!/usr/bin/env python3
"""修正几何表后，重算 7 张表的判定。

已修正的错误（texts.json 给的几何不可信）：
  图鉴分类名：name_offset 应为 0（不是 6），名字用 0x00 结尾
             真实可用宽度 = 6B（元数据从 +6 开始）
             ⇒ 0/343 塞得下，必须放大 stride 28→56

其余表的几何需逐一按同样方式核验：
  1. name_offset 用 ROM 实测（元数据起点）
  2. 结尾符是 0xFF 还是 0x00（eos）
  3. 真实可用宽度

用法：
    python scripts/research/ruby/a2_all_geom_truth.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000

# (表名, 基址, stride, 元素数)
TABLES = [
    ("招式名",         0x1CACFC, 8,  354),
    ("特性名",         0x1CBC44, 8,  77),
    ("属性名",         0x1CBB0C, 5,  18),
    ("道具名",         0x39A648, 40, 348),
    ("图鉴分类名",     0x38474C, 28, 386),
    ("秘密基地装饰名", 0x3C2A44, 28, 120),
    ("树果名",         0x3A1034, 56, 21),
]


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import encode_body

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    # 按模块索引译文
    by_mod: dict[str, list[dict]] = {}
    for e in d.get("entries") or []:
        m = e.get("module") or ""
        by_mod.setdefault(m, []).append(e)

    print(f"{'表':<16} {'stride':>6} {'元数据起':>8} {'结尾符':>7} {'可用':>5} "
          f"{'条数':>5} {'塞得下':>7} {'建议'}")
    print("-" * 90)

    results = []
    for name, base, stride, n in TABLES:
        # 1. 用 build.json 条目地址定位名字起点 → 反推 name_offset
        items = []
        for e in by_mod.get(name) or []:
            if e.get("type") != "replace" or e.get("phrase_code") is None:
                continue
            try:
                a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
            except ValueError:
                continue
            if a >= GBA_BASE:
                a -= GBA_BASE
            items.append((a, e))

        if not items:
            print(f"{name:<16} {'—':>6}  无 F980 条目")
            continue

        addrs = sorted(a for a, _ in items)
        # name_offset = 第一个名字地址 - 表基址（若等差）
        noff = (addrs[0] - base) % stride

        # 2. 元数据起点 = 名字后第一个非零字节
        starts = Counter()
        terminators = Counter()
        for a, e in items:
            try:
                raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
            except ValueError:
                continue
            seg = rom[a:a + stride]
            p = len(raw)
            # 结尾符
            if p > 0 and p <= len(seg):
                terminators[seg[p - 1]] += 1
            while p < len(seg) and seg[p] == 0x00:
                p += 1
            starts[p] += 1

        min_meta = min(starts) if starts else stride
        usable = min_meta
        term = terminators.most_common(1)[0][0] if terminators else 0

        # 3. 塞得下比例
        bodies = [encode_body(cm, e.get("translated") or "")
                  for _, e in items if (e.get("translated") or "")]
        if not bodies:
            print(f"{name:<16} {stride:>6}  无译文")
            continue
        # 结尾符决定是否要把 FF 换成 00
        fit = sum(1 for b in bodies if len(b) <= usable)
        longest = max(len(b) for b in bodies)

        if fit == len(bodies):
            advice = "FIXED"
        else:
            for k in (2, 4, 8):
                if longest <= stride * k - (stride - usable):
                    new_s = stride * k
                    advice = f"SWAP ×{k}→{new_s}"
                    break
            else:
                advice = "VARLEN"

        results.append((name, base, stride, noff, usable, term,
                        len(bodies), fit, longest, advice))
        print(f"{name:<16} {stride:>6} {min_meta:>8} {f'0x{term:02X}':>7} "
              f"{usable:>5} {len(bodies):>5} {fit:>7}  {advice}")

    print()
    print("=== 明细 ===")
    for (name, base, stride, noff, usable, term, cnt, fit, longest, advice) in results:
        print(f"  {name}: base=0x{base:06X} name_off={noff} "
              f"结尾符=0x{term:02X} 可用={usable}B 最长译文={longest}B → {advice}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
