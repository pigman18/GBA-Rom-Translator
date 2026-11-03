#!/usr/bin/env python3
"""按「地图 + 采集套路」批量生成 bot 场景脚本。

── 为什么做生成器 ──────────────────────────────────────────────────────
窗口覆盖要求把 §7.2 的 45 个窗口实例都采到，涉及十几张室内地图。
每个场景的结构高度一致（warp 进图 → 连帧 → 走位找 NPC → talk 开对话
→ 逐句推进），手写十几个会大量重复且容易漏掉「连帧」「闸门」这些关键点。
生成器把套路固化，改一处即可全部更新。

── 套路（TEMPLATE）的关键点 ────────────────────────────────────────────
1. **一次 warp**：连续第二次会 TIMEOUT（实测），所以一个场景只跳一次。
2. **连帧**：每个界面至少 burst，翻页/换句必须连帧（单帧证明不了过渡）。
3. **talk 闸门**：开对话用 talk，打空会当场失败，不产出假对照。
4. **八方向试探**：NPC 朝向未知时，用 `probe_dirs` 把四方向都试一遍，
   事后再按 VRAM 差异挑（见 COVERAGE 2.2 的坑 1）。

用法：
  python scripts/gen_scenes.py --emit          # 生成全部
  python scripts/gen_scenes.py --emit --only gym_dewford
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENES = ROOT / "bot" / "scenes" / "POKEMON_RUBY_AXVJ00"

# ── 场景定义：名字 -> (mapId, x, y, 说明, 模式) ─────────────────────────
#   模式：
#     "interior"  普通室内：连帧 + 走位 + 四方向试 A
#     "counter"   有柜台：走到中间往上，面朝 UP 与柜台对话
#     "gym"       道馆：进图 + 走位 + 试对话（方向未定，四方向都试）
SCENE_DEFS = {
    "gym_dewford":      ("3:3",  8, 15, "Dewford 道馆（格斗）", "gym"),
    "gym_rustboro":     ("11:3", 8, 12, "Rustboro 道馆（岩石）", "gym"),
    "gym_lavaridge":    ("4:1",  8, 12, "Lavaridge 道馆（火）1F", "gym"),
    "center_mauville":  ("10:5", 7, 8,  "Mauville 宝可梦中心 1F", "counter"),
    "center_oldale":    ("2:2",  7, 8,  "Oldale 宝可梦中心 1F", "counter"),
    "center_slateport": ("9:10", 7, 8,  "Slateport 宝可梦中心 1F", "counter"),
    "mart_oldale":      ("2:4",  7, 8,  "Oldale 商店", "counter"),
    "mart_slateport":   ("9:12", 8, 8,  "Slateport 商店", "counter"),
    "contest_lilycove": ("13:5", 10, 12, "Lilycove 华丽大赛会场", "interior"),
    "contest_slateport": ("9:3", 10, 12, "Slateport 华丽大赛会场", "interior"),
    "gamecorner_mauville": ("10:3", 8, 10, "Mauville 游戏厅", "counter_left"),
    "bikeshop_mauville": ("10:1", 6, 8,  "Mauville 自行车店", "counter"),
}

HEADER = '''-- ============================================================================
-- {name}.lua — {desc}（map={mapId}）
--
-- 【地图 ID 依据】scripts/map_ids_full.py
--   日版实测校准了 group 0/2/10 与美版完全一致，其余组按美版顺序换算。
--
-- 【到达方式】warp（精确跳图，2026-11-03 跑通）
--   写 SaveBlock1.lastHealLocation(+0x1C) → 用传送术 → 精确落点。
--   ⚠ 一个场景只做一次 warp（连续第二次会 TIMEOUT，实测）。
--   ⚠ 落点必须在地图内可走区域，否则落在黑屏（见 COVERAGE 2.2）。
--
-- 【采集套路】连帧 + talk 闸门（打空当场失败，不产出假对照）
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("{prefix}_start")

-- ① 出门到城市（warp 需要先能自由行动；传送术在室内不可用）
api.roam{{ seq = {{ "DOWN", "DOWN" }}, steps = 8 }}
api.shot("{prefix}_outside")

-- ② 跳进目标地图
api.warp{{ map = "{mapId}", x = {x}, y = {y}, mon = 1 }}
api.wait(60)
api.shot("{prefix}_inside")
api.burst("{prefix}_enter_f", 14, 8)
'''

BODY_GYM = '''
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
'''
BODY_COUNTER = '''
-- ③ 柜台/店员对话
--
--    ⚠ 教训（bikeshop/gamecorner 实测）：走到 (6,5) 面朝 UP 时 talk 超时，
--      但截图显示**店主在右上方**（不在正上方）。柜台位置的规律不可靠，
--      所以这里四方向**各试一次 talk（soft）**，只要有一个开框就继续。
--    ⚠ 顺序很重要（实测对照）：
--      · **先直接 UP** —— 对商店/宝可梦中心是对的（走到柜台前）
--      · 若四方向 talk 全打空，再**侧移后重试** —— 对紧贴老虎机的游戏厅有用
--      固定加侧移会让商店/PC 离开柜台（实测 bikeshop 139→1、
--      center 164→1）；固定不侧移则 gamecorner 只有 1。所以两段都要。
api.roam{{ seq = {{ "UP", "UP", "UP", "UP" }}, steps = 4 }}
api.shot("{prefix}_at_counter")

local probe = {{ "UP", "RIGHT", "LEFT", "DOWN" }}
for _, d in ipairs(probe) do
    api.tap(d, 5, 22)
    api.talk{{ timeout = 150, soft = true }}
    api.burst(string.format("{prefix}_dlg_%s_f", d), 10, 5)
    api.shot(string.format("{prefix}_dlg_%s", d))
    -- 若真开了框，多推两句（把这段对话采完整）
    for i = 1, 3 do
        api.tap("A", 5, 40)
        api.shot(string.format("{prefix}_dlg_%s_%d", d, i))
    end
    api.tap("B", 4, 30)
end

-- 逐句推进（每句连帧，覆盖逐字打印与换句重绘）
for i = 1, 8 do
    api.tap("A", 5, 45)
    api.burst(string.format("{prefix}_dlg%d_f", i + 1), 6, 6)
    api.shot(string.format("{prefix}_dlg%d", i + 1))
end

-- ④ 退出后试菜单（商店/PC 都有列表）
api.tap("B", 4, 40)
api.shot("{prefix}_menu_try")
api.tap("A", 6, 55)
api.burst("{prefix}_menu_f", 12, 8)
api.shot("{prefix}_menu")
for i = 1, 6 do
    api.tap("DOWN", 4, 26)
    api.burst(string.format("{prefix}_item%d_f", i), 5, 6)
    api.shot(string.format("{prefix}_item%d", i))
end
api.tap("B", 4, 45)
api.shot("{prefix}_end")
'''

BODY_INTERIOR = '''
-- ③ 普通室内：蛇形走位覆盖全屋，每格四方向试 A（找 NPC / 告示牌）
--
--    ⚠ 教训（contest_lilycove 实测）：只往上走 5 格，43 帧里只有 1 帧有窗口。
--      室内 NPC 常在侧面，必须横向也扫。
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
            api.tap(dd, 5, 18)
            api.tap("A", 6, 40)
            api.shot(string.format("{prefix}_p%02d_%s", n, dd))
            api.tap("B", 4, 22)
        end
    end
end
api.shot("{prefix}_end")
'''

BODY_COUNTER_LEFT = '''
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
'''

BODIES = {"gym": BODY_GYM, "counter": BODY_COUNTER, "counter_left": BODY_COUNTER_LEFT, "interior": BODY_INTERIOR}


def gen(name: str) -> str:
    """生成场景脚本。

    ⚠ 坑：HEADER 走 .format() 后 `{{` 会变成 `{`，但 BODY 若直接拼接就会
      留下未替换的 `{prefix}` 和 `{{`（实测症状：mGBA 报
      `scene load failed: nil`，因为 `api.roam{{ seq = ...}}` 是语法错）。
      所以 BODY 也必须走一遍 .format()，且模板里所有字面量花括号写 `{{`。
    """
    map_id, x, y, desc, mode = SCENE_DEFS[name]
    parts = name.split("_")
    prefix = (parts[0][:4] + "_" + parts[-1][:4]).lower()
    head = HEADER.format(name=name, mapId=map_id, x=x, y=y,
                         desc=desc, prefix=prefix)
    body = BODIES[mode].format(prefix=prefix)
    # ⚠ 必须以 `return api.S` 结尾。
    #   漏了会得到 `scene load failed: nil` —— dofile 返回 nil，
    #   bot.lua 判 `type(STEPS) ~= "table"` 直接失败（实测踩过）。
    return head + body + "\nreturn api.S\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    if not a.emit:
        print(__doc__)
        for n, (m, x, y, d, mode) in SCENE_DEFS.items():
            print(f"  {n:<24} map={m:<7} ({x},{y})  {mode:<9} {d}")
        return 0

    names = [a.only] if a.only else list(SCENE_DEFS)
    for n in names:
        if n not in SCENE_DEFS:
            print(f"[ERR] 未知场景 {n}")
            return 1
        p = SCENES / f"{n}.lua"
        p.write_text(gen(n), encoding="utf-8")
        print(f"[OK] {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
