-- ============================================================================
-- _probe_teleport.lua — 验证「改技能为传送术 + 改 lastHealLocation = 跳图」
--
-- 【这条路的依据，全部已实测】
--   ① 队伍加密三层已解决：
--      · XOR 往返 6/6 通过（verify_mon_crypto.py）
--      · 子结构顺序在日版与 pokeruby 有 3/5 错位，用实测归属表
--      · checkword = (四个 slot 的 u16 和 累加) & 0xFFFF，写在 +0x1C，
--        +0x1E 固定 0（6/6 命中，verify_checkword_algo.py）
--   ② 用 set_teleport_move.py 把 #1 的第 1 技能改成 100（テレポート），
--      回读校验通过（解密后读到 100）
--   ③ lastHealLocation（SB1+0x1C）**可写且能保住**
--      （实测写 Route118 0:33 x68 y7 后走出门仍是 00 21 ff 00 44 07）
--
-- 【本场景】
--   用改好的存档读档 → poke lastHealLocation = Route118(0:33)
--   → 打开队伍看 #1 技能是不是「テレポート」
--   → 使用它 → 看是否落到 Route118
--
-- ⚠ 传送术在**室内/城市**通常不允许使用（要野外的 mapType 允许）。
--   先在城市试着打开技能，若不允许我们再走到 Route119 野外。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("tp_start")                -- 商店内 map=10:7

-- ① 把回复点设成 Route118（目标）
api.poke{
    { sb1 = 0x1C, width = 1, value = 0x00, note = "lastHeal.g=0" },
    { sb1 = 0x1D, width = 1, value = 0x21, note = "lastHeal.n=33" },
    { sb1 = 0x1E, width = 1, value = 0xFF, note = "lastHeal.warpId=-1" },
    { sb1 = 0x20, width = 1, value = 68, note = "lastHeal.x=68" },
    { sb1 = 0x21, width = 1, value = 7, note = "lastHeal.y=7" },
}
api.shot("tp_target_set")

-- ② 走出商店到城市（传送术一般要野外，先出来）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("tp_outside")              -- map=0:2

-- ③ 打开系统菜单 → 宝可梦 → 第 2 只（索引 1）看技能
api.tap("START", 4, 60)
for _ = 1, 8 do api.tap("UP", 4, 6) end
api.tap("DOWN", 4, 12)              -- 到「ポケモン」
api.tap("A", 4, 80)
api.burst("tp_party", 10, 6)
api.shot("tp_party_list")

-- 第 2 只（技能被改成传送术的那只）
api.tap("DOWN", 4, 24)
api.shot("tp_sel2")
api.tap("A", 4, 70)                 -- 打开 DoWhat 菜单
api.burst("tp_dowhat", 8, 6)
api.shot("tp_dowhat_menu")

-- ④ 选「查看能力」看技能（第 1 项）
api.tap("A", 4, 100)
api.burst("tp_summary", 10, 8)
api.shot("tp_summary_page")

-- 翻到技能页
for i = 1, 2 do
    api.tap("RIGHT", 4, 40)
    api.shot(string.format("tp_tab%d", i + 1))
end
api.burst("tp_moves", 10, 8)
api.shot("tp_moves_page")

return api.S
