-- ============================================================================
-- boot.lua — 开机采集：开场 → 标题(Press Start) → 主菜单
--
-- 日版火红：标题画面按 START（不是 A）进入
--   つづきから / さいしょから / オプション
-- phase-1 把这三项换成 F7 测试字形；mainmenu 帧必须相对 origin 有新增墨迹。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

api.wait(2800)                 -- 跨过版权 + 开场动画，落到可按 START 的标题
api.shot("title")

api.tap("START", 10, 180)      -- ★ 进主菜单
api.wait(240)
api.shot("mainmenu")

api.tap("DOWN", 6, 60)
api.shot("mainmenu_down")

return api.S
