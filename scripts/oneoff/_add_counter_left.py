#!/usr/bin/env python3
"""给 bikeshop 单独指定 counter_left 模式（先侧移再上）。

── 实测对照 ────────────────────────────────────────────────────────────
bikeshop_mauville 在两种模板下的表现：
  · 「先 UP 4 格 → 四方向 talk」            → 1 帧
  · 「先 RIGHT 2 格 → UP 4 格 → 四方向 talk」→ 139 帧  ✅
截图显示店主在主角**右上方**，所以先侧移再上是正确路径。

而商店/PC 正好相反（先 UP 才对，固定侧移会离开柜台）。
⇒ 生成器加第四种模式 counter_left，专门给 bikeshop 这类「店主在侧面」的场景。

用法：python scripts/_add_counter_left.py
"""
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "scripts" / "gen_scenes.py"

NEW_BODY = '''BODY_COUNTER_LEFT = \'\'\'
-- ③ 柜台在侧面：先侧移再上行，然后四方向 talk
--
--    ⚠ 实测（bikeshop_mauville）：
--      · 先 UP 4 格 → 四方向 talk   ⇒ **1 帧**（打空）
--      · 先 RIGHT 2 格 → UP 4 格   ⇒ **139 帧** ✅
--      截图显示店主在主角**右上方**，所以必须先侧移。
--    （商店/PC 相反：它们要先直上，固定侧移会离开柜台。）
api.roam{{ seq = {{ "RIGHT", "RIGHT" }}, steps = 2 }}
api.shot("{prefix}_side")
api.roam{{ seq = {{ "UP", "UP", "UP", "UP" }}, steps = 4 }}
api.shot("{prefix}_at_counter")

local probe = {{ "UP", "RIGHT", "LEFT", "DOWN" }}
for _, d in ipairs(probe) do
    api.tap(d, 5, 22)
    api.talk{{ timeout = 200, soft = true }}
    api.burst(string.format("{prefix}_dlg_%s_f", d), 10, 5)
    api.shot(string.format("{prefix}_dlg_%s", d))
    for i = 1, 4 do
        api.tap("A", 5, 42)
        api.shot(string.format("{prefix}_dlg_%s_%d", d, i))
    end
    api.tap("B", 4, 30)
end

-- 退出后试菜单（选车/看车列表）
api.tap("A", 6, 60)
api.burst("{prefix}_menu_f", 12, 8)
api.shot("{prefix}_menu")
for i = 1, 6 do
    api.tap("DOWN", 4, 28)
    api.shot(string.format("{prefix}_item%d", i))
end
api.tap("B", 4, 45)
api.shot("{prefix}_end")
\'\'\'

'''


def main() -> int:
    s = P.read_text(encoding="utf-8")

    # 1) 插入新 BODY
    if "BODY_COUNTER_LEFT" in s:
        print("[skip] BODY_COUNTER_LEFT 已存在")
    else:
        anchor = "BODIES = {"
        if anchor not in s:
            print("[ERR] 找不到 BODIES")
            return 1
        s = s.replace(anchor, NEW_BODY + anchor, 1)

    # 2) 注册到 BODIES
    old_bodies = '"counter": BODY_COUNTER, "interior": BODY_INTERIOR}'
    new_bodies = ('"counter": BODY_COUNTER, "counter_left": BODY_COUNTER_LEFT, '
                  '"interior": BODY_INTERIOR}')
    if old_bodies in s:
        s = s.replace(old_bodies, new_bodies, 1)
    elif "counter_left" not in s:
        print("[ERR] 找不到 BODIES 定义")
        return 1

    # 3) bikeshop 改用 counter_left
    old_def = '"bikeshop_mauville": ("10:1", 6, 8,  "Mauville 自行车店", "counter"),'
    new_def = '"bikeshop_mauville": ("10:1", 6, 8,  "Mauville 自行车店", "counter_left"),'
    if old_def in s:
        s = s.replace(old_def, new_def, 1)
    elif '"counter_left"),' not in s:
        print("[warn] bikeshop 定义格式不匹配，请手工确认")
    P.write_text(s, encoding="utf-8")
    print("[OK] 已加 counter_left 模式并指派给 bikeshop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
