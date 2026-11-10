#!/usr/bin/env python3
"""把 motel_lilycove_2f 的落点改成 (4,7)，对准对象 (4,6)。

── 依据 ────────────────────────────────────────────────────────────────
motel_lilycove_2f (13:1) 实测有 6 个可交互对象：
    (4,6) (1,4) (7,7) (10,3) (7,3) (4,4)
原来校准按「离落点最近」选了 (4,4) → 落点 (4,5)，
但游戏把 warp 落点调成了 (3,5)（相邻格不可站），于是打不到任何对象。

改选 (4,6)，落点 (4,7)（它正下方），并靠 interior 模板的
「落点先四方向试」覆盖到。
"""
from pathlib import Path
import re

P = Path(__file__).resolve().parent.parent / "scripts" / "gen_scenes.py"


def main() -> int:
    s = P.read_text(encoding="utf-8")
    pat = re.compile(r'("motel_lilycove_2f":\s*\("13:1",\s*)(\d+)(,\s*)(\d+)(\s*,)')
    m = pat.search(s)
    if not m:
        print("[ERR] 未找到定义")
        return 1
    print(f"改前: {m.group(0)}")
    s = pat.sub(rf'\g<1>4\g<3>7\g<5>', s, count=1)
    P.write_text(s, encoding="utf-8")
    m2 = pat.search(s)
    print(f"改后: {m2.group(0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
