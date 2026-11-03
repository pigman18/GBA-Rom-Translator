-- ============================================================================
-- _probe_gym.lua — 在 Mauville City 里找道馆入口
--
-- 已知（2026-11-03 实测）：
--   · 商店内 map=10:7 pos=(3,3)；向下走出门 ⇒ map=0:2 pos=(23,17)（城市户外）
--   · 走回门 ⇒ map=10:7 pos=(3,2)
--   · map=0:2 就是 Mauville City（截图有 SHOP 招牌、房屋、水面）
--
-- 道馆（ジム）在 Mauville City 的**北侧**（原版布局），
-- 本探针从商店门口往北走，沿途截图，到了门口按 A 进门。
-- 用 `map=` 判断有没有换图（进道馆会变成 10:x 之类的室内图）。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local X, Y = 3, 3      -- 商店内落点

L.preamble(api)
api.shot("gym_at_shop")

-- ① 走出商店（下门）
for i = 1, 8 do
    api.walk("DOWN", X, Y + i, 120, true, 16, "y")
end
api.shot("gym_outside")        -- 应落 map=0:2

-- ② 在城里往北走：先向左回到街道中线，再往上
--    城市可走区域坐标未知，所以用「逐格推进 + soft」扫
for i = 1, 10 do
    api.walk("LEFT", X - i, Y + 8, 100, true, 16, "x")
end
api.shot("gym_left")

for i = 1, 14 do
    api.walk("UP", X - 10, Y + 8 - i, 100, true, 16, "y")
end
api.shot("gym_north")

-- ③ 到北边横向扫，找带「ジム」的门
for i = 1, 8 do
    api.walk("RIGHT", X - 10 + i, Y + 8 - 14, 100, true, 16, "x")
end
api.burst("gym_scan", 10, 10)
api.shot("gym_scan_end")

-- ④ 试按 A（如果正对着门，会进图）
api.tap("A", 6, 60)
api.burst("gym_try_a", 14, 8)
api.shot("gym_after_a")

return api.S
