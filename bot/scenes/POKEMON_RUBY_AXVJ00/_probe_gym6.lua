-- ============================================================================
-- _probe_gym6.lua — 金手指导航：出门后直接 poke 坐标扫到道馆门口
--
-- 【为什么这么写】
--   之前一直在用走位绕花坛，效率极低。其实**同图内改坐标是有效的**：
--   实测 poke SaveBlock1+0x00/0x02 写 pos，游戏立刻把角色挪过去
--   （(68,7) → (60,7) 当场生效）。
--   只有**跨图**改 mapGroup/mapNum 无效（地图要读档流程加载）——
--   而出门这一步向下走就自动完成了，所以：
--     走位只负责「出门」，剩下的全部用 poke 定位。
--
-- 【坐标扫描】
--   截图 005.png 已看清：主角 (15,17)，**左侧粉色大楼带拱形门 = 道馆**。
--   本探针在 x=8..15 / y=12..17 的小网格上逐点瞬移 + 截图，
--   从截图里挑出正对门的那一格，下一轮直接 poke 过去按 A。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("g6_shop")

-- ① 出门（只有这一步需要走位）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("g6_outside")

-- ② 坐标扫描：逐点瞬移到网格，截图看走到哪
--    ⚠ poke 用 sb1 偏移（跟着存档走，地址由 prove 定位，比绝对地址稳）
local pts = {}
for y = 12, 17 do
    for x = 8, 15 do
        pts[#pts + 1] = { x = x, y = y }
    end
end

for i, p in ipairs(pts) do
    api.poke{
        { sb1 = 0x00, width = 2, value = p.x, note = "pos.x" },
        { sb1 = 0x02, width = 2, value = p.y, note = "pos.y" },
    }
    api.wait(8)
    -- 只挑一部分截图，避免帧数爆炸（每 2 个点拍 1 张）
    if i % 2 == 1 then
        api.shot(string.format("g6_x%02d_y%02d", p.x, p.y))
    end
end

-- ③ 回到一个已知可站立的位置备查
api.poke{
    { sb1 = 0x00, width = 2, value = 15, note = "回到起点 x" },
    { sb1 = 0x02, width = 2, value = 17, note = "回到起点 y" },
}
api.wait(10)
api.shot("g6_back")

return api.S
