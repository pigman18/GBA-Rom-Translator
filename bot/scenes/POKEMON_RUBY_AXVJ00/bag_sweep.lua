-- ============================================================================
-- bag_sweep.lua — 背包逐项翻页扫描（字库采集 + 验收基线）
--
-- 刚需来源：
--   ① 字库采集：背包页集中出现大量不同汉字（道具名、底部说明、口袋名）
--   ② 验收：中文化后此页最易出现超宽/串行，需逐项截图对照
--
-- 做法：进入背包后逐项 DOWN 下翻到底，再逐项 UP 回顶；
--       每一步 shot，由 bot.lua 产出 png + vram/pal/io/ram/oam。
-- 时序：不数帧，bot.lua 每步等 settle，拿到定型帧。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local function body(api)
    api.shot("bag_sweep_00_top")

    -- 逐项下翻（覆盖整列道具名 + 底部说明重绘）
    for i = 1, 14 do
        api.tap("DOWN", 4, 40)
        api.shot(string.format("bag_sweep_%02d_down", i))
    end

    -- 逐项上翻回顶
    for i = 1, 14 do
        api.tap("UP", 4, 30)
        api.shot(string.format("bag_sweep_%02d_up", i))
    end

    api.shot("bag_sweep_99_back_top")
end

return L.make_scene(L.MENU.BAG, "bag_sweep", body)
