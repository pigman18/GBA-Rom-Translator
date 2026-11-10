#!/usr/bin/env python3
"""把 gen_scenes.py 的 BODY_GYM 换成「两段式」版本。

背景：实测发现两种道馆布局需要不同扫法 ——
  · gym_lavaridge 用「向上走 6 格 + 每格四方向 A」采到 31 个窗口；
    换成显式蛇形后掉到 1 个；
  · gym_dewford 两种都只有 1 个（NPC 在并列走道，隔墙打不到）。
⇒ 模板改成两段：先竖扫，再蛇形。

用法：python scripts/_patch_gym_body.py
"""
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "scripts" / "gen_scenes.py"

NEW = '''BODY_GYM = \'\'\'
-- ③ 道馆：两段式扫（先竖扫，再蛇形），每格四方向试 A
--
--    ⚠ 教训（实测 4 轮，很重要）：
--      · gym_lavaridge 用「向上走 6 格 + 每格四方向 A」能采到 **31 个窗口**；
--        换成显式蛇形路径后掉到 1 个 ⇒ **竖扫对这个道馆更有效**。
--      · gym_dewford 反过来：竖扫 1 个，蛇形也 1 个（NPC 在并列走道，
--        隔墙打不到）—— 这是地图结构限制，不是路径问题。
--      · 所以模板走**两段**：先竖扫，再蛇形，两种布局都照顾到。
local dirs = {{ "UP", "LEFT", "RIGHT", "DOWN" }}

-- 第一段：竖扫（对 Lavaridge 这类「一路向上」的道馆有效）
for step = 1, 6 do
    api.roam{{ seq = {{ "UP" }}, steps = 1 }}
    api.shot(string.format("{prefix}_v%d", step))
    for _, d in ipairs(dirs) do
        api.tap(d, 5, 16)
        api.tap("A", 6, 38)
        api.shot(string.format("{prefix}_v%d_%s", step, d))
        api.tap("B", 4, 20)
    end
end
api.shot("{prefix}_vs_end")

-- 第二段：蛇形（覆盖侧翼 NPC）
local path = {{
    "LEFT", "LEFT", "LEFT", "DOWN", "DOWN", "DOWN",
    "RIGHT", "RIGHT", "RIGHT", "UP", "UP",
}}
local n = 0
for _, d in ipairs(path) do
    api.roam{{ seq = {{ d }}, steps = 1 }}
    n = n + 1
    api.shot(string.format("{prefix}_p%02d_%s", n, d))
    for _, dd in ipairs(dirs) do
        api.tap(dd, 5, 16)
        api.tap("A", 6, 38)
        api.shot(string.format("{prefix}_p%02d_%s_%s", n, d, dd))
        api.tap("B", 4, 20)
    end
end
api.shot("{prefix}_end")
\'\'\'
'''


def main() -> int:
    lines = P.read_text(encoding="utf-8").splitlines(keepends=True)
    start = end = None
    for i, ln in enumerate(lines):
        if ln.startswith("BODY_GYM = '''"):
            start = i
        elif start is not None and ln.startswith("BODY_COUNTER = '''"):
            end = i
            break
    if start is None or end is None:
        print(f"[ERR] 边界未找到 start={start} end={end}")
        return 1
    print(f"替换 {start+1}..{end} 行")
    out = lines[:start] + [NEW] + lines[end:]
    P.write_text("".join(out), encoding="utf-8")
    print("[OK]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
