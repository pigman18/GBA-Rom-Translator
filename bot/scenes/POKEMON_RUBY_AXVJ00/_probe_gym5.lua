-- ============================================================================
-- _probe_gym5.lua — 绕过花坛，走到截图里那栋「粉色大楼拱形门」
--
-- 已从截图 005.png 看清布局（map=0:2 Mauville City）：
--   · 主角在 (15,17)，正上方是花坛（挡路）
--   · **左侧那栋粉色大楼带拱形门 = 道馆入口**（原版 Mauville Gym 外形）
--   · 花坛左右各有一条通道
--
-- 做法：先下再左（绕开花坛），再上（贴到门前的走道），按 A 进门。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("g5_shop")

-- ① 出门
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("g5_outside")

-- ② 往左走到花坛左侧（多次 LEFT，撞墙会自动跳过）
api.roam{ seq = { "LEFT", "LEFT", "LEFT" }, steps = 6 }
api.shot("g5_left")

-- ③ 向下绕开（走到花坛下沿的走道）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 4 }
api.shot("g5_down")

-- ④ 再往左贴到粉楼门前
api.roam{ seq = { "LEFT", "LEFT", "LEFT", "LEFT" }, steps = 5 }
api.shot("g5_at_door")

-- ⑤ 往上顶到门口并进门
api.roam{ seq = { "UP", "UP" }, steps = 4 }
api.shot("g5_door_front")
api.tap("A", 6, 60)
api.burst("g5_enter", 18, 8)
api.shot("g5_inside")

-- ⑥ 若已进门（map 变了），再按 A 推进剧情
api.tap("A", 6, 60)
api.burst("g5_inside2", 14, 8)
api.shot("g5_inside2_end")

return api.S
