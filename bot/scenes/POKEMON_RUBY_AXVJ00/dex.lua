-- ============================================================================
-- dex.lua — 宝可梦图鉴
--
-- 【到达目标】野外 → START → 第 1 项「ずかん」→ A
--   → 图鉴列表（编号 / 名字 / 捕获状态）→ 上下翻页
--
-- 【关注点】图鉴是最长文本的场景之一：宝可梦名 + 分类名（「たねポケモン」
--   这类）在 12px 下最容易溢出/换行错位，历史踩坑记录里就有一条。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local function body(api)
    api.shot("dex_open")

    -- 上下翻几屏（图鉴列表是长列表）
    for i = 1, 5 do
        api.tap("DOWN", 4, 25)
        api.shot(string.format("dex_down%d", i))
    end
    for i = 1, 2 do
        api.tap("RIGHT", 4, 40)
        api.shot(string.format("dex_page%d", i + 1))
    end
    for _ = 1, 4 do api.tap("UP", 4, 12) end
    api.shot("dex_back_top")
end

return L.make_scene(L.MENU.DEX, "dex", body)
