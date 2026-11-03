-- ============================================================================
-- _probe_gym_contact.lua — 精确定位「贴到 NPC 身边」的坐标
--
-- 现状：warp 进道馆 (5,8) 成功；走到 (5,3) 后按 A（四个方向都试）
--       全都没开对话框。
-- 从截图判读：主角（橙色）与右侧训练家（深色）之间似乎隔了一格。
--
-- 本轮改用「小范围网格 + 每点四方向按 A」的组合扫描，并把每张都存下来，
-- 事后按 VRAM 差异挑出"真的开了对话框"的那一帧（对话框会大面积改写
-- 底部 tilemap，与纯行走帧差异极大）。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("gc_start")

api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("gc_outside")

api.warp{ map = "10:0", x = 5, y = 8, mon = 1 }
api.wait(60)
api.shot("gc_inside")

-- 从 (5,8) 往上走，最多 8 格；每走一格就在四方向试 A
-- 这样无论 NPC 在哪一格，总会有一格贴上
local dirs = { "UP", "LEFT", "RIGHT", "DOWN" }
for step = 1, 8 do
    api.roam{ seq = { "UP" }, steps = 1 }
    api.shot(string.format("gc_pos%d", step))
    for _, d in ipairs(dirs) do
        api.tap(d, 5, 20)               -- 转身
        api.tap("A", 6, 45)             -- 试对话
        api.shot(string.format("gc_s%d_%s", step, d))
        api.tap("B", 4, 25)             -- 有对话就关掉
    end
end

return api.S
