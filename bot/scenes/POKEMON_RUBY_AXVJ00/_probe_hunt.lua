-- ============================================================================
-- _probe_hunt.lua — 验证 hunt（遇敌搜捕）能否让两侧都停在战斗画面
--
-- 设计（用户选定）：不追求「第 N 格必遇敌」，改成**一遇敌就停**。
--   hunt 逐帧看 DISPCNT，一旦不是野外值 0x7F60 立刻停手并 advance，
--   后面的采集全部从战斗画面开始 ⇒ 两侧起点界面一致。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("hunt_overworld")

-- 走进草丛并持续搜捕（最多 30 格）
api.hunt{ dir = "DOWN", x = 68, y = 7, steps = 30, timeout = 120 }

-- 到这里必然「已遇敌」或「走完没遇到」，用 await 判定并连帧采集
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 600, tag = "battle" }
api.burst("hunt_transition", 16, 8)
api.shot("hunt_in_battle")

return api.S
