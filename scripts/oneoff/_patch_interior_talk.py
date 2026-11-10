#!/usr/bin/env python3
"""加强 interior 模板：四方向用 talk(soft) 而不是只按 A。

── 为什么改 ────────────────────────────────────────────────────────────
`house_mauville2` 和 `motel_lilycove_2f` 校准后仍然只有 1 帧窗口。
截图显示 house_mauville2 里 NPC 就在主角正上方（朝向对），
但只按 A 没开框 —— 可能是 NPC 需要「面向 + A」的特定组合，
或者 mid-step 的 B 把它关掉了。

原 interior 模板是「四方向 tap + A + B」，改成「四方向 tap + talk(soft)」，
talk 会用「文本真的推进」当判据，比单发 A 可靠得多。

用法：python scripts/_patch_interior_talk.py
"""
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "scripts" / "gen_scenes.py"

NEW = '''BODY_INTERIOR = \'\'\'
-- ③ 普通室内：蛇形走位覆盖全屋，每格四方向用 **talk(soft)** 试探
--
--    ⚠ 教训（2026-11-04）：
--      · 原来用「四方向 tap + A」，house_mauville2 里 NPC 就在正上方、
--        朝向也对，但只按 A 就是不开框（实测 1 帧窗口）。
--      · 改用 talk(soft)：它以「文本真的推进」为判据，比单发 A 可靠。
local dirs = {{ "UP", "LEFT", "RIGHT", "DOWN" }}
local plan = {{
    {{ "LEFT", "LEFT", "LEFT" }},
    {{ "UP", "UP" }},
    {{ "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT" }},
    {{ "UP", "UP" }},
    {{ "LEFT", "LEFT", "LEFT", "LEFT" }},
}}
local n = 0
for _, seg in ipairs(plan) do
    for _, d in ipairs(seg) do
        api.roam{{ seq = {{ d }}, steps = 1 }}
        n = n + 1
        api.shot(string.format("{prefix}_p%02d", n))
        for _, dd in ipairs(dirs) do
            api.tap(dd, 5, 16)
            api.talk{{ timeout = 110, soft = true }}
            api.shot(string.format("{prefix}_p%02d_%s", n, dd))
            api.burst(string.format("{prefix}_p%02d_%s_f", n, dd), 4, 5)
            for i = 1, 2 do api.tap("A", 5, 32) end
            api.tap("B", 4, 20)
        end
    end
end
api.shot("{prefix}_end")
\'\'\'
'''


def main() -> int:
    lines = P.read_text(encoding="utf-8").splitlines(keepends=True)
    start = end = None
    for i, ln in enumerate(lines):
        if ln.startswith("BODY_INTERIOR = '''"):
            start = i
        elif start is not None and ln.startswith("BODIES = {"):
            end = i
            break
    if start is None or end is None:
        print(f"[ERR] 边界未找到 start={start} end={end}")
        return 1
    print(f"替换 {start+1}..{end}")
    P.write_text("".join(lines[:start]) + NEW + "".join(lines[end:]),
                 encoding="utf-8")
    print("[OK] interior 模板已改为四方向 talk(soft)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
