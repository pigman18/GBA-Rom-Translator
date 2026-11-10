#!/usr/bin/env python3
"""更新 SCENE_DEFS：把两个缺口场景的落点改成「可交互对象相邻格」。

依据 scripts/list_interactables.py 解出的 ObjectEventTemplate：
  gym_dewford (3:3)：最近对象 (2,17) → 落点 (2,18) 朝 UP
  contest_lilycove (13:5)：最近对象 (11,7) → 落点 (11,8) 朝 UP

用法：python scripts/_update_scene_defs.py
"""
import re
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "scripts" / "gen_scenes.py"


def main() -> int:
    s = P.read_text(encoding="utf-8")

    subs = [
        (r'"gym_dewford":\s*\("3:3",\s*\d+,\s*\d+,',
         '"gym_dewford":      ("3:3",  2, 18,'),
        (r'"contest_lilycove":\s*\("13:5",\s*\d+,\s*\d+,',
         '"contest_lilycove": ("13:5", 11, 8,'),
    ]
    n = 0
    for pat, rep in subs:
        s2, k = re.subn(pat, rep, s)
        if k:
            s = s2
            n += k
        else:
            print(f"[warn] 未匹配: {pat}")
    P.write_text(s, encoding="utf-8")
    print(f"[OK] 更新 {n} 处落点")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
