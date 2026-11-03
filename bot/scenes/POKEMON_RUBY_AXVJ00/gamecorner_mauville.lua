-- ============================================================================
-- gamecorner_mauville.lua — Mauville 游戏厅（map=10:3）
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
api.shot("game_mauv_start")

-- ① 出门到城市（warp 需要先能自由行动；传送术在室内不可用）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("game_mauv_outside")

-- ② 跳进目标地图
api.warp{ map = "10:3", x = 8, y = 10, mon = 1 }
api.wait(60)
api.shot("game_mauv_inside")
api.burst("game_mauv_enter_f", 14, 8)

-- ③ 柜台在侧面：先侧移再上行，然后四方向 talk
--
--    ⚠ 实测（bikeshop_mauville）：
--      · 先 UP 4 格 → 四方向 talk   ⇒ **1 帧**（打空）
--      · 先 RIGHT 2 格 → UP 4 格   ⇒ **139 帧** ✅
--      截图显示店主在主角**右上方**，所以必须先侧移。
--    （商店/PC 相反：它们要先直上，固定侧移会离开柜台。）
api.roam{ seq = { "RIGHT", "RIGHT" }, steps = 2 }
api.shot("game_mauv_side")
api.roam{ seq = { "UP", "UP", "UP", "UP" }, steps = 4 }
api.shot("game_mauv_at_counter")

local probe = { "UP", "RIGHT", "LEFT", "DOWN" }
for _, d in ipairs(probe) do
    api.tap(d, 5, 22)
    api.talk{ timeout = 200, soft = true }
    api.burst(string.format("game_mauv_dlg_%s_f", d), 10, 5)
    api.shot(string.format("game_mauv_dlg_%s", d))
    for i = 1, 4 do
        api.tap("A", 5, 42)
        api.shot(string.format("game_mauv_dlg_%s_%d", d, i))
    end
    api.tap("B", 4, 30)
end

-- 退出后试菜单（选车/看车列表）
api.tap("A", 6, 60)
api.burst("game_mauv_menu_f", 12, 8)
api.shot("game_mauv_menu")
for i = 1, 6 do
    api.tap("DOWN", 4, 28)
    api.shot(string.format("game_mauv_item%d", i))
end
api.tap("B", 4, 45)
api.shot("game_mauv_end")

return api.S
