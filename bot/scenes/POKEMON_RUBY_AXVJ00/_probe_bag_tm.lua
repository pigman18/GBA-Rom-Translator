-- ============================================================================
-- _probe_bag_tm.lua — 背包「技能/招式学习器」口袋进门乱码
--
-- RS 口袋顺序：道具 → 精灵球 → 招式学习器 → 树果 → 重要物品
-- 用户报：一进技能页就乱码（No. 与中文名叠、残墨）。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("overworld")

L.open_menu_at(api, L.MENU.BAG)
api.tap("A", 4, 60)
api.burst("bag_items_f", 12, 6)
api.shot("bag_items")

-- → 精灵球
api.tap("RIGHT", 4, 40)
api.burst("bag_balls_f", 10, 6)
api.shot("bag_balls")

-- → 招式学习器（技能页）
api.tap("RIGHT", 4, 40)
api.burst("bag_tm_enter_f", 14, 5)
api.shot("bag_tm")

-- 列表下移几项，看叠字/残墨是否加重
for i = 1, 5 do
    api.tap("DOWN", 4, 25)
    api.burst(string.format("bag_tm_dn%d_f", i), 6, 4)
    api.shot(string.format("bag_tm_dn%d", i))
end

api.tap("B", 4, 40)
api.shot("closed")

return api.S
