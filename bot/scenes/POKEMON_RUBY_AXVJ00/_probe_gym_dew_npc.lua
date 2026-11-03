-- ============================================================================
-- _probe_gym_dew_npc.lua — 按截图定位：Dewford 道馆的 NPC 在左上角
--
-- 【关键观察】（_probe_obj_pos3 的 003.png，放大后）
--   warp 到 (8,18) 时，主角在画面中央偏右，**唯一的 NPC 在左上角**
--   （戴头巾的格斗家）。主角正下方那个橙色方块是**木箱/地板装饰**，
--   不是 NPC —— 这解释了为什么朝它按 A 全部超时。
--
--   而 object 表里那 4 个坐标 (8,17)(9,24)(12,31)(19,31) 都不在左上角，
--   说明它们不是「人物」，而是**场景物件**（门/楼梯/箱子）。
--   ⇒ 结论：object 表不是找 NPC 的正确数据源（至少在这张图），
--     真正可行的还是**按画面走位**。
--
-- 【本轮做法】从落点往左上角走到 NPC 旁，边走近边试 A。
--   用「大跨度 roam + 每段截图」覆盖左上区域。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("dn_start")

api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("dn_outside")

api.warp{ map = "3:3", x = 8, y = 18, mon = 1 }
api.wait(60)
api.shot("dn_arrive")

-- 往左上走（截图里 NPC 在左上角）
api.roam{ seq = { "LEFT", "LEFT", "LEFT" }, steps = 3 }
api.shot("dn_left")

api.roam{ seq = { "UP", "UP", "UP" }, steps = 3 }
api.shot("dn_upleft")

-- 到左上区域后，逐格四方向试 A
local dirs = { "UP", "LEFT", "RIGHT", "DOWN" }
for step = 1, 8 do
    for _, d in ipairs(dirs) do
        api.tap(d, 5, 16)
        api.tap("A", 6, 36)
        api.shot(string.format("dn_s%d_%s", step, d))
        api.burst(string.format("dn_s%d_%s_f", step, d), 4, 5)
        api.tap("B", 4, 18)
    end
    -- 蛇形推进
    local d = (step % 2 == 1) and "UP" or "RIGHT"
    api.roam{ seq = { d }, steps = 1 }
    api.shot(string.format("dn_p%d", step))
end

api.shot("dn_end")
return api.S
