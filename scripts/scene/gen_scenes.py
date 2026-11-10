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
#   ★ 落点怎么定（2026-11-03 起有工具了，别再用猜的）：
#       python scripts/list_interactables.py --sav <存档>
#     它会解出 ObjectEventTemplate（日版布局 SaveBlock1+0x0C0C，每项 0x18，
#     +0x00 s16 x / +0x02 s16 y / +0x0C u32 script），
#     直接给出「warp 到哪个相邻格、朝哪个方向」。
#     ⚠ 存档必须在目标地图上；想查某张图就先让 bot 跳过去采一帧 ram.bin。
#
#   ⚠⚠ gym_dewford.lua 与 contest_lilycove.lua 是**手工写的**（不走生成器）：
#      落点来自 list_interactables 的实际输出，且带「为什么之前采不到」的注释。
#      **不要用 --emit --only 这两个名覆盖**，否则会丢注释和定制逻辑。
#      SCENE_DEFS 里保留它们只为记录落点。
#   模式：
#     "interior"  普通室内：连帧 + 走位 + 四方向试 A
#     "counter"   有柜台：走到中间往上，面朝 UP 与柜台对话
#     "gym"       道馆：进图 + 走位 + 试对话（方向未定，四方向都试）
SCENE_DEFS = {
    "gym_dewford":      ("3:3",  2, 18, "Dewford 道馆（格斗）", "gym"),
    "gym_rustboro":     ("11:3", 8, 12, "Rustboro 道馆（岩石）", "gym"),
    "gym_lavaridge":    ("4:1",  8, 12, "Lavaridge 道馆（火）1F", "gym"),
    "center_mauville":  ("10:5", 7, 8,  "Mauville 宝可梦中心 1F", "counter"),
    "center_oldale":    ("2:2",  7, 8,  "Oldale 宝可梦中心 1F", "counter"),
    "center_slateport": ("9:10", 7, 8,  "Slateport 宝可梦中心 1F", "counter"),
    "mart_oldale":      ("2:4",  7, 8,  "Oldale 商店", "counter"),
    "mart_slateport":   ("9:12", 8, 8,  "Slateport 商店", "counter"),
    "contest_lilycove": ("13:5", 11, 8, "Lilycove 华丽大赛会场", "interior"),
    "contest_slateport": ("9:3", 10, 12, "Slateport 华丽大赛会场", "interior"),
    "gamecorner_mauville": ("10:3", 8, 10, "Mauville 游戏厅", "counter_left"),
    "bikeshop_mauville": ("10:1", 6, 8,  "Mauville 自行车店", "counter"),
    "center_dewford": ('3:1', 7, 8, 'Dewford 宝可梦中心 1F', 'counter'),
    "herbshop_lavaridge": ('4:0', 7, 6, 'Lavaridge 药草店', 'counter_left'),
    "mart_lavaridge": ('4:4', 7, 8, 'Lavaridge 商店', 'counter'),
    "center_lavaridge": ('4:5', 7, 8, 'Lavaridge 宝可梦中心 1F', 'counter'),
    "mart_fallarbor": ('5:0', 7, 8, 'Fallarbor 商店', 'counter'),
    "contest_fallarbor": ('5:2', 5, 8, 'Fallarbor 华丽大赛会场', 'interior'),
    "center_fallarbor": ('5:3', 7, 8, 'Fallarbor 宝可梦中心 1F', 'counter'),
    "contest_verdanturf_l": ('6:0', 7, 6, 'Verdanturf 大赛大厅', 'interior'),
    "contest_verdanturf": ('6:1', 10, 12, 'Verdanturf 华丽大赛会场', 'interior'),
    "mart_verdanturf": ('6:2', 7, 8, 'Verdanturf 商店', 'counter'),
    "center_verdanturf": ('6:3', 7, 8, 'Verdanturf 宝可梦中心 1F', 'counter'),
    "center_pacifidlog": ('7:0', 7, 8, 'Pacifidlog 宝可梦中心 1F', 'counter'),
    "gym_petalburg": ('8:1', 4, 17, 'Petalburg 道馆（普通）', 'gym'),
    "center_petalburg": ('8:4', 7, 8, 'Petalburg 宝可梦中心 1F', 'counter'),
    "mart_petalburg": ('8:6', 7, 8, 'Petalburg 商店', 'counter'),
    "contest_slateport_l": ('9:2', 9, 7, 'Slateport 大赛大厅', 'interior'),
    "fanclub_slateport": ('9:5', 8, 10, 'Slateport 宝可梦发烧友俱乐部', 'interior'),
    "museum_slateport": ('9:6', 7, 8, 'Slateport 海洋博物馆 1F', 'interior'),
    "center_rustboro": ('11:5', 7, 8, 'Rustboro 宝可梦中心 1F', 'counter'),
    "mart_rustboro": ('11:7', 7, 8, 'Rustboro 商店', 'counter'),
    "gym_fortree": ('12:1', 8, 12, 'Fortree 道馆（飞行）', 'gym'),
    "center_fortree": ('12:2', 7, 8, 'Fortree 宝可梦中心 1F', 'counter'),
    "mart_fortree": ('12:4', 7, 8, 'Fortree 商店', 'counter'),
    "contest_lilycove_l": ('13:4', 8, 8, 'Lilycove 大赛大厅', 'interior'),
    "center_lilycove": ('13:6', 7, 8, 'Lilycove 宝可梦中心 1F', 'counter'),
    "gym_mossdeep": ('14:0', 8, 12, 'Mossdeep 道馆（超能）', 'gym'),
    "center_mossdeep": ('14:3', 7, 8, 'Mossdeep 宝可梦中心 1F', 'counter'),
    "mart_mossdeep": ('14:5', 7, 8, 'Mossdeep 商店', 'counter'),
    "gym_sootopolis": ('15:0', 8, 12, 'Sootopolis 道馆（水）1F', 'gym'),
    "center_sootopolis": ('15:2', 7, 8, 'Sootopolis 宝可梦中心 1F', 'counter'),
    "mart_sootopolis": ('15:4', 7, 8, 'Sootopolis 商店', 'counter'),
    "house_oldale1": ("2:0", 8, 8, "Oldale 民家 1", "interior"),
    "house_oldale2": ("2:1", 8, 8, "Oldale 民家 2", "interior"),
    "center_oldale_2f": ("2:3", 8, 8, "Oldale 宝可梦中心 2F", "interior"),
    "house_dewford1": ("3:0", 8, 8, "Dewford 民家 1", "interior"),
    "center_dewford_2f": ("3:2", 8, 8, "Dewford 宝可梦中心 2F", "interior"),
    "hall_dewford": ("3:4", 8, 8, "Dewford 会馆", "interior"),
    "house_dewford2": ("3:5", 8, 8, "Dewford 民家 2", "interior"),
    "gym_lavaridge_b1f": ("4:2", 8, 8, "Lavaridge 道馆 B1F", "gym"),
    "house_lavaridge": ("4:3", 8, 8, "Lavaridge 民家", "interior"),
    "center_lavaridge_2f": ("4:6", 8, 8, "Lavaridge 宝可梦中心 2F", "interior"),
    "center_fallarbor_2f": ("5:4", 8, 8, "Fallarbor 宝可梦中心 2F", "interior"),
    "house_fallarbor1": ("5:5", 8, 8, "Fallarbor 民家 1", "interior"),
    "house_fallarbor2": ("5:6", 4, 5, "Fallarbor 民家 2", "interior"),
    "center_verdanturf_2f": ("6:4", 8, 8, "Verdanturf 宝可梦中心 2F", "interior"),
    "house_wanda": ("6:5", 8, 8, "Verdanturf 瓦妮达家", "interior"),
    "house_friendship": ("6:6", 4, 5, "Verdanturf 鉴定之家", "interior"),
    "house_verdanturf": ("6:7", 8, 8, "Verdanturf 民家", "interior"),
    "center_pacifidlog_2f": ("7:1", 8, 8, "Pacifidlog 宝可梦中心 2F", "interior"),
    "house_pacifidlog1": ("7:2", 8, 8, "Pacifidlog 民家 1", "interior"),
    "house_pacifidlog2": ("7:3", 8, 8, "Pacifidlog 民家 2", "interior"),
    "house_pacifidlog3": ("7:4", 8, 8, "Pacifidlog 民家 3", "interior"),
    "house_pacifidlog4": ("7:5", 8, 8, "Pacifidlog 民家 4", "interior"),
    "house_pacifidlog5": ("7:6", 8, 8, "Pacifidlog 民家 5", "interior"),
    "house_wally": ("8:0", 7, 6, "Petalburg 小胜家", "interior"),
    "house_petalburg1": ("8:2", 8, 8, "Petalburg 民家 1", "interior"),
    "house_petalburg2": ("8:3", 8, 8, "Petalburg 民家 2", "interior"),
    "center_petalburg_2f": ("8:5", 8, 8, "Petalburg 宝可梦中心 2F", "interior"),
    "shipyard_slateport_1f": ("9:0", 8, 8, "Slateport 船厂 1F", "interior"),
    "shipyard_slateport_2f": ("9:1", 8, 8, "Slateport 船厂 2F", "interior"),
    "house_slateport1": ("9:4", 8, 8, "Slateport 民家 1", "interior"),
    "museum_slateport_2f": ("9:7", 9, 7, "Slateport 海洋博物馆 2F", "interior"),
    "harbor_slateport": ("9:8", 8, 11, "Slateport 港口", "interior"),
    "house_slateport2": ("9:9", 8, 8, "Slateport 民家 2", "interior"),
    "center_slateport_2f": ("9:11", 8, 8, "Slateport 宝可梦中心 2F", "interior"),
    "house_mauville1": ("10:2", 4, 5, "Mauville 民家 1", "interior"),
    "house_mauville2": ("10:4", 4, 6, "Mauville 民家 2", "interior"),
    "center_mauville_2f": ("10:6", 8, 8, "Mauville 宝可梦中心 2F", "interior"),
    "devon_1f": ("11:0", 8, 8, "Rustboro Devon 公司 1F", "interior"),
    "devon_2f": ("11:1", 1, 6, "Rustboro Devon 公司 2F", "interior"),
    "devon_3f": ("11:2", 3, 6, "Rustboro Devon 公司 3F", "interior"),
    "school_rustboro": ("11:4", 8, 8, "Rustboro 宝可梦学校", "interior"),
    "center_rustboro_2f": ("11:6", 8, 8, "Rustboro 宝可梦中心 2F", "interior"),
    "house_fortree1": ("12:0", 7, 5, "Fortree 民家 1", "interior"),
    "center_fortree_2f": ("12:3", 8, 8, "Fortree 宝可梦中心 2F", "interior"),
    "house_fortree2": ("12:5", 2, 4, "Fortree 民家 2", "interior"),
    "house_fortree3": ("12:6", 5, 5, "Fortree 民家 3", "interior"),
    "house_fortree4": ("12:7", 6, 5, "Fortree 民家 4", "interior"),
    "house_fortree5": ("12:8", 6, 5, "Fortree 民家 5", "interior"),
    "decor_fortree": ("12:9", 6, 6, "Fortree 装饰店", "counter"),
    "motel_lilycove_1f": ("13:0", 8, 8, "Lilycove 旅馆 1F", "interior"),
    "motel_lilycove_2f": ("13:1", 4, 7, "Lilycove 旅馆 2F", "interior"),
    "museum_lilycove_1f": ("13:2", 8, 8, "Lilycove 美术馆 1F", "interior"),
    "museum_lilycove_2f": ("13:3", 8, 8, "Lilycove 美术馆 2F", "interior"),
    "center_lilycove_2f": ("13:7", 8, 8, "Lilycove 宝可梦中心 2F", "interior"),
    "house_mossdeep1": ("14:1", 8, 8, "Mossdeep 民家 1", "interior"),
    "house_mossdeep2": ("14:2", 8, 8, "Mossdeep 民家 2", "interior"),
    "center_mossdeep_2f": ("14:4", 8, 8, "Mossdeep 宝可梦中心 2F", "interior"),
    "gym_sootopolis_b1f": ("15:1", 8, 8, "Sootopolis 道馆 B1F", "gym"),
    "center_sootopolis_2f": ("15:3", 8, 8, "Sootopolis 宝可梦中心 2F", "interior"),
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
-- ③ 普通室内：蛇形走位覆盖全屋，每格四方向用 **talk(soft)** 试探
--
--    ⚠ 教训（2026-11-04）：
--      · 原来用「四方向 tap + A」，house_mauville2 里 NPC 就在正上方、
--        朝向也对，但只按 A 就是不开框（实测 1 帧窗口）。
--      · 改用 talk(soft)：它以「文本真的推进」为判据，比单发 A 可靠。
local dirs = {{ "UP", "LEFT", "RIGHT", "DOWN" }}

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
    # ★ 手工维护的场景：不要被 --emit 覆盖。
    #   它们的落点来自 list_interactables 的实际输出，且带「为什么之前采不到」
    #   的详细注释。实测踩过：全量 --emit 把这俩文件的定制注释冲掉了。
    MANUAL = {"gym_dewford", "contest_lilycove"}
    skipped = []
    for n in names:
        if n not in SCENE_DEFS:
            print(f"[ERR] 未知场景 {n}")
            return 1
        if n in MANUAL and not a.only:
            skipped.append(n)
            continue
        p = SCENES / f"{n}.lua"
        p.write_text(gen(n), encoding="utf-8")
        print(f"[OK] {p.name}")
    if skipped:
        print(f"[skip] 手工场景未覆盖: {', '.join(skipped)}"
              f"（强制重生成请用 --only <名字>）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
