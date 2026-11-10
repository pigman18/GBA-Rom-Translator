#!/usr/bin/env python3
"""先定 stride 方案（必须是旧 stride 的 2 的幂倍），再跑自动注入。

之前算错的地方：
  属性名 5 → 17：17/5 = 3.4，不是整数，无法用移位实现
  属性名 5 → 20：20/5 = 4 = 2^2 ✅ 可行

各表正确的新 stride（都取 2 的幂倍）：
  招式名        8 → 32   (×4, 可用 32B, 最长 21B ✓)
  特性名        8 → 32   (×4, 可用 32B, 最长 17B ✓)
  属性名        5 → 20   (×4, 可用 20B, 最长 13B ✓)
  道具名       40 → 80   (×2, 可用 49B, 最长 29B ✓)
  图鉴分类名   28 → 56   (×2, 可用 34B, 最长 17B ✓)
  秘密基地装饰名 28 → 56  (×2, 可用 38B, 最长 29B ✓)

用法：
    python scripts/research/ruby/a2_stride_fix_verify.py
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

# (表名, 基址, 旧stride, 新stride, 旧可用, 最长译文, 基准站点数)
TABLES = [
    ("招式名",         0x1CACFC, 8,  32, 8,  21, 40),
    ("特性名",         0x1CBC44, 8,  32, 8,  17, 3),
    ("属性名",         0x1CBB0C, 5,  20, 5,  13, 3),
    ("道具名",         0x39A648, 40, 80, 9,  29, 14),
    ("图鉴分类名",     0x38474C, 28, 56, 6,  17, 5),
    ("秘密基地装饰名", 0x3C2A44, 28, 56, 10, 29, 22),
]


def main() -> int:
    from meowth.table_stride import rewrite_table_stride

    rom = ROM.read_bytes()

    # 先校验每个方案合法
    print("=== stride 方案校验 ===")
    print(f"{'表':<16} {'旧':>4} {'新':>4} {'倍数':>5} {'2幂':>4} "
          f"{'新可用':>6} {'最长':>4} {'够用':>4}")
    print("-" * 66)
    for name, base, old_s, new_s, old_usable, longest, _ in TABLES:
        ratio = new_s // old_s
        is_pow2 = ratio > 0 and (ratio & (ratio - 1)) == 0
        meta = old_s - old_usable
        new_usable = new_s - meta
        fit = longest <= new_usable
        print(f"{name:<16} {old_s:>4} {new_s:>4} {ratio:>5} "
              f"{'✅' if is_pow2 else '❌':>4} {new_usable:>6} "
              f"{longest:>4} {'✅' if fit else '❌':>4}")

    # 再跑自动注入
    print()
    print("=== 自动注入：全量站点扫描 ===")
    print(f"{'表':<16} {'基准':>5} {'找到':>5} {'patch':>6} {'警告':>5} {'状态'}")
    print("-" * 62)

    total_expect = total_found = 0
    all_ok = True
    plans = []

    for name, base, old_s, new_s, _ou, _ln, expect in TABLES:
        r = rewrite_table_stride(rom, base, old_s, new_s,
                                 expect_min_sites=expect, dry_run=True)
        total_expect += expect
        total_found += r.n_sites
        ok = r.n_sites >= expect and not r.warnings
        if not ok:
            all_ok = False
        print(f"{name:<16} {expect:>5} {r.n_sites:>5} {len(r.patches):>6} "
              f"{len(r.warnings):>5} {'✅' if ok else '⚠️'}")
        for w in r.warnings[:4]:
            print(f"    ⚠️ {w}")
        plans.append((name, r, expect))

    print("-" * 62)
    print(f"{'合计':<16} {total_expect:>5} {total_found:>5}")

    print()
    print("=== 覆盖率 ===")
    for name, r, expect in plans:
        rate = r.n_sites / expect if expect else 0
        bar = "█" * int(rate * 20)
        print(f"  {name:<16} {r.n_sites:>3}/{expect:<3} {rate:>5.0%} {bar}"
              + ("  ✅" if rate >= 1.0 else "  ⚠️"))

    print()
    if all_ok:
        print("✅ 全部站点覆盖，可以生成自动注入")
        return 0
    print("⚠️ 仍有遗漏，需继续修正算法")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
