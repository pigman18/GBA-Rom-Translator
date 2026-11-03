-- ============================================================================
-- load.lua — 读档进游戏，抢"地图名弹窗"那一帧
--
-- 有存档时主菜单第一项是「つづきから」，按 A 直接继续。
-- 进图瞬间左上角会弹地图名（真新镇 = まさらたうん，配置里已译成中文）。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

api.wait(2800)
api.shot("title")
api.tap("START", 10, 240)
api.shot("menu")
api.tap("A", 8, 300)
api.shot("enter1")
api.prove()
api.wait(120)
api.shot("enter2")
api.tap("A", 6, 200)
api.shot("enter3")
api.wait(180)
api.shot("enter4")
api.wait(180)
api.shot("enter5")

return api.S
