#!/usr/bin/env python3
"""把 counter 模板改回「不侧移」，但保留「侧移后重试」作为后备。

── 实测教训（很重要）──────────────────────────────────────────────────
在 counter 模板里固定加「先 RIGHT 2 格再 UP」后：
  gamecorner_mauville  1 → 164  ✅ 有效
  bikeshop_mauville  139 → 1    ❌ 变差
  center_mauville    164 → 1    ❌ 变差
⇒ 侧移对紧贴老虎机台的游戏厅有用，但会让商店/PC 离开柜台。

**正确做法**：先直接 UP（对商店/PC 是对的），
若四方向 talk 都打空，再**回到落点附近侧移后重试**。
这样两类场景都能覆盖。

用法：python scripts/_patch_counter_v2.py
"""
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "scripts" / "gen_scenes.py"

OLD = '''--    ⚠ 先侧移再上行：实测 gamecorner 落点 (8,10) 紧贴老虎机台，
--      直接 UP 被挡（只有 1 帧窗口）；先 RIGHT 绕 2 格再 UP，
--      窗口从 1 → **218 帧**。所以模板固定加这一步。
api.roam{{ seq = {{ "RIGHT", "RIGHT" }}, steps = 2 }}
api.shot("{prefix}_side")
api.roam{{ seq = {{ "UP", "UP", "UP", "UP" }}, steps = 4 }}
api.shot("{prefix}_at_counter")
'''

NEW = '''--    ⚠ 顺序很重要（实测对照）：
--      · **先直接 UP** —— 对商店/宝可梦中心是对的（走到柜台前）
--      · 若四方向 talk 全打空，再**侧移后重试** —— 对紧贴老虎机的游戏厅有用
--      固定加侧移会让商店/PC 离开柜台（实测 bikeshop 139→1、
--      center 164→1）；固定不侧移则 gamecorner 只有 1。所以两段都要。
api.roam{{ seq = {{ "UP", "UP", "UP", "UP" }}, steps = 4 }}
api.shot("{prefix}_at_counter")
'''


def main() -> int:
    s = P.read_text(encoding="utf-8")
    if OLD not in s:
        print("[ERR] 找不到当前 counter 段")
        return 1
    s = s.replace(OLD, NEW, 1)

    # 在四方向 talk 循环之后插入「侧移重试」段
    anchor = '''    api.tap("B", 4, 30)
end
'''
    retry = '''    api.tap("B", 4, 30)
end

-- 后备：若四方向都没开框，侧移一段再重试（游戏厅这类紧贴柜台的场景）
api.roam{{ seq = {{ "RIGHT", "RIGHT" }}, steps = 2 }}
api.shot("{prefix}_side_retry")
for _, d in ipairs(probe) do
    api.tap(d, 5, 20)
    api.talk{{ timeout = 120, soft = true }}
    api.burst(string.format("{prefix}_r_%s_f", d), 8, 5)
    api.shot(string.format("{prefix}_r_%s", d))
    for i = 1, 2 do api.tap("A", 5, 35) end
    api.tap("B", 4, 25)
end
'''
    if anchor not in s:
        print("[ERR] 找不到四方向 talk 的结尾")
        return 1
    s = s.replace(anchor, retry, 1)
    P.write_text(s, encoding="utf-8")
    print("[OK] counter 模板改为「先直上，失败再侧移重试」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
