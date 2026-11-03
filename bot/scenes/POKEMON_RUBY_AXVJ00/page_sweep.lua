-- ============================================================================
-- page_sweep.lua — 翻页扫描（字库采集 + 验收基线）
--
-- 需求来源：背包、设置两个页面的自动翻页是**刚需**：
--   ① 字库采集：这两页集中出现大量不同汉字（道具名、说明、选项名）
--   ② 验收：中文化后这两页最容易出现超宽/串行，需要逐页截图对照
--
-- 做法：
--   背包：进入后逐项 DOWN 遍历整列（吃满道具名 + 底部说明重绘）
--   设置：进入后逐项 DOWN 遍历所有选项（吃满选项名）
--   每一步都 shot，由 bot.lua 产出 png + vram/pal/io/ram/oam
--
-- 时序：不数帧，bot.lua 每步等 settle，拿到的是定型帧。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local function body(api)
    -- ── 背包：逐项下翻 ────────────────────────────────────────────────
    api.shot("bag_00_top")

    for i = 1, 12 do
        api.tap("DOWN", 4, 40)
        api.shot(string.format("bag_%02d_down", i))
    end

    -- 回到顶部
    for i = 1, 12 do
        api.tap("UP", 4, 30)
    end
    api.shot("bag_99_back_top")

    -- 退出背包
    api.tap("B", 4, 45)
    api.shot("bag_98_closed")

    -- ── 设置：逐项下翻 ────────────────────────────────────────────────
    -- 从野外 START 菜单进「设置」（第 7 项附近），用 DOWN 移动后 A 进入
    api.tap("START", 4, 60)
    for i = 1, 6 do
        api.tap("DOWN", 4, 25)
    end
    api.tap("A", 4, 60)
    api.shot("options_00_top")

    for i = 1, 8 do
        api.tap("DOWN", 4, 35)
        api.shot(string.format("options_%02d_down", i))
    end

    for i = 1, 8 do
        api.tap("UP", 4, 25)
    end
    api.shot("options_99_back_top")

    api.tap("B", 4, 45)
    api.shot("options_98_closed")
end

L.run(body)
return api.S
