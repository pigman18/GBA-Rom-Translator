-- ============================================================================
-- _probe_whiteout2.lua — 造白屏：进战斗后把 HP 清零，看是否触发白屏传送
--
-- 【路子】（源码依据 pret/pokeruby overworld.c）
--   DoWhiteOut() { ... Overworld_SetWarpDestToLastHealLoc(); WarpIntoMap(); }
--   ⇒ 白屏是**唯一能可靠触发 WarpIntoMap 的常规路径**，
--     而它用的是 lastHealLocation（SB1+0x1C，已实测能写且能保住）。
--
-- 【怎么造白屏】
--   全员 HP 归零 → 战斗判负 → 白屏 → 落到 lastHealLocation。
--   战斗中每只的当前 HP 在 gBattleMons 结构里（0x02024A80，KEEP-US）。
--   但结构偏移未知，所以本探针改成**更直接**的办法：
--     把场上宝可梦的 HP 写成 1，然后让它挨一下 —— 不，还是要偏移。
--
--   ★ 改用「先野外遇敌 → 战斗里用 poke 扫 HP」：
--     战斗开始时 gBattleMons[0].hp 附近扫，找等于当前 HP 的 u16。
--     本轮先只把**战斗界面采下来**，HP 偏移留到下一轮用截图+内存对照确定。
--
-- ⚠ 本探针的目的是「拿到一场战斗的 ram.bin 供扫 HP 用」，
--   同时验证 lastHealLocation 在战斗后是否仍在。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ADDR_RNG = 0x03004818

L.preamble(api)
api.shot("wo2_shop")

-- ① 先把 lastHealLocation 设成 Route118（目标）
api.poke{
    { sb1 = 0x1C, width = 1, value = 0x00, note = "g=0" },
    { sb1 = 0x1D, width = 1, value = 0x21, note = "n=33" },
    { sb1 = 0x1E, width = 1, value = 0xFF, note = "warpId=-1" },
    { sb1 = 0x20, width = 1, value = 68, note = "x=68" },
    { sb1 = 0x21, width = 1, value = 7, note = "y=7" },
}
api.shot("wo2_target")

-- ② 出门到城市
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("wo2_outside")

-- ③ 回 Route118 才有草丛；这里直接在城市找水/草丛不现实，
--    先用固定 RNG + hunt 在城市周围试遇敌（Mauville 附近也有遭遇点）
api.poke{ { addr = ADDR_RNG, width = 4, value = 0x0000AAAA, note = "钉 RNG" } }
api.hunt{ dir = "DOWN", x = 23, y = 17, steps = 30, timeout = 120 }
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 600, tag = "battle" }
api.shot("wo2_battle")
api.burst("wo2_battle_f", 10, 8)

-- ④ 战斗里，用 SHOT 记录 gBattleMons 就能离线扫 HP
api.shot("wo2_battle_state")

return api.S
