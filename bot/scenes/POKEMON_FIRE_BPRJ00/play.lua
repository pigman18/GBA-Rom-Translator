-- ============================================================================
-- play.lua — 一路按 A 穿过博士开场，落到游戏世界
--
-- 为什么用"连按 A"而不是精确脚本：开场是线性对话，按 A 是唯一推进方式；
-- 连按 N 次比逐条对位更抗版本差异（叶绿/绿宝石同理可用）。
-- 每 6 次按 A 截一张，方便回看"走到第几屏了"。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

api.wait(2800)
api.tap("START", 10, 220)
api.tap("A", 8, 260)

for i = 1, 10 do
    api.tap("A", 6, 150)
    if i % 2 == 0 then api.shot(string.format("press%02d", i)) end
end

api.wait(240)
api.shot("world")
api.tap("DOWN", 12, 120)
api.tap("DOWN", 12, 120)
api.shot("walk1")

return api.S
