-- ============================================================================
-- _probe_te_page_edge.lua — 训练家之眼翻页边界残墨
--
-- 用户稳定路径：
--   1) 滚到第一页最后一项（可见约 8 行）
--   2) 再 DOWN 一次翻到下一页首项（用户例：少爷光吾 → 怪兽爱好者敏夫）
--   3) A 进详情 → B 返回 → 红残墨
-- 本 save 注册名单可能不同，但「首页末 → 再翻一页 → 详情 → 回」几何相同。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

-- 列表可见行数（与用户截图一致：8 行）
local PAGE_ROWS = 8

L.preamble(api)
api.shot("overworld")

L.open_menu_at(api, L.MENU.NAV)
api.tap("A", 4, 90)
api.burst("nav_boot_f", 16, 8)
api.wait(40)
for _ = 1, 2 do api.tap("DOWN", 4, 20) end
api.tap("A", 4, 90)
api.burst("list_enter_f", 12, 8)
api.shot("list_top")

-- 滚到第一页最后一项
for i = 1, PAGE_ROWS - 1 do
    api.tap("DOWN", 4, 22)
    if i == PAGE_ROWS - 1 then
        api.burst("page1_last_f", 8, 5)
        api.shot("page1_last")
    end
end

-- 再下一页（翻页边界）
api.tap("DOWN", 4, 30)
api.burst("page2_first_f", 10, 5)
api.shot("page2_first")

-- 详情 → 返回
api.tap("A", 4, 90)
api.burst("detail_f", 14, 8)
api.shot("detail")
api.wait(20)
api.tap("B", 4, 50)
api.burst("back_f", 12, 6)
api.shot("list_after_detail")

-- 再上下晃两下看残墨是否粘住
api.tap("DOWN", 4, 25)
api.burst("after_dn_f", 6, 5)
api.shot("after_dn")
api.tap("UP", 4, 25)
api.burst("after_up_f", 6, 5)
api.shot("after_up")

api.tap("B", 4, 40)
api.tap("B", 4, 40)
api.shot("closed")

return api.S
