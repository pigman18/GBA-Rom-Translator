-- ============================================================================
-- bag.lua — 背包（BUG 1 / BUG 2 主现场）
--
-- 【到达目标】野外 → START → 第 3 项「バッグ」→ A → 背包界面
--
-- 【本场景覆盖的四个撞点】
--   ① 列表 + 底部说明框（长道具名 vs 右侧面板边框）
--   ② **对第 1 项「学习装置」按 A → 再 A 选「使用」→ 说明对话框**
--      ← 用户实测最严重的一帧：三行中文横着压到背包列表和「どうぐ」标签上
--   ③ 对话框**翻页**（`\p` 分页）：第 2 页只有「用！」两个字，第 1 页的
--      字模 tile 一个没清 —— 整屏残影（BUG 2 的标准现场）
--   ④ 道具子菜单逐项移动时底部提示的重绘 / 口袋切换 / 列表滚到底
--
-- 【为什么「使用」安全】学习装置是装备类道具，按「使用」只播一段说明
--   （`おとうさんの ことば‥‥ / ユウキ！こういうものには つかいどきが あるんだ！`，
--   译文 `爸爸的话…… / ～！这种东西该用的时候就要\p用！`），不消耗、不改存档。
--   实测退回列表后仍是「学习装置 × 2」，因此两侧仍是干净对照。
--   仍**不选**「携带 / 丢弃」（那两项会改宝可梦持物）。
--
-- 【时序】不必数帧：bot.lua 每步之后等画面稳定（settle），打印动画会被等完，
--   截图拿到的都是「这一页打完、停在 ▼」的定型帧 —— 正是要验收的那一帧。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local function body(api)
    api.shot("bag_open")

    -- ── ① 第 1 项「学习装置」按 A：道具子菜单（使用/携带/丢弃/取消）──────────
    --    此时子菜单框 + 底部「想做什么？」+ 右侧列表三块同屏
    api.tap("A", 4, 45)
    api.shot("bag_item_menu")

    -- ── ② 选「使用」：说明对话框第 1 页（撞 UI 最严重的一帧）────────────────
    api.tap("A", 4, 45)
    api.shot("bag_use_p1")

    -- ── ③ 翻到第 2 页（`\p`）：只有「用！」，第 1 页的字模应该被清掉 ─────────
    api.tap("A", 4, 45)
    api.shot("bag_use_p2")

    -- ── ④ 关掉对话框：回到列表，检查框体区域有没有擦花 ───────────────────────
    api.tap("A", 4, 45)
    api.shot("bag_use_closed")

    -- ── ⑤ 再开子菜单，逐项移动：底部提示每换一项整句重画（残留高发点）────────
    api.tap("A", 4, 45)
    api.shot("bag_item_menu_re")
    for i = 2, 4 do
        api.tap("DOWN", 4, 30)
        api.shot(string.format("bag_item_menu%d", i))
    end
    for _ = 1, 3 do api.tap("UP", 4, 12) end
    api.shot("bag_item_menu_top")

    -- ── ⑥ 取消，回到列表（弹窗消失后要检查列表有没有被擦花）─────────────────
    api.tap("B", 4, 40)
    api.shot("bag_item_menu_closed")

    -- ── ⑦ 逐个口袋翻页（RIGHT 切换口袋，整屏重绘）───────────────────────────
    for i = 2, 4 do
        api.tap("RIGHT", 4, 40)
        api.shot(string.format("bag_pocket%d", i))
    end
    api.tap("LEFT", 4, 40)
    api.tap("LEFT", 4, 40)
    api.tap("LEFT", 4, 40)
    api.shot("bag_pocket_back")

    -- ── ⑧ 列表逐项下移 + 滚到底（越过一屏 => 触发列表滚动重绘）───────────────
    for i = 1, 4 do
        api.tap("DOWN", 4, 25)
        api.shot(string.format("bag_item%d", i + 1))
    end
    for _ = 5, 9 do
        api.tap("DOWN", 4, 25)
    end
    api.shot("bag_scroll_bottom")
end

return L.make_scene(L.MENU.BAG, "bag", body)
