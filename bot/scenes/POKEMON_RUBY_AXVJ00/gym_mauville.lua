-- ============================================================================
-- gym_mauville.lua — Mauville City 道馆（10:0）
--
-- 【地图 ID 的推导依据】（scripts/map_ids.py 有完整推导）
--   日版实测点校准了三个地图组与美版**完全一致**：
--     group 0  : Route118=33, Route119=34, MauvilleCity=2
--     group 2  : OldaleTown_PokemonCenter_1F=2
--     group 10 : MauvilleCity_Mart=7
--   美版 group10 = IndoorMauville 的顺序是
--     [Gym, BikeShop, House1, GameCorner, House2, PC_1F, PC_2F, Mart]
--   Mart 实测 = 10:7 = 第 8 项 ✓ ⇒ **Gym = 10:0**
--
-- 【为什么用 warp】（2026-11-03 跑通的能力）
--   写 SaveBlock1.lastHealLocation(+0x1C) → 用传送术 → 精确落点。
--   一个场景只做一次 warp（连续第二次会 TIMEOUT，见 ACTIONS 文档）。
--
-- 【采集目标】道馆是文本最密集的室内之一：
--   门口 NPC 提示、馆内训练家对话、馆主战前对话、
--   以及道馆特有的「属性提示牌」等。
--   已知文档 §7.2 的窗口清单里，战斗/对话类窗口都能在这里采到。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("gm_start")                 -- 商店内 10:7

-- ① 出门到城市（warp 需要先能自由行动；且传送术在室内不可用）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("gm_outside")               -- 0:2

-- ② 跳进道馆
--    坐标先给 (5,8) —— 道馆门口附近的典型落点；若落点在墙里会再调
api.warp{ map = "10:0", x = 5, y = 8, mon = 1 }
api.wait(60)
api.shot("gm_inside")
api.burst("gm_enter", 12, 8)

-- ③ 走到道馆里的训练家旁边
--    ⚠ 朝向是 LEFT —— 这轮**实测定下来的**，不是猜的：
--      用 4 方向逐点试 A + 事后按 VRAM 差异排序，差异最大的那帧
--      （044.png，diff=102562 vs 其他 <98000）对应的动作就是 `gn2_a_LEFT`，
--      画面确实出现了道馆训练家的对话框。
--      （先按 UP 试 → talk 闸门直接报「没打到对话」，闸门起作用了。）
api.roam{ seq = { "DOWN", "UP", "UP" }, steps = 6 }
api.shot("gm_walk")

-- 朝左转身面向 NPC
api.tap("LEFT", 5, 30)
api.shot("gm_facing")

-- ④ 用 talk 闸门开对话（打空会当场失败，不产出假对照）
api.talk{ timeout = 300 }
api.burst("gm_dlg_open", 16, 6)
api.shot("gm_dlg1")

-- ⑤ 逐句推进（每句连帧，覆盖逐字打印与换句重绘）
for i = 1, 10 do
    api.tap("A", 5, 50)
    api.burst(string.format("gm_dlg%d_f", i + 1), 8, 6)
    api.shot(string.format("gm_dlg%d", i + 1))
end
api.shot("gm_end")

return api.S
