-- ============================================================================
-- _probe_menu_map.lua — 开始菜单 8 项逐个探路（连续帧）
--
-- 目的：先用一次运行把「哪些菜单项真的能进、进去长什么样」摸清，
--       再据此写正式场景。避免每写一个场景就跑一轮双模拟器。
--
-- 每项：开菜单 → 顶格 → DOWN 到第 i 项 → shot(定妆) → A → burst 12 帧（看转场）
--       → 退回到野外（B 若干）
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("p0_overworld")

local N = 8
for i = 1, N do
    -- 打开菜单并移到第 i 项（先回顶，避免依赖进入时光标位置）
    api.tap("START", 4, 60)
    for _ = 1, N do api.tap("UP", 4, 6) end
    for _ = 1, i - 1 do api.tap("DOWN", 4, 10) end
    api.shot(string.format("p%d_on_%d", i, i))

    api.tap("A", 4, 10)
    api.burst(string.format("p%d_in_%d", i, i), 14, 3)

    -- 退回野外：B 最多 6 下，多按无副作用（野外 B 不做事）
    for _ = 1, 6 do api.tap("B", 4, 30) end
    api.shot(string.format("p%d_back_%d", i, i))
end

return api.S
