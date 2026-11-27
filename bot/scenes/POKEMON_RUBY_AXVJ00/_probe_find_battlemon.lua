-- ============================================================================
-- _probe_find_battlemon.lua — 定位 gBattleMons（战斗显示的数据源）
--
-- 【为什么必须找它】
--   已验证：gEnemyParty（0x030044F0）不是战斗显示的数据源 ——
--   写它的明文派生区被下一帧覆盖，写它的加密区导致整只被重建。
--
--   而用户新需求（对方只有 1 个技能 + 携带气势头巾）超出了遇敌表的能力
--   （遇敌表只有 minLevel/maxLevel/species）。这类字段只能改战斗中的副本，
--   即 gBattleMons。
--
-- 【定位策略】
--   进战斗后扫 EWRAM 全段（0x02000000..0x02040000），
--   按「species=354」搜 u16 命中；再按「lv=50」「hp 合理」二次筛选。
--   上一轮只扫了 0..0x26000 命中 0 处，这次扫满 256KB。
--
-- 【gBattleMons 结构参考（pokeruby include/battle.h）】
--   struct BattlePokemon {
--     u16 species; u16 attack; u16 defense; u16 speed;
--     u16 spAttack; u16 spDefense;
--     u16 moves[4]; u32 hp; u32 maxHP;
--     u16 item;  u16 ability; ...
--   }   —— 单只约 0x58 字节
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("fm_ov")

-- 先把目标固定：species 354 / lv50
local WILD = 0x083786D0
local word = (354 << 16) | (50 << 8) | 50
api.pokecart{
    { addr = WILD + 0x00, width = 4, value = word },
    { addr = WILD + 0x04, width = 4, value = word },
    { addr = WILD + 0x08, width = 4, value = word },
    { addr = WILD + 0x0C, width = 4, value = word },
    { addr = WILD + 0x10, width = 4, value = word },
    { addr = WILD + 0x14, width = 4, value = word },
    { addr = WILD + 0x18, width = 4, value = word },
    { addr = WILD + 0x1C, width = 4, value = word },
    { addr = WILD + 0x20, width = 4, value = word },
    { addr = WILD + 0x24, width = 4, value = word },
    { addr = WILD + 0x28, width = 4, value = word },
    { addr = WILD + 0x2C, width = 4, value = word },
}

-- 进战斗
L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("fm_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.tap("A", 4, 70)
api.tap("A", 4, 70)
api.burst("fm_cast", 8, 6)
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("fm_in", 8, 6)
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("fm_menu", 10, 4)
api.shot("fm_settled")

-- ★ 扫 EWRAM 全段找 species 354（u16）
for i = 0, 3 do
    api.scan{ addr = 0x02000000 + i * 0x10000, len = 0x10000,
              value = 354, width = 2, tag = "sp354_" .. i }
end

-- 也扫 IWRAM
for i = 0, 1 do
    api.scan{ addr = 0x03000000 + i * 0x8000, len = 0x8000,
              value = 354, width = 2, tag = "isp354_" .. i }
end

api.shot("fm_done")
return api.S
