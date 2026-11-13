-- ============================================================================
-- _probe_start_reopen.lua — 复现开始菜单残墨
--
-- 用户路径：START 开 → START 关 → START 再开 → 上下移动 → 出现残留
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("overworld")

-- 1) 第一次打开
api.tap("START", 4, 60)
api.burst("open1_f", 8, 4)
api.shot("open1")

-- 2) START 关闭
api.tap("START", 4, 60)
api.burst("close1_f", 6, 4)
api.shot("closed1")

-- 3) 再打开
api.tap("START", 4, 60)
api.burst("open2_f", 8, 4)
api.shot("open2")

-- 4) 上下移动（残墨触发段）
for i = 1, 4 do
    api.tap("DOWN", 4, 8)
    api.burst(string.format("down%d_f", i), 6, 3)
    api.shot(string.format("down%d", i))
end
for i = 1, 3 do
    api.tap("UP", 4, 8)
    api.burst(string.format("up%d_f", i), 6, 3)
    api.shot(string.format("up%d", i))
end

api.tap("START", 4, 40)
api.shot("final_closed")

return api.S
