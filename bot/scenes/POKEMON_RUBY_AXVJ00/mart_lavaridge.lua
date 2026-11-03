-- ============================================================================
-- mart_lavaridge.lua — Lavaridge 商店（map=4:4）
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
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("mart_lava_start")

-- ① 出门到城市（warp 需要先能自由行动；传送术在室内不可用）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("mart_lava_outside")

-- ② 跳进目标地图
api.warp{ map = "4:4", x = 7, y = 8, mon = 1 }
api.wait(60)
api.shot("mart_lava_inside")
api.burst("mart_lava_enter_f", 14, 8)

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
api.roam{ seq = { "UP", "UP", "UP", "UP" }, steps = 4 }
api.shot("mart_lava_at_counter")

local probe = { "UP", "RIGHT", "LEFT", "DOWN" }
for _, d in ipairs(probe) do
    api.tap(d, 5, 22)
    api.talk{ timeout = 150, soft = true }
    api.burst(string.format("mart_lava_dlg_%s_f", d), 10, 5)
    api.shot(string.format("mart_lava_dlg_%s", d))
    -- 若真开了框，多推两句（把这段对话采完整）
    for i = 1, 3 do
        api.tap("A", 5, 40)
        api.shot(string.format("mart_lava_dlg_%s_%d", d, i))
    end
    api.tap("B", 4, 30)
end

-- 逐句推进（每句连帧，覆盖逐字打印与换句重绘）
for i = 1, 8 do
    api.tap("A", 5, 45)
    api.burst(string.format("mart_lava_dlg%d_f", i + 1), 6, 6)
    api.shot(string.format("mart_lava_dlg%d", i + 1))
end

-- ④ 退出后试菜单（商店/PC 都有列表）
api.tap("B", 4, 40)
api.shot("mart_lava_menu_try")
api.tap("A", 6, 55)
api.burst("mart_lava_menu_f", 12, 8)
api.shot("mart_lava_menu")
for i = 1, 6 do
    api.tap("DOWN", 4, 26)
    api.burst(string.format("mart_lava_item%d_f", i), 5, 6)
    api.shot(string.format("mart_lava_item%d", i))
end
api.tap("B", 4, 45)
api.shot("mart_lava_end")

return api.S
