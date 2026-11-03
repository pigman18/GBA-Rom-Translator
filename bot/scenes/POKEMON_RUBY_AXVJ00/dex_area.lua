-- ============================================================================
-- dex_area.lua — 图鉴：地区分布图 + 详细页（覆盖文档 §7.2 G 类）
--
-- 【要覆盖什么】
--   G 类第 1 项：`0x0810DAF6` = 图鉴地区分布画面
--   （`Task_PokedexAreaScreen_1`，显示某只宝可梦在丰缘地区的分布）
--
--   另外 G 类还有「通信进化」（`CB2_TradeEvolutionSceneLoadGraphics` /
--   `Task_TradeEvolutionScene`），那需要**两台机器联机交换**，
--   单机 bot 无法触发 —— 这属真实限制，已记入 COVERAGE。
--
-- 【怎么到达】
--   系统菜单第 1 项「ずかん」→ 图鉴列表 → 选一只 → 详细页
--   → 左右翻页到「分布（AREA）」页
--   （Ruby 图鉴详细页顺序：数据 / 分布 两页，用 LEFT/RIGHT 切）
--
-- 【为什么单独做一个场景】
--   现有 `dex` 场景只到列表翻页，没进详细页，所以 G 类窗口没采到。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("da_overworld")

-- ① 开系统菜单 → 第 1 项 ずかん
--    ⚠ 一定要用 `L.open_menu_at()`，不要自己手写 START + UP：
--      手写版实测两次都进错地方（一次进设置、一次直接跟 NPC 说话变成
--      「训练家卡片」，因为 START 没被游戏接受、后续 UP/A 变成了走路+对话）。
--      open_menu_at 是 start_menu 场景验证过的，内部会先 START 再 UP 归顶。
L.open_menu_at(api, 1)          -- 1 = ずかん
api.burst("da_menu_top_f", 8, 6)
api.shot("da_menu_top")

api.tap("A", 4, 100)
api.burst("da_dex_enter", 16, 8)
api.shot("da_dex_list")

-- ② 列表里选中**已捕获**的宝可梦（关键！）
--    ⚠ 实测教训：先按 DOWN 把光标移到 No.004，那只是「遇见过、未捕获」，
--      按 A 打不开详细页（画面仍是列表，见 045.png）。
--      妙蛙花 No.003 是已捕获的（左侧「抓到 88」）。
--    做法：用 UP 回到 No.003（第一只会是可捕获的），再按 A。
for _ = 1, 3 do api.tap("UP", 4, 20) end
api.shot("da_sel_top")
api.burst("da_sel_top_f", 8, 6)

api.tap("A", 4, 100)
api.burst("da_detail_enter", 20, 8)
api.shot("da_detail")

-- ③ 详细页左右翻：Ruby 的图鉴详细页有「数据 / 分布」
local tabs = { "RIGHT", "RIGHT", "LEFT", "LEFT" }
for i, d in ipairs(tabs) do
    api.tap(d, 4, 40)
    api.burst(string.format("da_tab%d_f", i), 12, 6)
    api.shot(string.format("da_tab%d", i))
end

-- ④ 分布页上再按 A（可能进入全屏地区图 Task_PokedexAreaScreen_1）
api.tap("A", 4, 60)
api.burst("da_area_enter", 20, 8)
api.shot("da_area")

-- 地区图上按方向键移动光标，触发地图重绘
local dirs = { "RIGHT", "RIGHT", "DOWN", "LEFT", "UP" }
for i, d in ipairs(dirs) do
    api.tap(d, 4, 30)
    api.burst(string.format("da_area_%d_f", i), 8, 6)
    api.shot(string.format("da_area_%d", i))
end

-- ⑤ 退出：B 回详细页 → B 回列表 → B 回野外
for _ = 1, 4 do api.tap("B", 4, 50) end
api.burst("da_exit", 8, 8)
api.shot("da_end")
return api.S
