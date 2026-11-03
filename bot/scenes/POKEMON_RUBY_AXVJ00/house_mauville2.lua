-- ============================================================================
-- house_mauville2.lua — Mauville 民家 2（map=10:4）
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
api.shot("hous_mauv_start")

-- ① 出门到城市（warp 需要先能自由行动；传送术在室内不可用）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("hous_mauv_outside")

-- ② 跳进目标地图
api.warp{ map = "10:4", x = 4, y = 6, mon = 1 }
api.wait(60)
api.shot("hous_mauv_inside")
api.burst("hous_mauv_enter_f", 14, 8)

-- ③ 普通室内：蛇形走位覆盖全屋，每格四方向用 **talk(soft)** 试探
--
--    ⚠ 教训（2026-11-04）：
--      · 原来用「四方向 tap + A」，house_mauville2 里 NPC 就在正上方、
--        朝向也对，但只按 A 就是不开框（实测 1 帧窗口）。
--      · 改用 talk(soft)：它以「文本真的推进」为判据，比单发 A 可靠。
local dirs = { "UP", "LEFT", "RIGHT", "DOWN" }

-- ★ 落点先用四方向 talk(soft) 试一轮再走开。
--   落点是按 NPC 坐标算出来的（calibrate_all.py），到位就该先试；
--   实测 house_mauville2 判模板先 LEFT 走掉，再也没回到 NPC 旁边
--   （轨迹 (3,6)→(2,6)→(1,6)→(1,5)→(1,3)→(2,2)，全程没碰 (4,6)）。
for _, dd in ipairs(dirs) do
    api.tap(dd, 5, 18)
    api.talk{ timeout = 120, soft = true }
    api.shot(string.format("hous_mauv_arrive_%s", dd))
    api.burst(string.format("hous_mauv_arrive_%s_f", dd), 6, 5)
    for i = 1, 2 do api.tap("A", 5, 35) end
    api.tap("B", 4, 22)
end

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
        api.shot(string.format("hous_mauv_p%02d", n))
        for _, dd in ipairs(dirs) do
            api.tap(dd, 5, 16)
            api.talk{ timeout = 110, soft = true }
            api.shot(string.format("hous_mauv_p%02d_%s", n, dd))
            api.burst(string.format("hous_mauv_p%02d_%s_f", n, dd), 4, 5)
            for i = 1, 2 do api.tap("A", 5, 32) end
            api.tap("B", 4, 20)
        end
    end
end
api.shot("hous_mauv_end")

return api.S
