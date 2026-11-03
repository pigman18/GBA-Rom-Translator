-- _diag.lua — 定位标题画面出现时机（高密度采样，不按键）
--
-- 已知：origin 在 f=3664 出现标题（dispcnt=0x1741）。
--   translated（带 hook）在同一帧点没命中，且 keysRead 在 f=3838 后停摆。
-- 本场景逐 200 帧拍到 f=5000，直接看标题何时出现 / 是否出现。
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

for i = 1, 25 do
    api.wait(200)
    api.shot(string.format("f%04d", i * 200))
end

return api.S
