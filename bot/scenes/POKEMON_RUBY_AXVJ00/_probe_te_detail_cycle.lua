-- ============================================================================
-- _probe_te_detail_cycle.lua — 训练家之眼残墨复现
--
-- 用户路径：列表 → 详情 → B 回列表 → 下一项 → 详情（可再 B）
-- 红残墨来自详情标签（持有的宝可梦 / 作战 / 自我介绍）退回后未清净。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("overworld")

-- 进 ポケナビ → トレーナーアイ
L.open_menu_at(api, L.MENU.NAV)
api.tap("A", 4, 90)
api.burst("nav_boot_f", 16, 8)
api.wait(40)
for _ = 1, 2 do api.tap("DOWN", 4, 20) end
api.tap("A", 4, 90)
api.burst("list_enter_f", 12, 8)
api.shot("list_top")

-- ① 第一项详情
api.tap("A", 4, 90)
api.burst("detail1_f", 14, 8)
api.shot("detail1")
api.wait(20)

-- ② B 回列表
api.tap("B", 4, 50)
api.burst("back1_f", 10, 6)
api.shot("list_after_detail1")

-- ③ 下一项
api.tap("DOWN", 4, 25)
api.burst("list_next_f", 8, 5)
api.shot("list_next")

-- ④ 第二项详情
api.tap("A", 4, 90)
api.burst("detail2_f", 14, 8)
api.shot("detail2")
api.wait(20)

-- ⑤ B 再回列表
api.tap("B", 4, 50)
api.burst("back2_f", 10, 6)
api.shot("list_after_detail2")

-- ⑥ 再下移两格
for i = 1, 2 do
    api.tap("DOWN", 4, 25)
    api.burst(string.format("list_scroll%d_f", i), 6, 5)
    api.shot(string.format("list_scroll%d", i))
end

-- ⑦ 备选：进详情后用 RIGHT 切下一位（不经列表），再 B 回列表
api.tap("A", 4, 90)
api.burst("detail3_f", 10, 6)
api.shot("detail3")
api.tap("RIGHT", 4, 40)
api.burst("detail3_right_f", 10, 6)
api.shot("detail3_right")
api.tap("B", 4, 50)
api.burst("back3_f", 10, 6)
api.shot("list_after_detail_right")

api.tap("B", 4, 40)
api.tap("B", 4, 40)
api.shot("closed")

return api.S
