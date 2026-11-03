-- ============================================================================
-- _probe_lily2.lua — 华丽大赛大厅（Lilycove）：先绕行再接近 NPC
--
-- 【观察】（contest_lilycove 的 003.png 放大）
--   warp 到 (10,12) 时主角在画面中央偏下，**画面上方有多个 NPC**，
--   右上角一位深衣 NPC 最近。会场地面是大片地毯，可走区域很大。
--   ⇒ 空场走位没问题，问题是「走得太少」：interior 模板只走了 5 步。
--
-- 【本轮做法】先往上走 5 格，再左右扫，每格四方向试 A。
--   与游戏厅的成功经验一致（先绕开、再接近）。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("ly2_start")

api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("ly2_outside")

api.warp{ map = "13:5", x = 10, y = 12, mon = 1 }
api.wait(60)
api.shot("ly2_arrive")

-- 往上走到 NPC 区
api.roam{ seq = { "UP", "UP", "UP" }, steps = 4 }
api.shot("ly2_up")
api.roam{ seq = { "UP", "UP" }, steps = 3 }
api.shot("ly2_up2")

-- 逐格四方向试 A，蛇形覆盖
local dirs = { "UP", "LEFT", "RIGHT", "DOWN" }
local plan = { "LEFT", "LEFT", "LEFT", "DOWN", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "UP", "UP", "LEFT", "LEFT" }
for k, d in ipairs(plan) do
    for _, dd in ipairs(dirs) do
        api.tap(dd, 5, 16)
        api.tap("A", 6, 36)
        api.shot(string.format("ly2_k%02d_%s", k, dd))
        api.burst(string.format("ly2_k%02d_%s_f", k, dd), 4, 5)
        api.tap("B", 4, 18)
    end
    api.roam{ seq = { d }, steps = 1 }
    api.shot(string.format("ly2_p%02d", k))
end

api.shot("ly2_end")
return api.S
