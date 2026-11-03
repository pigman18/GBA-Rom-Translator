-- ============================================================================
-- start_menu.lua — 系统开始菜单（8 项全浏览）
--
-- 【到达目标】野外 → START → 菜单 8 项，逐项下移看选中高亮重绘
--   図鑑 / ポケモン / バッグ / ポケナビ / ユウキ / レポート / せってい / とじる
--
-- 【为什么要这个场景】这是**文本最密集**的菜单之一：8 行菜单项 + 每行
--   选中态的高亮重绘。汉字/假名混排，最能暴露 12px 字体的撞 tile 与残影。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("overworld")

-- 逐项浏览（含回顶反向检查）
-- 2026-11-03：菜单首次打开 + 每项选中高亮都连帧。
-- 8 项菜单是文本最密集的一屏之一，高亮重绘的残影只在过渡帧里看得到。
L.open_menu_at(api, 1)
api.burst("start_menu_open_f", 10, 6)
api.shot("start_menu_top")
for i = 1, L.MENU_COUNT - 1 do
    api.tap("DOWN", 4, 25)
    api.burst(string.format("start_menu_%d_f", i + 1), 5, 5)
    api.shot(string.format("start_menu_%d", i + 1))
end

-- 回顶清一次选中态残留
for _ = 1, L.MENU_COUNT do api.tap("UP", 4, 12) end
api.shot("start_menu_back_top")

L.exit_to_overworld(api, 4, "start_menu_closed")

return api.S
