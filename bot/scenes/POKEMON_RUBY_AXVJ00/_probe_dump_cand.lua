-- ============================================================================
-- _probe_dump_cand.lua — dump gBattleMons 候选地址
--
-- 【上一轮扫描结果】
--   EWRAM 里 species=354 命中 3 处：
--     0x02020146 / 0x020241C4 / 0x02024838
--   IWRAM 命中 0x03001DFD / 0x03009DFD（地址不对齐 4，疑似误报）
--
-- 【本场景】
--   把 3 处候选各 dump 0x80 字节，离线分析哪个符合 struct BattlePokemon：
--     u16 species | u16 attack | u16 defense | u16 speed | u16 spAtk | u16 spDef
--     u16 moves[4] | u32 hp | u32 maxHP | u16 item | u16 ability ...
--   判据：species=354、六维合理、moves 里有真实招式、hp<=maxHP。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("dc_ov")

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
api.burst("dc_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.tap("A", 4, 70)
api.tap("A", 4, 70)
api.burst("dc_cast", 8, 6)
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("dc_in", 8, 6)
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("dc_menu", 10, 4)
api.shot("dc_settled")

-- ★ dump 3 处候选（各 0x80 字节，从命中地址往前退 8 字节，确保含结构头）
api.probe{ addr = 0x02020140, len = 0x80, tag = "cand_A" }
api.probe{ addr = 0x020241B8, len = 0x80, tag = "cand_B" }
api.probe{ addr = 0x02024830, len = 0x80, tag = "cand_C" }

-- 同时 dump 我方（火焰鸡 species 256?）附近作结构对照
-- 火焰鸡日版 species 编号 = 256（木守宫是 277? 需现场确认，先 dump 大范围）
api.scan{ addr = 0x02020000, len = 0x10000, value = 256, width = 2,
          tag = "sp256" }

api.shot("dc_done")
return api.S
