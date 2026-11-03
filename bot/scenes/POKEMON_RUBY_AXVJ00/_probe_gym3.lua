-- ============================================================================
-- _probe_gym3.lua — 从商店出门后，用 roam 找 Mauville City 道馆
--
-- 实测路线（已确认，不要再猜）：
--   读档 map=10:7 pos=(3,7)（商店内，站在门口）
--   → DOWN 向下走穿出门 ⇒ map=0:2 pos=(23,17)（Mauville City 街道）
--   → 街道上可左右走到 (15,17) / (34,17)，说明东西向通畅
--
-- Mauville City 原版布局：**道馆在城市北侧**（从商店门口往北/西北）。
-- 本探针：先复现出门，然后用 roam 往北推，每段截图，靠 map= 判断是否进图。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("g3_shop")

-- ① 出门：直接往 DOWN 走够（实测 12 格足够穿门）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("g3_outside")            -- 应 map=0:2

-- ② 往北推：先左一点到街道中线，再一路 UP
api.roam{ seq = { "LEFT", "LEFT", "UP", "UP", "UP", "UP" }, steps = 6 }
api.shot("g3_north")

api.roam{ seq = { "UP", "UP", "UP", "UP" }, steps = 8 }
api.shot("g3_north2")

-- ③ 在北侧横向扫：找带门/招牌的建筑
api.roam{ seq = { "LEFT", "LEFT", "LEFT", "LEFT", "LEFT", "LEFT" }, steps = 6 }
api.shot("g3_west")

api.roam{ seq = { "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT",
                  "RIGHT", "RIGHT", "RIGHT", "RIGHT" }, steps = 6 }
api.burst("g3_east_burst", 12, 10)
api.shot("g3_east")

-- ④ 试着按 A（若正对门会进图）
api.tap("A", 6, 60)
api.burst("g3_try_a", 14, 8)
api.shot("g3_after_a")

return api.S
