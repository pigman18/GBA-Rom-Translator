-- ============================================================================
-- _probe_obj_pos2.lua — 按截图修正：NPC 在主角**下方**，朝 DOWN 试
--
-- 【上一轮观察】（003.png 放大看）
--   warp 到 (8,18) 后，主角在画面中央，**NPC 就在主角正下方一格**。
--   而 list_objects 解出的 obj[1] = (8,17) 在玩家原本 (8,15) 的**下方 2 格**。
--   ⇒ object 坐标的 y 方向与「屏幕上下」一致，但**落点 (8,18) 反而跑到了
--     NPC 上方** —— 说明 warp 落点的 y 与 object 表的 y 存在约 1~2 格偏移，
--     或者 (8,18) 那格本身不是我以为的位置。
--
-- 本探针不再猜偏移，改为**逐格靠近**：从 (8,18) 依次试 y=19,20,21
-- 的相邻格，每格都试四方向 talk，用日志里 TALK hit 判断哪一格能开框。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("o2_start")

api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("o2_outside")

-- 落在 NPC 附近的一个安全格
api.warp{ map = "3:3", x = 8, y = 18, mon = 1 }
api.wait(60)
api.shot("o2_arrive")
api.burst("o2_arrive_f", 8, 6)

-- 逐格靠近：每格四方向都试 talk（soft，打空继续）
local dirs = { "DOWN", "UP", "LEFT", "RIGHT" }
local tried = 0
for step = 1, 5 do
    for _, d in ipairs(dirs) do
        api.tap(d, 5, 18)
        api.talk{ timeout = 120, soft = true }
        tried = tried + 1
        api.shot(string.format("o2_s%d_%s", step, d))
        api.burst(string.format("o2_s%d_%s_f", step, d), 6, 5)
        for i = 1, 2 do
            api.tap("A", 5, 35)
        end
        api.tap("B", 4, 25)
    end
    -- 换一格（先用 DOWN 试，走不动 roam 会自动跳过）
    api.roam{ seq = { "DOWN" }, steps = 1 }
    api.shot(string.format("o2_step%d", step))
end

api.shot("o2_end")
return api.S
