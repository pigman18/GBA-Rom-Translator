-- ============================================================================
-- play3.lua — 连按 A 直到进入游戏世界（穿过取名、开场后对话、屋内）
-- 每 10 次按 A 截一张；末尾多截一张确认落点。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

api.wait(2800)
api.tap("START", 10, 220)
api.tap("A", 8, 260)

for i = 1, 100 do
    api.tap("A", 5, 110)
    if i % 10 == 0 then api.shot(string.format("a%03d", i)) end
end

api.wait(240)
api.shot("end")

return api.S
