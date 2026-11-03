-- ============================================================================
-- intro.lua — 开机 → 标题 → 主菜单 → 进游戏 → 博士开场
--
-- 目的：让**新游戏前几分钟**的文本出现在画面里，这样"中日对位"可以直接用截图看。
-- 不读档（两侧都没有 .sav），所以两侧走的是同一条"新开局"路径，帧对齐可比。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

api.wait(2800)
api.shot("title")

api.tap("START", 10, 200)
api.shot("menu")

api.tap("A", 8, 260)          -- 主菜单第一项（无存档时是"最初から"）
api.shot("after_menu")

api.tap("A", 8, 240)          -- 博士开场第一屏
api.shot("intro1")
api.tap("A", 8, 200)
api.shot("intro2")
api.tap("A", 8, 200)
api.shot("intro3")
api.tap("A", 8, 200)
api.shot("intro4")

return api.S
