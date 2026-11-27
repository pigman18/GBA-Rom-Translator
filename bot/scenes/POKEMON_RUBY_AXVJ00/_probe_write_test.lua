-- ============================================================================
-- _probe_write_test.lua — 验证「战斗后写明文区」能否改变画面
--
-- 【前提（已实测确定）】
--   日版真实地址（符号表 KEEP-US 是错的，这里是实测值）：
--     gPlayerParty = 0x03004290   6 只 × 100B
--     gEnemyParty  = 0x030044F0   6 只 × 100B
--   单只明文区：+0x54 level(1B) / +0x56 curHP(2B) / +0x58 maxHP(2B)
--               +0x5A..0x62 atk/def/spe/spa/spd (各 2B)
--
-- 【本次验证什么】
--   把敌方 E[0] 的：
--     · level 12 → 77
--     · maxHP 32 → 321
--     · curHP 32 → 200
--     · atk   13 → 555
--   然后立刻拍图，看血条上的 Lv 与 HP 数字是否跟着变。
--
--   若变 → 方案 A 成立（战斗后注入有效）
--   若不变 → 战斗初始化已把数据拷进 gBattleMons，必须改那边
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ENEMY0 = 0x030044F0

L.preamble(api)
api.shot("wt_ov")

-- 进战斗
L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("wt_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.tap("A", 4, 70)
api.tap("A", 4, 70)
api.burst("wt_cast", 8, 6)
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("wt_in", 8, 6)
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("wt_menu", 10, 4)
api.shot("wt_before")

-- 写前读一次，确认基线
api.probe{ addr = ENEMY0, len = 100, tag = "enemy_before" }

-- ★ 写明文区
api.poke{
    { addr = ENEMY0 + 0x54, width = 1, value = 77,  note = "level 12->77" },
    { addr = ENEMY0 + 0x58, width = 2, value = 321, note = "maxHP 32->321" },
    { addr = ENEMY0 + 0x56, width = 2, value = 200, note = "curHP 32->200" },
    { addr = ENEMY0 + 0x5A, width = 2, value = 555, note = "atk 13->555" },
}

api.probe{ addr = ENEMY0, len = 100, tag = "enemy_after" }

-- 拍几帧看画面反应（血条是每帧重画的，立刻就能看出）
api.burst("wt_after", 16, 4)
api.shot("wt_final")

return api.S
