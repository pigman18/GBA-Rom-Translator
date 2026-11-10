-- ============================================================================
-- bag.lua — 背包（BUG 1 / BUG 2 主现场）
--
-- 【到达目标】野外 → START → 第 3 项「バッグ」→ A → 背包界面
--
-- 【本场景覆盖的撞点】
--   ⓪ 列表光标下移：底边 ×1×2 数量残影（用户 2026-11-06）
--   ① 列表 + 底部说明框
--   ② 「学习装置」→「使用」说明对话框第 1 页
--   ③ `\p` 翻页第 2 页（应收「用！」；用户报「用栏」疑 F900）
--   ④ 子菜单 / 口袋切换 / 列表滚到底
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local function body(api)
    api.burst("bag_enter", 10, 6)
    api.shot("bag_open")

    -- ── ⓪ 列表内光标下移：盯底边 ×N 残影 / 乱码条 ───────────────────────────
    for i = 1, 6 do
        api.tap("DOWN", 4, 28)
        api.burst(string.format("bag_cur_dn%d_f", i), 8, 4)
        api.shot(string.format("bag_cur_dn%d", i))
    end
    for _ = 1, 6 do api.tap("UP", 4, 12) end
    api.burst("bag_cur_top_f", 6, 4)
    api.shot("bag_cur_top")

    -- ── ① 第 1 项「学习装置」→ 子菜单 ───────────────────────────────────────
    api.tap("A", 4, 45)
    api.burst("bag_item_menu_in", 8, 6)
    api.shot("bag_item_menu")

    -- ── ② 「使用」第 1 页 ───────────────────────────────────────────────────
    api.tap("A", 4, 45)
    api.burst("bag_use_p1_f", 12, 6)
    api.shot("bag_use_p1")

    -- ── ③ `\p` 第 2 页（「用！」/ 用户「用栏」）──────────────────────────────
    api.tap("A", 4, 45)
    api.burst("bag_use_p2_f", 16, 5)
    api.shot("bag_use_p2")

    -- ── ④ 关对话框 ─────────────────────────────────────────────────────────
    api.tap("A", 4, 45)
    api.burst("bag_use_closed_f", 10, 6)
    api.shot("bag_use_closed")

    -- ── ⑤ 子菜单逐项 ───────────────────────────────────────────────────────
    api.tap("A", 4, 45)
    api.shot("bag_item_menu_re")
    for i = 2, 4 do
        api.tap("DOWN", 4, 30)
        api.burst(string.format("bag_item_menu%d_f", i), 6, 5)
        api.shot(string.format("bag_item_menu%d", i))
    end
    for _ = 1, 3 do api.tap("UP", 4, 12) end
    api.shot("bag_item_menu_top")

    -- ── ⑥ 取消回列表 ───────────────────────────────────────────────────────
    api.tap("B", 4, 40)
    api.shot("bag_item_menu_closed")

    -- ── ⑦ 口袋切换 ─────────────────────────────────────────────────────────
    for i = 2, 4 do
        api.tap("RIGHT", 4, 40)
        api.burst(string.format("bag_pocket%d_f", i), 10, 6)
        api.shot(string.format("bag_pocket%d", i))
    end
    api.tap("LEFT", 4, 40)
    api.tap("LEFT", 4, 40)
    api.tap("LEFT", 4, 40)
    api.shot("bag_pocket_back")

    -- ── ⑧ 列表下移 + 滚到真正末尾（无红▼；盯上一行数量×残留是否消失）────────
    for i = 1, 6 do
        api.tap("DOWN", 4, 25)
        api.burst(string.format("bag_item%d_f", i + 1), 6, 4)
        api.shot(string.format("bag_item%d", i + 1))
    end
    -- 口袋道具多，多按几次直到末尾；末帧应对齐「无残留×」
    for n = 7, 28 do
        api.tap("DOWN", 4, 20)
        if n % 3 == 0 then
            api.burst(string.format("bag_scroll_f%d", n), 4, 4)
        end
    end
    api.burst("bag_scroll_end_f", 8, 4)
    api.shot("bag_scroll_end")
end

return L.make_scene(L.MENU.BAG, "bag", body)
