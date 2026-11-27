-- ============================================================================
-- _probe_one_move.lua — 对方只留 1 个技能 + 携带气势头巾
--
-- 【已定位的结构】
--   候选 C @0x02024838 是 struct BattlePokemon，实测字段：
--     +0x00 species = 0x0162 (354 负电拍拍)
--     +0x02..0x0A attack/defense/speed/spAtk/spDef  = 45/51/106/90/93
--     +0x0C moves[0..3] = 268, 87, 226, 97
--   与「lv50 负电拍拍按等级生成的招式」完全一致 ⇒ 定位正确。
--
-- 【本次目标（用户需求）】
--   ① 对方只有 1 个技能 → moves[1..3] = 0
--   ② 携带气势头巾（Focus Band，item id 需现场确认）
--
-- 【做法】
--   写 moves[1..3] = 0，然后打开招式列表看是否只剩 1 项。
--   item 先试几个常见 id，看道具图标是否出现。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local BMON = 0x02024838   -- struct BattlePokemon（敌方）

L.preamble(api)
api.shot("om_ov")

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

L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("om_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.tap("A", 4, 70)
api.tap("A", 4, 70)
api.burst("om_cast", 8, 6)
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("om_in", 8, 6)
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("om_menu", 10, 4)
api.shot("om_before")

api.probe{ addr = BMON, len = 0x60, tag = "before" }

-- ★ moves[1..3] = 0（只留 moves[0]=268 挑衅）
--   moves[1] 在 +0x0E，moves[2] +0x10，moves[3] +0x12
api.poke{
    { addr = BMON + 0x0E, width = 2, value = 0, note = "moves[1]=0" },
    { addr = BMON + 0x10, width = 2, value = 0, note = "moves[2]=0" },
    { addr = BMON + 0x12, width = 2, value = 0, note = "moves[3]=0" },
}

api.probe{ addr = BMON, len = 0x60, tag = "after" }
api.shot("om_after_poke")

-- 打开「战斗」→ 招式列表，看是否只剩 1 项
api.tap("A", 4, 60)
api.burst("om_moves", 12, 4)
api.shot("om_moves_settled")

return api.S
