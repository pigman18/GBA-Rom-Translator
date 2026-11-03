-- ============================================================================
-- _probe_door.lua — 用你手动存的「商店内」存档，验证能否走出门
--
-- 存档实测：roms/outputs/POKEMON_RUBY_AXVJ00_translated.sav
--           map=10:7 pos=(3,7)（Mauville City 商店内）
--
-- 前面已证实：从商店 (3,3) 向下走 ⇒ map=0:2 pos=(23,17)（城市户外）。
-- 本探针只用最朴素的 walk（不用 roam），把出门这一步走通，
-- 顺便确定这只商店的门在哪一侧。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("door_in_shop")           -- 应在 map=10:7

-- 存档坐标 (3,7)：先往上走（门通常在北墙）
for i = 1, 6 do
    api.walk("UP", 3, 7 - i, 100, true, 16, "y")
end
api.shot("door_up6")

-- 再往下走穿过整间店
for i = 1, 12 do
    api.walk("DOWN", 3, 7 - 6 + i, 100, true, 16, "y")
end
api.shot("door_down12")

-- 若还没出去，横向试
for i = 1, 6 do
    api.walk("LEFT", 3 - i, 7, 100, true, 16, "x")
end
api.shot("door_left6")

for i = 1, 12 do
    api.walk("RIGHT", 3 - 6 + i, 7, 100, true, 16, "x")
end
api.burst("door_right_burst", 10, 10)

return api.S
