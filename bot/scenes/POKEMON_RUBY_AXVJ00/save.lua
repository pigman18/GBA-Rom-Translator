-- ============================================================================
-- save.lua — レポート（保存确认）
--
-- 【到达目标】野外 → START → 第 6 项「レポート」→ A
--   → 左上存档信息框 + 底部确认句 + 是/否
--
-- 【为什么必须做这个场景】
--   1) 确认句曾因 UI界面 group=文本 被 unresolved_redirect，整句留日文
--   2) 信息框标签（徽章/图鉴/时间）与确认句同屏，是存档文案回归面
--   选「否」退出，不写盘。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("overworld")

L.open_menu_at(api, L.MENU.SAVE)
api.shot("save_on_item")
api.tap("A", 4, 90)
-- 信息框 + 确认句淡入
api.burst("save_enter_f", 16, 8)
api.shot("save_enter")
api.wait(40)
api.shot("save_confirm")

-- 下移到「否」再确认取消（避免写档）
api.tap("DOWN", 4, 30)
api.shot("save_on_no")
api.tap("A", 4, 60)
api.burst("save_cancel_f", 10, 6)
api.shot("save_cancelled")

L.exit_to_overworld(api, 4, "save_closed")

return api.S
