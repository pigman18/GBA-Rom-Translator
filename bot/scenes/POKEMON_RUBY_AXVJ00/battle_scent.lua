-- ============================================================================
-- battle_scent.lua — 香甜气息强制遇敌（**不写死 species**）
--
-- 【固定遇敌原理（本场景的核心）】
--   不靠钉 RNG、不靠写 gBattleMons species，而是**改遇敌表**：
--   scripts/battle/fix_encounter.py 把目标地图 land 表的 12 个槽全部
--   改成同一 species（Route110 → 354 负电拍拍）。
--
--   源码依据（pokeruby src/wild_encounter.c）：
--     landMonsInfo->wildPokemon[ChooseWildMonIndex_Land()].species
--   ChooseWildMonIndex_Land() = Random()%100 分 12 档 → 返回 0..11
--   ⇒ 12 槽同物种时，**无论 RNG 落哪档结果都一样**，随机性被消灭而非追逐。
--
--   ⚠ 前提：origin 与 translated 两侧 ROM 都要打同一份补丁，
--     否则一侧仍是混合表、另一侧固定，对照不成立。
--
-- 【操作路线】（_probe_scent 实测确认）
--   野外 → START → 第2项「ポケモン」→ A → 队伍列表
--   → DOWN×5 选第6只（带香甜气息）→ A → 动作菜单第1项 → A
--
-- 用法：
--   python bot/run.py POKEMON_RUBY_AXVJ00 battle_scent \
--     --save roms/outputs/POKEMON_RUBY_AXVJ00_translated.sav \
--     --origin work/_fixtest/origin_n354.gba \
--     --translated work/_fixtest/trans_n354.gba
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("sc_ov")

-- ① 进宝可梦菜单
L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("sc_party_enter", 8, 6)

-- ② 选第 6 只（带香甜气息）
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.shot("sc_party_last")

-- ③ 动作菜单 → 第 1 项（野外招式）
api.tap("A", 4, 70)
api.shot("sc_action_menu")
api.tap("A", 4, 70)
api.burst("sc_cast", 10, 6)
api.shot("sc_after_cast")

-- ④ 等进战斗
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("sc_battle_in", 8, 6)
api.shot("sc_in_battle")

-- ⑤ 推台词到主菜单，拍血条定态
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("sc_menu", 12, 4)
api.shot("sc_menu_settled")

return api.S
