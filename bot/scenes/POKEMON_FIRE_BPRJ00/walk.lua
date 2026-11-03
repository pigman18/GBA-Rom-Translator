-- ============================================================================
-- walk.lua — 连按 A 进游戏，然后从卧室走到镇上
--
-- 目标：踩到"进入新地图"的那一帧，让**地图名弹窗**出现（まさらたうん）。
-- 这条串在配置里已经译成「真新镇」，所以它是"中文真的上屏了"最直接的证据。
-- 路线依据卧室布局：楼梯在右上角 → 下楼 → 一楼往门口走。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

api.wait(2800)
api.tap("START", 10, 220)
api.tap("A", 8, 260)
for i = 1, 100 do api.tap("A", 5, 110) end
api.wait(200)
api.shot("room")

api.tap("RIGHT", 24, 120)
api.tap("UP", 30, 160)
api.shot("stairs")

api.tap("DOWN", 30, 120)
api.tap("DOWN", 30, 120)
api.shot("floor1")

api.tap("DOWN", 30, 120)
api.tap("DOWN", 30, 150)
api.shot("door")
api.wait(200)
api.shot("town")
api.tap("DOWN", 30, 200)
api.shot("town2")

return api.S
