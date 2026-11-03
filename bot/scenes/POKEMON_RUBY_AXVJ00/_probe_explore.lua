-- ============================================================================
-- _probe_explore.lua — 从现有存档出发，探明「还能走到哪些新场景」
--
-- 背景：换地图靠改 .sav 已被证伪（地图是读档流程加载的，不是 location 驱动），
--       所以大赛/道馆只能**在游戏内走过去**。先用探针把可用出口摸清。
--
-- 做法：从起点出发，逐格朝四个方向推进，直到走不动为止。
--   walk 用 soft=true：撞墙不算失败（walk 内部会记 BLOCKED），
--   正好用来判断"这个方向最远能到哪一格"。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("ex_start")

-- 逐格推进：每个方向最多推 N 格，每格一个 walk（目标格由 Lua 递增）
-- ⚠ 目标坐标必须**真实递增**：walk 的语义是「按住方向直到坐标到目标格」，
--   写 (0,0) 会立刻判到位、一格都不走（踩过）。
local START_X, START_Y = 68, 7
local N = 8

-- 向上
for i = 1, N do
    api.walk("UP", START_X, START_Y - i, 120, true, 16, "y")
end
api.shot("ex_up_max")

-- 向下（回到起点再往下）
for i = 1, N do
    api.walk("DOWN", START_X, START_Y + i, 120, true, 16, "y")
end
api.shot("ex_down_max")

-- 向左
for i = 1, N do
    api.walk("LEFT", START_X - i, START_Y + N, 120, true, 16, "x")
end
api.shot("ex_left_max")

-- 向右
for i = 1, N do
    api.walk("RIGHT", START_X + i, START_Y + N, 120, true, 16, "x")
end
api.burst("ex_right_burst", 12, 10)

return api.S
