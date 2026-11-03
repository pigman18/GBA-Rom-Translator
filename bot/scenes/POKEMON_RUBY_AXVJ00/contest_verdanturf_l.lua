-- ============================================================================
-- contest_verdanturf_l.lua — Verdanturf 大赛大厅（map=6:0）
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
api.shot("cont_l_start")

-- ① 出门到城市（warp 需要先能自由行动；传送术在室内不可用）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("cont_l_outside")

-- ② 跳进目标地图
api.warp{ map = "6:0", x = 7, y = 6, mon = 1 }
api.wait(60)
api.shot("cont_l_inside")
api.burst("cont_l_enter_f", 14, 8)

-- ③ 普通室内：蛇形走位覆盖全屋，每格四方向试 A（找 NPC / 告示牌）
--
--    ⚠ 教训（contest_lilycove 实测）：只往上走 5 格，43 帧里只有 1 帧有窗口。
--      室内 NPC 常在侧面，必须横向也扫。
local dirs = { "UP", "LEFT", "RIGHT", "DOWN" }
local plan = {
    { "LEFT", "LEFT", "LEFT" },
    { "UP", "UP" },
    { "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT" },
    { "UP", "UP" },
    { "LEFT", "LEFT", "LEFT", "LEFT" },
}
local n = 0
for _, seg in ipairs(plan) do
    for _, d in ipairs(seg) do
        api.roam{ seq = { d }, steps = 1 }
        n = n + 1
        api.shot(string.format("cont_l_p%02d", n))
        for _, dd in ipairs(dirs) do
            api.tap(dd, 5, 18)
            api.tap("A", 6, 40)
            api.shot(string.format("cont_l_p%02d_%s", n, dd))
            api.tap("B", 4, 22)
        end
    end
end
api.shot("cont_l_end")

return api.S
