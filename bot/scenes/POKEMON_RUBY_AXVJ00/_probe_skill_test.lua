-- ============================================================================
-- _probe_skill_test.lua — 验证「改等级能否带来技能变化」
--
-- 【背景】
--   Gen3 野生宝可梦的技能由 GiveMonInitialMoveset 按「等级可达的最近4招」生成，
--   IV/性格由 CreateMon 随机 —— 这三项**不在遇敌表里**，无法直接指定。
--   但等级可控（遇敌表 minLevel/maxLevel）。
--
--   所以要确认：把等级从 13 拉到 50，敌方技能是否会跟着变成高等级招式？
--   若会 → 用「等级」间接控制技能，能满足「测招式名文本 BUG」的需求。
--
-- 【做法】
--   pokecart 把 12 槽改成 species 354 / lv50，进战斗后
--   打开「战斗」菜单 → 招式列表，拍下招式名。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local WILD = 0x083786D0
local LV = 50

L.preamble(api)
api.shot("st_ov")

-- 12 槽 → species 354 / lv50
local w = 354 * 0x10000 + LV * 0x100 + LV
api.pokecart{
    { addr = WILD + 0x00, width = 4, value = w, note = "slot0" },
    { addr = WILD + 0x04, width = 4, value = w, note = "slot1" },
    { addr = WILD + 0x08, width = 4, value = w, note = "slot2" },
    { addr = WILD + 0x0C, width = 4, value = w, note = "slot3" },
    { addr = WILD + 0x10, width = 4, value = w, note = "slot4" },
    { addr = WILD + 0x14, width = 4, value = w, note = "slot5" },
    { addr = WILD + 0x18, width = 4, value = w, note = "slot6" },
    { addr = WILD + 0x1C, width = 4, value = w, note = "slot7" },
    { addr = WILD + 0x20, width = 4, value = w, note = "slot8" },
    { addr = WILD + 0x24, width = 4, value = w, note = "slot9" },
    { addr = WILD + 0x28, width = 4, value = w, note = "slot10" },
    { addr = WILD + 0x2C, width = 4, value = w, note = "slot11" },
}

-- 触发遇敌
L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("st_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.tap("A", 4, 70)
api.tap("A", 4, 70)
api.burst("st_cast", 8, 6)
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("st_in", 8, 6)
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("st_menu", 10, 4)
api.shot("st_battle_menu")

-- 读加密区，看技能到底是什么（解密由 Python 侧做）
api.probe{ addr = 0x030044F0, len = 100, tag = "enemy_mon" }

-- 打开「战斗」→ 招式列表
api.tap("A", 4, 60)
api.burst("st_moves", 10, 4)
api.shot("st_moves_settled")

-- 再读一次（战斗正式开始后结构可能已变）
api.probe{ addr = 0x030044F0, len = 100, tag = "enemy_mon2" }

return api.S
