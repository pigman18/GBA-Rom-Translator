#!/usr/bin/env python3
"""验证 v3 算法：按「最终地址寄存器」追踪，覆盖率是否 100%。

v3 判据：
  1. ldr 找基址寄存器 rBase
  2. ldr 之后找 `adds rX,rX,rBase` → rX
  3. 追踪 rX 的所有移位写入
  4. 取「能整除 old_stride」的那条

预期：87/92 → 应接近 92/92

用法：
    python scripts/research/ruby/stride_v3_verify.py
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

TABLES = [
    ("招式名",         0x1CACFC, 8,  16),
    ("特性名",         0x1CBC44, 8,  16),
    ("属性名",         0x1CBB0C, 5,  10),
    ("道具名",         0x39A648, 40, 80),
    ("图鉴分类名",     0x38474C, 28, 56),
    ("秘密基地装饰名", 0x3C2A44, 28, 56),
]


def main() -> int:
    from meowth.table_stride import rewrite_table_stride

    rom = ROM.read_bytes()

    print("=" * 82)
    print("=== v3：按「最终地址寄存器」追踪 ===")
    print("=" * 82)
    print()
    print(f"{'表':<16} {'ldr':>4} {'识别':>4} {'patch':>6} {'覆盖':>6} {'警告':>4} 状态")
    print("-" * 82)

    total_ldr = total_hit = 0
    all_ok = True
    results = []

    for name, base, old_s, new_s in TABLES:
        r = rewrite_table_stride(rom, base, old_s, new_s, require_full=True)
        total_ldr += r.n_ldrs
        total_hit += r.n_sites
        ok = r.ok
        if not ok:
            all_ok = False
        print(f"{name:<16} {r.n_ldrs:>4} {r.n_sites:>4} {len(r.patches):>6} "
              f"{r.coverage:>5.0%} {len(r.warnings):>4} "
              + ("✅" if ok else "⚠️"))
        for w in r.warnings[:3]:
            print(f"    ⚠️ {w}")
        results.append((name, r))

    print("-" * 82)
    print(f"{'合计':<16} {total_ldr:>4} {total_hit:>4} "
          f"{total_hit / total_ldr:>5.0%}")
    print()

    # 逐表看形态
    print("=== 各表识别出的移位形态 ===")
    for name, r in results:
        if not r.sites:
            print(f"  {name:<16} 无站点")
            continue
        from collections import Counter
        forms = Counter(f"{s.mn}#{s.shift}" for s in r.sites)
        print(f"  {name:<16} " + ", ".join(
            f"{k}×{v}" for k, v in forms.most_common(4)))

    print()
    if all_ok:
        print("✅ 全部站点识别，覆盖率 100%")
        return 0
    print(f"⚠️ 覆盖率 {total_hit}/{total_ldr}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
