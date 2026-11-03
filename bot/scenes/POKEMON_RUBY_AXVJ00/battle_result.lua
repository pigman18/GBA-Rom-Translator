-- ============================================================================
-- battle_result.lua — 战斗结算与胜负横幅（覆盖文档 §7.2 B 类）
--
-- 【要覆盖什么】
--   B 类：13 个调用点，解码出的文本是
--     `\CC0200かち`（胜利）/ `\CC0200まけ`（失败）/ `\CC0200ひきわけ`（平局）
--   —— 这是战斗结束时的**结果横幅**。
--
-- 【怎么触发】
--   确定性遇敌 → 一直按 A 打完（我方 36 级 vs 野生低等级，基本必胜）
--   → 结算画面会显示「かち」横幅 + 经验/升级/学招提示。
--   经验结算里还能采到 C 类的「学新招确认（はい/いいえ）」。
--
-- ⚠ 与 battle_full 的区别：battle_full 到「队伍子菜单」就收尾（逃跑），
--   本场景**打到结束**，专门采结算与横幅。
-- ⚠ 战斗中会消耗 HP，但每个场景重新读档，不影响其他场景。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ADDR_RNG = 0x03004818

L.preamble(api)
api.shot("br_overworld")

-- ① 确定性遇敌
api.poke{ { addr = ADDR_RNG, width = 4, value = 0x0000AAAA, note = "钉 RNG" } }
api.hunt{ dir = "DOWN", x = 68, y = 7, steps = 40, timeout = 120 }
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 900, tag = "battle" }
api.burst("br_transition", 14, 8)
api.shot("br_battle_in")

-- ② 推过开场，进主菜单
for i = 1, 3 do
    api.tap("A", 5, 45)
    api.burst(string.format("br_intro%d", i), 6, 8)
end
api.shot("br_menu")

-- ③ 直接「たたかう」+ 第一招，反复打
--    每轮：A（选招式菜单）→ A（第一招）→ 等动画 → 连按 A 推进
for round = 1, 12 do
    api.tap("A", 5, 50)                 -- たたかう
    api.shot(string.format("br_move_menu%d", round))
    api.burst(string.format("br_move%d_f", round), 8, 6)
    api.tap("A", 5, 60)                 -- 第一招
    api.burst(string.format("br_atk%d", round), 20, 8)
    -- 推进战斗文本（伤害/效果）
    for j = 1, 6 do
        api.tap("A", 5, 50)
        api.burst(string.format("br_r%d_%d", round, j), 4, 8)
    end
    api.shot(string.format("br_round%d_end", round))
end

-- ④ 结算：胜负横幅 + 经验 + 升级 + 学招
api.burst("br_settle_f", 30, 8)
api.shot("br_settle")

-- 逐帧推进结算，把横幅/经验/学招确认都采到
for i = 1, 20 do
    api.tap("A", 5, 55)
    api.burst(string.format("br_fin%02d", i), 5, 8)
    api.shot(string.format("br_fin%02d", i))
end

api.shot("br_end")
return api.S
