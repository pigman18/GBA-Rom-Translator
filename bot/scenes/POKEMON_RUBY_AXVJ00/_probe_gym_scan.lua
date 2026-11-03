-- ============================================================================
-- _probe_gym_scan.lua — 金手指网格扫描：找出道馆门口那一格
--
-- 已确认（2026-11-03）：
--   ✅ 同图内 poke pos 立刻生效：(23,17)→(23,10)→(23,20)→(10,15) 全对
--   ✅ 出门只需走位（向下走穿门 ⇒ map 10:7 → 0:2）
--   ⇒ 所以「跳场景」的正确做法是：**走位只负责换图，图内位置全用 poke**
--
-- 截图 005.png 显示：主角 (15,17)，左侧粉色大楼带拱形门（道馆外形），
-- 上方有花坛挡路。本探针在 x=4..14 / y=10..16 上逐点瞬移并截图，
-- 从画面挑出「正对拱形门」的一格。
--
-- ⚠ 只拍一部分点（每 3 点 1 张），否则帧数与体积都太大。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("gs_shop")

-- 出门（唯一需要走位的一步）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("gs_out")

-- 网格扫描：先扫「北侧一行」和「左侧一列」，这两处最可能对着门
local pts = {}
-- 左侧一列（x=4..14, y=15）：看粉楼正面
for x = 4, 14 do pts[#pts + 1] = { x = x, y = 15 } end
-- 北侧一行（y=10..14, x=10）：看花坛上方
for y = 10, 14 do pts[#pts + 1] = { x = 10, y = y } end
-- 再补一行更北的
for x = 6, 12 do pts[#pts + 1] = { x = x, y = 12 } end

for i, p in ipairs(pts) do
    api.poke{
        { sb1 = 0x00, width = 2, value = p.x, note = "x" },
        { sb1 = 0x02, width = 2, value = p.y, note = "y" },
    }
    api.wait(6)
    api.shot(string.format("gs_%02d_x%02d_y%02d", i, p.x, p.y))
end

return api.S
