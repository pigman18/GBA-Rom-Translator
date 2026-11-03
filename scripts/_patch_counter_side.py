#!/usr/bin/env python3
"""把游戏厅的成功方案固化进生成器（counter 模式增加「先侧移再上」）。

── 背景 ────────────────────────────────────────────────────────────────
gamecorner_mauville 原来只有 1 帧有窗口。实测发现：
  warp 到 (8,10) 时**紧贴老虎机台**，直接 UP 被挡；
  改成 **先 RIGHT 绕 2 格，再 UP**，窗口从 1 帧涨到 **218 帧**。
所以 counter 模板加上「先侧移」这一步，对所有紧贴柜台的场景都更稳。

用法：python scripts/_patch_counter_side.py
"""
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "scripts" / "gen_scenes.py"

OLD = '''api.roam{{ seq = {{ "UP", "UP", "UP", "UP" }}, steps = 4 }}
api.shot("{prefix}_at_counter")
'''
NEW = '''--    ⚠ 先侧移再上行：实测 gamecorner 落点 (8,10) 紧贴老虎机台，
--      直接 UP 被挡（只有 1 帧窗口）；先 RIGHT 绕 2 格再 UP，
--      窗口从 1 → **218 帧**。所以模板固定加这一步。
api.roam{{ seq = {{ "RIGHT", "RIGHT" }}, steps = 2 }}
api.shot("{prefix}_side")
api.roam{{ seq = {{ "UP", "UP", "UP", "UP" }}, steps = 4 }}
api.shot("{prefix}_at_counter")
'''


def main() -> int:
    s = P.read_text(encoding="utf-8")
    if OLD not in s:
        print("[ERR] 找不到 counter 的 UP 段")
        return 1
    P.write_text(s.replace(OLD, NEW, 1), encoding="utf-8")
    print("[OK] counter 模板已加「先侧移再上行」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
