-- ============================================================================
-- _probe_dew_final.lua — 走已验证路径到左上角，再在那里找 NPC
--
-- 【已验证的事实】
--   从落点 (8,18) 四面都走不动（BLOCKED），而 **(8,15) 可以走**：
--   实测路径能到 (2,7)（左上角），用了 21 步 roam。
--   截图显示 NPC（戴头巾的格斗家）就在左上角。
--   ⇒ 用落点 (8,15) + 已知可行路径，比继续换落点靠谱。
--
-- 【本轮做法】
--   1) warp 到 (8,15)（已验证可走）
--   2) 沿已验证路径走到 (2,7)
--   3) 在左上角 3x3 范围内逐格四方向试 A
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("df_start")

api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("df_outside")

api.warp{ map = "3:3", x = 8, y = 15, mon = 1 }
api.wait(60)
api.shot("df_arrive")

-- 已验证路径（能到左上角 (2,7)）
local path = {
    "LEFT", "LEFT", "LEFT", "UP", "UP", "UP", "UP",
    "RIGHT", "RIGHT", "UP", "UP", "UP", "UP",
    "LEFT", "LEFT", "LEFT", "LEFT", "LEFT",
    "UP", "UP", "UP",
}
local dirs = { "UP", "LEFT", "RIGHT", "DOWN" }
local n = 0
for _, d in ipairs(path) do
    api.roam{ seq = { d }, steps = 1 }
    n = n + 1
    -- 每走 3 格就把四方向 A 试一遍（密度够，帧数不至于爆炸）
    if n % 3 == 0 then
        api.shot(string.format("df_p%02d", n))
        for _, dd in ipairs(dirs) do
            api.tap(dd, 5, 16)
            api.tap("A", 6, 36)
            api.shot(string.format("df_p%02d_%s", n, dd))
            api.burst(string.format("df_p%02d_%s_f", n, dd), 4, 5)
            api.tap("B", 4, 18)
        end
    end
end

-- 到左上角后密集扫描
api.shot("df_at_corner")
for k = 1, 10 do
    for _, dd in ipairs(dirs) do
        api.tap(dd, 5, 16)
        api.tap("A", 6, 36)
        api.shot(string.format("df_c%d_%s", k, dd))
        api.tap("B", 4, 18)
    end
    -- 原地微调：交替上下左右各一格
    local d = ({"UP", "RIGHT", "DOWN", "LEFT"})[(k % 4) + 1]
    api.roam{ seq = { d }, steps = 1 }
end

api.shot("df_end")
return api.S
