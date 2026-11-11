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
    -- 2026-11-03：入口连帧，覆盖图鉴列表首屏绘制
    api.burst("dex_enter", 12, 6)
    api.shot("dex_open")

    -- 2026-11-11：进「图鉴条目页」（A 选中列表项）——分类名「たねポケモン」那行
    -- 只在这一页画，列表页看不到；这一页的两个绘制点走的是直接读字段
    -- （不走 getter），是 12px 分类名的验收点。
    api.tap("A", 4, 30)
    api.burst("dex_entry_f", 8, 6)
    api.shot("dex_entry")
    api.tap("B", 4, 20)
    api.burst("dex_entry_back_f", 4, 5)

    -- 上下翻几屏（图鉴列表是长列表）
    -- 每项都连抓 4 帧：宝可梦名/分类名重绘时的过渡帧是溢出高发点
    for i = 1, 5 do
        api.tap("DOWN", 4, 25)
        api.burst(string.format("dex_down%d_f", i), 4, 5)
        api.shot(string.format("dex_down%d", i))
    end
    -- 左右翻页 = 整屏换页，连抓 10 帧看旧页字模有没有被带过来
    for i = 1, 2 do
        api.tap("RIGHT", 4, 40)
        api.burst(string.format("dex_page%d_f", i + 1), 10, 6)
        api.shot(string.format("dex_page%d", i + 1))
    end
    for _ = 1, 4 do api.tap("UP", 4, 12) end
    api.shot("dex_back_top")
end

return L.make_scene(L.MENU.DEX, "dex", body)
