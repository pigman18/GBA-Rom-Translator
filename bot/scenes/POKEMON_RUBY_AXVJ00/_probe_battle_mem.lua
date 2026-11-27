-- ============================================================================
-- _probe_battle_mem.lua — 诊断：战斗界面里血条读的是哪个结构？
--
-- 【要回答的问题】
--   方案 A 想「战斗开始后写明文区改等级/六血」，但必须先确认：
--     ① 血条显示的 Lv/HP 到底来自 gEnemyParty 还是 gBattleMons？
--     ② 战斗初始化后，写 gEnemyParty 还有没有用（会不会被覆盖）？
--
-- 【做法】
--   进战斗后，用 probe 把两处内存都 dump 下来，比对：
--     · gEnemyParty[0]  0x030045C0  len=100
--     · gBattleMons[1]  0x02024A80 + 1*0x58  len=0x58（敌方是 battler 1）
--   同时拍图存证，人工核对血条上的 Lv/HP 与哪份数据吻合。
--
-- 【用法】
--   python bot/run.py POKEMON_RUBY_AXVJ00 _probe_battle_mem \
--     --save roms/outputs/POKEMON_RUBY_AXVJ00_translated.sav \
--     --translated roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba \
--     --origin roms/origin/POKEMON_RUBY_AXVJ00.gba
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("pm_ov")

-- ① 进宝可梦菜单 → 选第 6 只 → 野外招式（香甜气息）
L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("pm_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.shot("pm_last")
api.tap("A", 4, 70)
api.shot("pm_action")
api.tap("A", 4, 70)
api.burst("pm_cast", 8, 6)
api.shot("pm_after_cast")

-- ② 等进战斗
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("pm_in", 8, 6)

-- ③ 推台词到主菜单（血条定态）
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("pm_menu", 10, 4)
api.shot("pm_settled")

-- ④ ★ 核心：dump 内存
--    gEnemyParty[0]：整 100B
api.probe{ addr = 0x030045C0, len = 100, tag = "enemy_party0" }
--    gEnemyPartyCount
api.probe{ addr = 0x030045B8, len = 4, tag = "enemy_count" }
--    gBattleMons[1]（敌方 battler）：单只 0x58 = 88B，多读一点留余量
api.probe{ addr = 0x02024A80 + 0x58, len = 96, tag = "battlemon1" }
--    gBattleMons[0]（我方）作对照
api.probe{ addr = 0x02024A80, len = 96, tag = "battlemon0" }

api.shot("pm_done")
return api.S
