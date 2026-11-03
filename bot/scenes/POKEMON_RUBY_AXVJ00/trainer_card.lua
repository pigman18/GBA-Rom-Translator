-- ============================================================================
-- trainer_card.lua — 训练家卡片（ユウキ）
--
-- 【到达目标】野外 → START → 第 5 项「ユウキ」→ A
--   → 训练家卡片（名字 / ID / 金钱 / 游戏时间 / 徽章 / 图鉴计数）
--
-- 【关注点】这一屏是**数字 + 短标签 + 徽章图形**混排：
--   「プレイじかん」「もっているバッジ」「ポケモンずかん」这类中文标签
--   在 12px 下会明显变长，是最容易和徽章图形撞 UI 的一屏。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local function body(api)
    -- 2026-11-03：卡片是「标签 + 数字 + 徽章图形」混排，进入时整屏绘制，
    -- 连帧才能看出文字是否压到徽章图形上。
    api.burst("card_enter", 12, 6)
    api.shot("trainer_card")
    -- 卡片可翻面（正面/背面）
    api.tap("A", 4, 50)
    api.burst("card_back_f", 10, 6)
    api.shot("trainer_card_back")
    api.tap("A", 4, 50)
    api.burst("card_front_f", 10, 6)
    api.shot("trainer_card_front")
end

return L.make_scene(L.MENU.TRAINER, "trainer", body)
