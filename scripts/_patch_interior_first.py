#!/usr/bin/env python3
"""interior 模板：落点先四方向试一轮，再开始蛇形走位。

── 为什么 ────────────────────────────────────────────────────────────
house_mauville2 校准后落点 (4,6) 正好在 NPC (4,5) 正下方，
但模板第一步是 LEFT，走到 (3,6) 才开始试 A —— 再也没回到 NPC 旁边。
实测轨迹：(3,6)→(2,6)→(1,6)→(1,5)→(1,3)→(2,2)，全程没碰过 (4,6)。

⇒ 落点是**用 NPC 坐标算出来的**，那么一到位就该先试，不能先走开。

用法：python scripts/_patch_interior_first.py
"""
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "scripts" / "gen_scenes.py"

OLD = '''local dirs = {{ "UP", "LEFT", "RIGHT", "DOWN" }}
local plan = {{
    {{ "LEFT", "LEFT", "LEFT" }},'''
NEW = '''local dirs = {{ "UP", "LEFT", "RIGHT", "DOWN" }}

-- ★ 落点先用四方向 talk(soft) 试一轮再走开。
--   落点是按 NPC 坐标算出来的（calibrate_all.py），到位就该先试；
--   实测 house_mauville2 判模板先 LEFT 走掉，再也没回到 NPC 旁边
--   （轨迹 (3,6)→(2,6)→(1,6)→(1,5)→(1,3)→(2,2)，全程没碰 (4,6)）。
for _, dd in ipairs(dirs) do
    api.tap(dd, 5, 18)
    api.talk{{ timeout = 120, soft = true }}
    api.shot(string.format("{prefix}_arrive_%s", dd))
    api.burst(string.format("{prefix}_arrive_%s_f", dd), 6, 5)
    for i = 1, 2 do api.tap("A", 5, 35) end
    api.tap("B", 4, 22)
end

local plan = {{
    {{ "LEFT", "LEFT", "LEFT" }},'''


def main() -> int:
    s = P.read_text(encoding="utf-8")
    if "落点先用四方向 talk(soft) 试一轮再走开" in s:
        print("[skip] 已打过补丁")
        return 0
    if OLD not in s:
        print("[ERR] 找不到 interior 的 plan 起点")
        return 1
    P.write_text(s.replace(OLD, NEW, 1), encoding="utf-8")
    print("[OK] interior 模板已加「落点先试」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
