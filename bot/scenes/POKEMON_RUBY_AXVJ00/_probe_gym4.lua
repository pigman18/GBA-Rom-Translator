-- ============================================================================
-- _probe_gym4.lua — 绕过建筑，走到 Mauville City 北侧找道馆
--
-- 实测（_probe_gym3 日志 + 截图）：
--   出门后站在 map=0:2 (23,17)
--   向左走能到 (15,17)，再往北走到 (15,13) 就被建筑挡住
--   截图 012/020 显示：(15,13) 正上方是「粉顶房 + SHOP」，左侧是粉色大楼
--
-- 所以路线是：回街道 → 往左穿过建筑间隙 → 再北上。
-- 截图上左侧那栋**粉色大楼**很可能是道馆（Mauville Gym 外观是紫/粉色系）。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("g4_shop")

-- ① 出门（实测 DOWN 足够穿门）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("g4_outside")

-- ② 先往左走远一点，越过房子（截图上左侧有通道）
api.roam{ seq = { "DOWN", "LEFT", "LEFT", "LEFT", "LEFT" }, steps = 6 }
api.shot("g4_west_far")

-- ③ 北上（此时应已越过阻挡）
api.roam{ seq = { "UP", "UP", "UP", "UP", "UP" }, steps = 6 }
api.shot("g4_north")

-- ④ 再往左找粉色大楼的门
api.roam{ seq = { "LEFT", "LEFT", "LEFT", "LEFT" }, steps = 5 }
api.burst("g4_look", 12, 10)
api.shot("g4_look_end")

-- ⑤ 试按 A 进门
api.tap("A", 6, 60)
api.burst("g4_enter", 16, 8)
api.shot("g4_after_a")

return api.S
