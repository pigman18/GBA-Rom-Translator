-- ============================================================================
-- load2.lua — 读档 → 跳过"これまでの あらすじ"回顾 → 落到地图（抢地图名弹窗）
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

api.wait(2800)
api.tap("START", 10, 240)
api.tap("A", 8, 300)
api.prove()

for i = 1, 36 do
    api.tap("A", 6, 140)
    if i % 6 == 0 then api.shot(string.format("p%02d", i)) end
end

api.wait(240)
api.shot("map")
api.wait(180)
api.shot("map2")

return api.S
