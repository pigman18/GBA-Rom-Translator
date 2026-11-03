#!/usr/bin/env python3
"""找出「改 location 后地图没切换」的真正原因。

现象：Route118_68-7.sav 改成 loc=10:7 pos=(3,3) warp=0 后，
      prove 读到的值与真·商店存档一模一样，画面却仍是 Route118 且主角消失。

本脚本把两份逻辑存档**整块**逐字节对比（不只 SaveBlock1 头部），
按段汇总差异，直接指出哪些字段跟着地图变了。
用法：python scripts/diff_sav_full.py <a.sav> <b.sav>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bot" / "tools"))
from savedit import rebuild  # noqa: E402

# 逻辑存档分段（savlib 实证）
REGIONS = [
    (0x00000, 0x00890, "SaveBlock2"),
    (0x01000, 0x03AC0, "SaveBlock1"),
    (0x05000, 0x083D8, "PokemonStorage"),
]


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    ap, bp = Path(sys.argv[1]), Path(sys.argv[2])
    a, _ = rebuild(ap.read_bytes())
    b, _ = rebuild(bp.read_bytes())

    print(f"A = {ap.name}")
    print(f"B = {bp.name}\n")

    for off, size, name in REGIONS:
        diffs = [i for i in range(size) if a[off + i] != b[off + i]]
        print(f"{name}: {len(diffs)} 字节不同 / 共 {size}")
        if diffs:
            # 按连续段聚合成区间，方便阅读
            runs, s, prev = [], diffs[0], diffs[0]
            for i in diffs[1:]:
                if i == prev + 1:
                    prev = i
                    continue
                runs.append((s, prev)); s = prev = i
            runs.append((s, prev))
            for s, e in runs[:40]:
                seg_a = a[off + s:off + e + 1]
                seg_b = b[off + s:off + e + 1]
                print(f"  +0x{s:05X}..0x{e:05X} ({e - s + 1}B)")
                print(f"      A={seg_a.hex(' ')}")
                print(f"      B={seg_b.hex(' ')}")
            if len(runs) > 40:
                print(f"  … 另有 {len(runs) - 40} 段")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
