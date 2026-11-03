-- ============================================================================
-- options.lua — 设置界面（せってい / 改变设置，对照 验收效果/2.PNG）
--
-- 【到达目标】野外 → START → 下移到第 7 项「せってい」→ A 进入
--   界面内容：对话速度 / 战斗动画 / 对战规则 / 声音 / 按键模式 / 窗口 / 关闭
--
-- 【路线】preamble（读档 + prove）→ 打开系统菜单第 7 项 → A
--         → 逐行下移并左右改值（每次改值触发该行重绘）
--
-- ⚠ 开场不要连按 A（会跟身边 NPC 说话，对话框吞掉后续按键）。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

-- 1) 前置：开机 → 读档 → prove（存档必须真被加载）
L.preamble(api)
api.shot("overworld")

-- 2) 打开系统菜单第 7 项「せってい」并进入
L.open_menu_at(api, L.MENU.OPTION)
api.shot("opt_on_item")
api.tap("A", 4, 60)
-- 2026-11-03：进入过渡 + 首屏连帧
api.burst("opt_enter_f", 12, 6)
api.shot("opt_enter")
api.wait(40)
api.shot("opt_open")                 -- ★ 对照 验收效果/2.PNG

-- 3) 逐行下移 + 左右改值（每次改值都会重绘该行 → 抓重绘态）
--    改值是**单行重绘**，最容易只擦掉自己写过的那半边 ⇒ 必须连帧
for i = 1, 5 do
    api.tap("RIGHT", 4, 25)
    api.burst(string.format("opt_row%d_right_f", i), 6, 5)
    api.shot(string.format("opt_row%d_right", i))
    api.tap("DOWN", 4, 25)
    api.burst(string.format("opt_row%d_f", i + 1), 6, 5)
    api.shot(string.format("opt_row%d", i + 1))
end

-- 4) 回顶再逐行左改（验证反向重绘）
for _ = 1, 5 do api.tap("UP", 4, 12) end
api.wait(30)
api.shot("opt_back_top")
for i = 1, 3 do
    api.tap("LEFT", 4, 25)
    api.shot(string.format("opt_left%d", i))
end

-- 5) 返回野外
L.exit_to_overworld(api, 4, "opt_closed")

return api.S
