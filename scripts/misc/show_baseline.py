#!/usr/bin/env python3
"""查看基线分级明细，找出 C 级场景及其原因。

用法：python scripts/show_baseline.py [A|B|C]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "work" / "_baseline" / "scene_baseline.json"


def main() -> int:
    if not B.is_file():
        print("[ERR] 先跑 scripts/build_baseline.py")
        return 1
    d = json.loads(B.read_text(encoding="utf-8"))
    want = sys.argv[1].upper() if len(sys.argv) > 1 else None

    grades = ["A", "B", "C"] if not want else [want]
    for g in grades:
        items = [(k, v) for k, v in d.items() if v["grade"] == g]
        print(f"=== {g} 级（{len(items)} 个）===")
        # C 级按相似度升序（最差的在前），其他按降序
        key = (lambda x: x[1]["sim_median"] or 0)
        items.sort(key=key, reverse=(g != "C"))
        for k, v in items:
            fd = v["dims"]
            print(f"  {k:<26} sim={v['sim_median']:<8} 帧={v['frames']:<4} "
                  f"fail={v['verdicts'].get('fail', 0):<4} "
                  f"s_scene={fd.get('s_scene', 0):<3} "
                  f"garble={fd.get('g_garble', 0):<3} "
                  f"collide={fd.get('g_collide', 0)}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
