-- ============================================================================
-- _probe_gym_npc.lua — 在道馆里找出「能对话的站位与朝向」
--
-- 已确认：warp{map="10:0"} 成功进道馆（截图：黄色格子地面 + 白柱子 + 多名训练家）。
-- 但从 (5,8) 走到 (5,3) 面朝上按 A，talk 闸门报「没打到对话」。
--
-- 本探针不做 talk（会因打空而中断），改成**每个方向都试一次 A**，
-- 看哪个方向能让 DISPCNT/窗口发生变化（有对话框出现）。
-- 用 shot 记录，事后人工看哪张有对话框。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("gn_start")

api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("gn_outside")

api.warp{ map = "10:0", x = 5, y = 8, mon = 1 }
api.wait(60)
api.shot("gn_inside")

-- 往上走两格（到 (5,6)）后，四方向逐个试
api.roam{ seq = { "UP", "UP" }, steps = 3 }
api.shot("gn_up2")

-- 四个方向各转一次身 + 按 A，每个都截图
local dirs = { "UP", "DOWN", "LEFT", "RIGHT" }
for i, d in ipairs(dirs) do
    api.tap(d, 5, 25)                 -- 仅转身
    api.shot(string.format("gn_face_%s", d))
    api.tap("A", 6, 50)               -- 试对话
    api.shot(string.format("gn_a_%s", d))
    api.burst(string.format("gn_a_%s_f", d), 6, 6)
    -- 如果真开了对话，按 B 关掉再试下一个方向
    api.tap("B", 4, 30)
    api.shot(string.format("gn_b_%s", d))
end

-- 再往上走一格，重复一轮（NPC 可能在更近的位置）
api.roam{ seq = { "UP" }, steps = 2 }
api.shot("gn_upmore")
for i, d in ipairs(dirs) do
    api.tap(d, 5, 25)
    api.tap("A", 6, 50)
    api.shot(string.format("gn2_a_%s", d))
    api.tap("B", 4, 30)
end

return api.S
