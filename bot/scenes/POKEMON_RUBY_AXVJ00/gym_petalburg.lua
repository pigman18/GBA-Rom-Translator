-- ============================================================================
-- gym_petalburg.lua — Petalburg 道馆（普通）（map=8:1）
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
api.shot("gym_peta_start")

-- ① 出门到城市（warp 需要先能自由行动；传送术在室内不可用）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("gym_peta_outside")

-- ② 跳进目标地图
api.warp{ map = "8:1", x = 4, y = 17, mon = 1 }
api.wait(60)
api.shot("gym_peta_inside")
api.burst("gym_peta_enter_f", 14, 8)

-- ③ 道馆：两段式扫（先竖扫，再蛇形），每格四方向试 A
--
--    ⚠ 教训（实测 4 轮，很重要）：
--      · gym_lavaridge 用「向上走 6 格 + 每格四方向 A」能采到 **31 个窗口**；
--        换成显式蛇形路径后掉到 1 个 ⇒ **竖扫对这个道馆更有效**。
--      · gym_dewford 反过来：竖扫 1 个，蛇形也 1 个（NPC 在并列走道，
--        隔墙打不到）—— 这是地图结构限制，不是路径问题。
--      · 所以模板走**两段**：先竖扫，再蛇形，两种布局都照顾到。
local dirs = { "UP", "LEFT", "RIGHT", "DOWN" }

-- 第一段：竖扫（对 Lavaridge 这类「一路向上」的道馆有效）
for step = 1, 6 do
    api.roam{ seq = { "UP" }, steps = 1 }
    api.shot(string.format("gym_peta_v%d", step))
    for _, d in ipairs(dirs) do
        api.tap(d, 5, 16)
        api.tap("A", 6, 38)
        api.shot(string.format("gym_peta_v%d_%s", step, d))
        api.tap("B", 4, 20)
    end
end
api.shot("gym_peta_vs_end")

-- 第二段：蛇形（覆盖侧翼 NPC）
local path = {
    "LEFT", "LEFT", "LEFT", "DOWN", "DOWN", "DOWN",
    "RIGHT", "RIGHT", "RIGHT", "UP", "UP",
}
local n = 0
for _, d in ipairs(path) do
    api.roam{ seq = { d }, steps = 1 }
    n = n + 1
    api.shot(string.format("gym_peta_p%02d_%s", n, d))
    for _, dd in ipairs(dirs) do
        api.tap(dd, 5, 16)
        api.tap("A", 6, 38)
        api.shot(string.format("gym_peta_p%02d_%s_%s", n, d, dd))
        api.tap("B", 4, 20)
    end
end
api.shot("gym_peta_end")

return api.S
