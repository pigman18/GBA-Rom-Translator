-- ============================================================================
-- _probe_gym2.lua — 用 roam 从商店走到 Mauville City 道馆
--
-- 已知（实测）：
--   商店 map=10:7 pos=(3,3)；向下走出门 ⇒ map=0:2 pos=(23,17)（城市）
--   换图会重置坐标 ⇒ 必须用 roam（只按方向，不看绝对坐标）
--
-- Mauville City 原版布局：道馆在城市**北侧/西北**。
-- 本探针分两段：
--   ① 出门（DOWN 8 格）
--   ② 往北 + 往西扫，每段结束截图，靠 map= 判断是否已进道馆
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("g2_in_shop")

-- ① 出门
api.roam{ seq = { "DOWN", "DOWN" }, steps = 6 }
api.shot("g2_outside")

-- ② 城市里往北（UP 多走），再往西（LEFT），每段截图
api.roam{ seq = { "LEFT", "UP", "UP", "UP", "UP" }, steps = 6 }
api.shot("g2_north")

api.roam{ seq = { "UP", "RIGHT", "RIGHT" }, steps = 6 }
api.shot("g2_north2")

-- ③ 到北侧后横向扫一遍找门
api.roam{ seq = { "LEFT", "LEFT", "LEFT", "LEFT", "LEFT", "LEFT" }, steps = 5 }
api.burst("g2_scan", 12, 10)
api.shot("g2_scan_end")

-- ④ 试进（正对门按 A）
api.tap("A", 6, 60)
api.burst("g2_try_enter", 14, 8)
api.shot("g2_after_a")

return api.S
