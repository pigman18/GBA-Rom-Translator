#!/usr/bin/env python3
"""验证：统一用符号执行后，各表的「要改站点」是否都被精确识别。

判据（比覆盖率更硬）：
  - 每个 K==旧stride 的站点 → 必须生成 patch
  - 每个 patch 的移位指令 → 必须真的作用于该站点的 index
  - 改完后重扫 → K 应全部变成新 stride，无残留旧值

用法：
    python scripts/research/ruby/stride_v4_verify.py
"""
from __future__ import annotations

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

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

# (表名, 基址, 旧stride, 新stride, 最长译文)
TABLES = [
    ("招式名",         0x1CACFC, 8,  32, 21),
    ("特性名",         0x1CBC44, 8,  32, 17),
    ("属性名",         0x1CBB0C, 5,  20, 13),
    ("道具名",         0x39A648, 40, 80, 29),
    ("图鉴分类名",     0x38474C, 28, 56, 17),
    ("秘密基地装饰名", 0x3C2A44, 28, 56, 29),
]


def main() -> int:
    from meowth.table_stride import plan_stride_rewrite, verify_applied

    rom = ROM.read_bytes()

    print("=" * 84)
    print("=== v4：基于符号执行 K 值的精确改写 ===")
    print("=" * 84)
    print()
    print(f"{'表':<16} {'ldr':>4} {'K匹配':>6} {'不改':>5} {'验证(改)':>9} {'残留旧':>7}")
    print("-" * 84)

    total_ldr = total_match = 0
    all_ok = True

    for name, base, old_s, new_s, longest in TABLES:
        plan = plan_stride_rewrite(rom, base, old_s, new_s)
        total_ldr += plan.n_ldrs
        total_match += plan.n_patches

        # 验证
        should, changed, stale = verify_applied(rom, base, old_s, new_s)
        ok = (changed == should and stale == 0)
        if not ok:
            all_ok = False

        print(f"{name:<16} {plan.n_ldrs:>4} {plan.n_patches:>6} "
              f"{len(plan.skipped):>5} {changed:>9} {stale:>7}  "
              + ("✅" if ok else "⚠️"))

        # 跳过原因统计
        if plan.skipped:
            cnt = Counter((s.stride, s.reason) for s in plan.skipped)
            for (k, why), n in cnt.most_common(3):
                print(f"      跳过 K={k}: {n} 处  ({why})")

    print("-" * 84)
    print(f"{'合计':<16} {total_ldr:>4} {total_match:>6}")
    print()

    # 特性名详情（3 站点，应全改）
    print("=== 特性名详情（验证 3/3）===")
    p = plan_stride_rewrite(rom, 0x1CBC44, 8, 32)
    for pt in p.patches:
        print(f"  ✅ 0x{pt.offset:06X}: {pt.data.hex(' ')}  {pt.label}")
    for s in p.skipped:
        print(f"  ⏭  0x{s.ldr_off:06X}: K={s.stride}  {s.reason}")

    print()
    if all_ok:
        print("✅ 全部表：要改站点精确识别，改后无残留")
        return 0
    print("⚠️ 有表未通过验证")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
