-- ============================================================================
-- play2.lua — 继续连按 A：博士开场 → 选性别 → 取名 → 进屋
--
-- 取名画面连按 A 会走"默认名字 + 确认"，不需要打字。
-- 每 8 次按 A 截一张，用来定位"走到第几屏"。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

api.wait(2800)
api.tap("START", 10, 220)
api.tap("A", 8, 260)

for i = 1, 48 do
    api.tap("A", 5, 110)
    if i % 8 == 0 then api.shot(string.format("a%02d", i)) end
end

api.wait(200)
api.shot("end")

return api.S
