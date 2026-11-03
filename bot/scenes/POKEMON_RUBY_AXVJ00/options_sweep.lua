-- ============================================================================
-- options_sweep.lua — 设置页逐项翻页扫描（字库采集 + 验收基线）
--
-- 刚需来源：
--   ① 字库采集：设置页集中出现选项名（战斗规则/动画/字体样式等）
--   ② 验收：中文化后选项名易超宽，需逐项截图对照
--
-- 做法：进入设置页后逐项 DOWN 遍历，再 UP 回顶；每步 shot。
-- 时序：不数帧，bot.lua 每步等 settle。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local function body(api)
    api.shot("opt_sweep_00_top")

    -- 逐项下翻
    for i = 1, 8 do
        api.tap("DOWN", 4, 35)
        api.shot(string.format("opt_sweep_%02d_down", i))
    end

    -- 逐项上翻回顶
    for i = 1, 8 do
        api.tap("UP", 4, 25)
        api.shot(string.format("opt_sweep_%02d_up", i))
    end

    api.shot("opt_sweep_99_back_top")
end

return L.make_scene(L.MENU.OPTION, "options_sweep", body)
