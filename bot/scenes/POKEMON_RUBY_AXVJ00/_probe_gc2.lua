-- ============================================================================
-- _probe_gc2.lua — 游戏厅：从 (8,10) 先往右绕，再往上接近 NPC
--
-- 【观察】（003.png 放大）
--   warp 到 (8,10) 时主角在下方中央，**正上方 2 格就有绿帽女性 NPC**，
--   左侧是老虎机区（多家 NPC），右侧有柜台/告示牌。
--   但之前直接按 UP 被挡 —— 主角紧贴老虎机台的边缘。
--
-- 【本轮做法】先 RIGHT 走 2 格绕开，再 UP 上去，然后四方向试 A。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("gc2_start")

api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("gc2_outside")

api.warp{ map = "10:3", x = 8, y = 10, mon = 1 }
api.wait(60)
api.shot("gc2_arrive")

-- 先右绕 2 格，再上行
api.roam{ seq = { "RIGHT", "RIGHT" }, steps = 2 }
api.shot("gc2_right")
api.roam{ seq = { "UP", "UP", "UP" }, steps = 2 }
api.shot("gc2_up")

-- 逐格四方向试 A
local dirs = { "UP", "LEFT", "RIGHT", "DOWN" }
for k = 1, 8 do
    for _, d in ipairs(dirs) do
        api.tap(d, 5, 16)
        api.tap("A", 6, 36)
        api.shot(string.format("gc2_k%d_%s", k, d))
        api.burst(string.format("gc2_k%d_%s_f", k, d), 4, 5)
        api.tap("B", 4, 18)
    end
    local d = ({"UP", "LEFT", "UP", "RIGHT"})[(k % 4) + 1]
    api.roam{ seq = { d }, steps = 1 }
end
api.shot("gc2_end")
return api.S
