-- ============================================================================
-- pokemon_menu.lua — 宝可梦菜单 / 队伍列表  ★ fontNum 关注场景
--
-- 【为什么单独做这个场景】
--   用户口径：「fontNum=4 场景使用 Small 字体，渲染 8×8px，主要用在
--   **队伍名称显示**、**战斗宝可梦名显示**」。
--   队伍列表就是 fontNum=4（Small）的主要落点，必须单独采集对照。
--
-- 【到达目标】野外 → START → 第 2 项「ポケモン」→ A
--   → 队伍列表（6 只，含名字/等级/HP 条）→ A 看单只摘要 → 左右翻页
--
-- 【路线】make_scene 保证带 prove；内部逐只翻摘要页
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local function body(api)
    -- 队伍列表（★ Small 字体：宝可梦名）
    -- 2026-11-03：入口连帧，抓「从菜单淡入到列表定型」的完整过程。
    -- 单帧只能证明「定型帧长这样」，证明不了中途有没有错位/残影。
    api.burst("party_enter", 10, 6)
    api.shot("party_list")

    -- 光标逐只下移（每只的名字都要画一遍 → 逐个抓重绘）
    -- 每次移动都连抓 4 帧：选中高亮的过渡帧也是要验收的（残影常出在这里）
    for i = 1, 5 do
        api.tap("DOWN", 4, 30)
        api.burst(string.format("party_sel%d_f", i + 1), 4, 5)
        api.shot(string.format("party_sel%d", i + 1))
    end
    for _ = 1, 5 do api.tap("UP", 4, 15) end
    api.shot("party_back_top")

    -- A → DoWhat 菜单（查看能力 / 排序 / 携带物品 / 取消）
    api.tap("A", 4, 60)
    api.burst("party_action", 8, 6)
    api.shot("party_action_menu")

    -- ★ 选第 1 项「查看能力」进摘要（能力）页，左右翻页
    --   为什么必须覆盖：B08 修复把 CHS 字模带放在 BG0 charBase1 的
    --   0x016E..0x01BF，紧邻能力页合法的字模址 0x168 区，必须验证互不踩踏。
    api.tap("A", 4, 130)
    api.burst("summary_enter", 10, 8)
    api.shot("summary_ability")
    for i = 2, 4 do
        api.tap("RIGHT", 4, 45)
        -- 翻页是整屏重画：连抓 10 帧看旧页字模有没有被带过来
        api.burst(string.format("summary_tab%d_f", i), 10, 6)
        api.shot(string.format("summary_tab%d", i))
    end

    -- 退回：摘要 → DoWhat → 列表（关队伍菜单由 make_scene 的统一收尾负责）
    for _ = 1, 2 do api.tap("B", 4, 45) end
    api.shot("party_again")
end

return L.make_scene(L.MENU.POKEMON, "pokemon", body)
