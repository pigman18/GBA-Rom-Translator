-- ============================================================================
-- contest_hall.lua — 华丽大赛会场（FallarborTown_ContestHall）
--
-- 【地图 ID 推导】（scripts/map_ids.py 有完整证据）
--   日版实测校准了三个组与美版完全一致：
--     group 0  : Route118=33, Route119=34, MauvilleCity=2
--     group 2  : OldaleTown_PokemonCenter_1F=2
--     group 10 : MauvilleCity_Mart=7（美版是第 8 项 ✓）
--   美版 group 5 = IndoorFallarbor：
--     [Mart, ContestLobby, ContestHall, PC_1F, PC_2F, House1, House2]
--   ⇒ ContestLobby = 5:1，ContestHall = 5:2
--
-- 【采什么】
--   华丽大赛是文档 §7.2 H 类窗口（`ContestAICmd_unk_5E`、`WallyBufferExec`），
--   以及 §7.2 的 33-34 项（选手训练家名 / 招式说明）。
--   会场里有评委、参赛者、以及「要参加哪一项比赛」的菜单文本。
--
-- 【策略】先进 Lobby（5:1）看报名菜单，再进 Hall（5:2）看会场。
--   ⚠ 一个场景只做一次 warp（连续第二次会 TIMEOUT），
--     所以本场景只用一次 warp 进 Lobby；Hall 靠走位进入。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("ct_start")

-- 出门到城市
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("ct_outside")

-- 跳进华丽大赛 Lobby（5:1）
--   ⚠ 落点 (10,10) 实测踩在地图外（黑屏，只有上边缘可见）。
--     从那张图看，可走区域在地图**上方**，所以把 y 调小、x 往中间靠。
--     先试 (8,5)；若仍偏，看 ct_lobby 截图再调。
api.warp{ map = "5:1", x = 8, y = 5, mon = 1 }
api.wait(60)
api.shot("ct_lobby")
api.burst("ct_lobby_f", 14, 8)

-- Lobby 里往四周走，找报名台/柜台（通常会触发菜单）
api.roam{ seq = { "UP", "UP", "LEFT", "RIGHT" }, steps = 5 }
api.shot("ct_lobby_walk")

-- 试对话：柜台报名会出菜单（要选参赛宝可梦/类别）
api.tap("UP", 5, 25)
api.tap("A", 6, 60)
api.burst("ct_register", 16, 8)
api.shot("ct_register_shot")

-- 若出现菜单，逐项看（哪一项 / 等级）
for i = 1, 4 do
    api.tap("DOWN", 4, 30)
    api.burst(string.format("ct_menu%d", i), 6, 6)
    api.shot(string.format("ct_menu%d_shot", i))
end
api.tap("B", 4, 40)
api.shot("ct_back")

-- 再试一次 A，确认报名流程
api.tap("A", 6, 60)
api.burst("ct_reg2", 12, 8)
api.shot("ct_reg2_shot")
api.tap("B", 4, 50)
api.shot("ct_end")

return api.S
