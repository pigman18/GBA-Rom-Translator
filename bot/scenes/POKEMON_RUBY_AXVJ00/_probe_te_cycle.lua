-- ============================================================================
-- _probe_te_cycle.lua — 训练家之眼「来回」残墨（扩宽版）
--
-- 覆盖用户路径：列表滚屏 / 翻页 / 多进多出详情 / 换选中项 / 退回后再滚。
-- 关键帧带 dump（vram/ram），便于对照左栏统计与右栏红数字残墨。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local PAGE_ROWS = 8

local function dump_shot(name)
    -- shot 默认带五件套；关键定型帧用唯一名
    api.shot(name)
end

L.preamble(api)
dump_shot("overworld")

L.open_menu_at(api, L.MENU.NAV)
api.tap("A", 4, 90)
api.burst("nav_boot_f", 16, 8)
api.wait(40)
for _ = 1, 2 do api.tap("DOWN", 4, 20) end
api.tap("A", 4, 90)
api.burst("list_enter_f", 12, 8)
dump_shot("list_enter")

-- ── 阶段 A：纯列表滚动（不进详情），看左栏是否被「带清」──────────────
for i = 1, PAGE_ROWS - 1 do
    api.tap("DOWN", 4, 18)
end
api.burst("A_page1_last_f", 8, 4)
dump_shot("A_page1_last")

api.tap("DOWN", 4, 28)
api.burst("A_page2_f", 10, 5)
dump_shot("A_page2")

for i = 1, 4 do
    api.tap("DOWN", 4, 18)
end
dump_shot("A_page2_mid")

for i = 1, 6 do
    api.tap("UP", 4, 18)
end
dump_shot("A_scroll_up")

-- ── 阶段 B：同一项 详情↔列表 ×3 ─────────────────────────────────────
for round = 1, 3 do
    api.tap("A", 4, 90)
    api.burst(string.format("B%d_detail_f", round), 14, 6)
    dump_shot(string.format("B%d_detail", round))
    api.wait(15)
    api.tap("B", 4, 50)
    api.burst(string.format("B%d_back_f", round), 12, 5)
    dump_shot(string.format("B%d_back", round))
end

-- ── 阶段 C：换项再进详情（用户「来回」）──────────────────────────────
api.tap("DOWN", 4, 22)
dump_shot("C_sel_dn")
api.tap("A", 4, 90)
api.burst("C_detail_f", 14, 6)
dump_shot("C_detail")
api.tap("B", 4, 50)
api.burst("C_back_f", 12, 5)
dump_shot("C_back")

api.tap("UP", 4, 22)
dump_shot("C_sel_up")
api.tap("A", 4, 90)
api.burst("C_detail2_f", 14, 6)
dump_shot("C_detail2")
api.tap("B", 4, 50)
api.burst("C_back2_f", 12, 5)
dump_shot("C_back2")

-- ── 阶段 D：翻页边界 + 详情 + 再滚（page_edge 合入）──────────────────
for i = 1, PAGE_ROWS do
    api.tap("DOWN", 4, 18)
end
api.burst("D_near_edge_f", 8, 4)
dump_shot("D_near_edge")

api.tap("DOWN", 4, 30)
api.burst("D_page_edge_f", 10, 5)
dump_shot("D_page_edge")

api.tap("A", 4, 90)
api.burst("D_detail_f", 14, 6)
dump_shot("D_detail")
api.tap("B", 4, 50)
api.burst("D_back_f", 12, 5)
dump_shot("D_back")

api.tap("DOWN", 4, 22)
dump_shot("D_after_dn")
api.tap("UP", 4, 22)
dump_shot("D_after_up")
api.tap("DOWN", 4, 22)
api.tap("DOWN", 4, 22)
dump_shot("D_after_dn2")

-- ── 阶段 E：快速连进连出 4 次（加压残墨）────────────────────────────
for round = 1, 4 do
    api.tap("A", 4, 70)
    api.wait(25)
    dump_shot(string.format("E%d_detail", round))
    api.tap("B", 4, 40)
    api.wait(20)
    dump_shot(string.format("E%d_back", round))
    if round % 2 == 1 then
        api.tap("DOWN", 4, 18)
    else
        api.tap("UP", 4, 18)
    end
end
dump_shot("E_final")

api.tap("B", 4, 40)
api.tap("B", 4, 40)
dump_shot("closed")

return api.S
