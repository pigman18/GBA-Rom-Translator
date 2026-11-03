-- ============================================================================
-- _probe_city.lua — 从商店走出到 Mauville City，摸清城市布局
--
-- 背景（2026-11-03 实测两次）：
--   ① 换地图靠改 .sav 已证伪（地图是读档流程加载的，不是 location 驱动）
--   ② 但**走位跨图是可行的** —— 从商店 (3,3) 走动后坐标变成 (23,16)，
--      截图是户外城镇（房屋/树/水面）。说明室内外连通，能走到道馆。
--
-- 本探针目的：把「商店 → 城市 → 找道馆」这条路线走出来，
--   日志现在打 `map=g:n`，可直接判断有没有换图。
--
-- ⚠ 起点必须是 (3,3)：商店存档实测落点。之前误用 Route118 的 (68,7)
--   当目标，walk 全判 BLOCKED（目标格根本不在当前图里）。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local X, Y = 3, 3      -- 商店内实际落点（prove 实证）

L.preamble(api)
api.shot("city_start")

-- ① 向下走出商店（每格都是真实递增目标）
for i = 1, 8 do
    api.walk("DOWN", X, Y + i, 120, true, 16, "y")
end
api.shot("city_down8")

-- ② 继续向下（如果已出门，这里会走到街道上）
for i = 9, 18 do
    api.walk("DOWN", X, Y + i, 120, true, 16, "y")
end
api.shot("city_down18")

-- ③ 向上走出商店（另一边门）
for i = 1, 18 do
    api.walk("UP", X, Y + 18 - i, 120, true, 16, "y")
end
api.shot("city_up_end")

-- ④ 横向扫：向右 12 格，看街道延伸到哪
for i = 1, 12 do
    api.walk("RIGHT", X + i, Y, 120, true, 16, "x")
end
api.shot("city_right12")

-- ⑤ 向左 12 格
for i = 1, 24 do
    api.walk("LEFT", X + 12 - i, Y, 120, true, 16, "x")
end
api.burst("city_left_burst", 10, 10)

return api.S
