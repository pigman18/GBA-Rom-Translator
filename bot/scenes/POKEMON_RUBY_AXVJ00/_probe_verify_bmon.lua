-- ============================================================================
-- _probe_verify_bmon.lua — 决定性验证 0x02024838 是不是 gBattleMons
--
-- 【为什么需要验证】
--   候选 C @0x02024838 的 species/六维/moves 都对得上（354、45/51/106/90/93、
--   268/87/226/97），但 hp/maxHP 字段读出来是垃圾值，字段边界没完全确认。
--
-- 【判定方法（最直接）】
--   把这里的 species 改成别的值（如 1=妙蛙种子），
--   **若血条名字跟着变** ⇒ 这就是战斗显示的数据源，定位正确。
--   若不变 ⇒ 不是它，之前改 moves 也没意义。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local BMON = 0x02024838

L.preamble(api)
api.shot("vb_ov")

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
api.burst("vb_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.tap("A", 4, 70)
api.tap("A", 4, 70)
api.burst("vb_cast", 8, 6)
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("vb_in", 8, 6)
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("vb_menu", 10, 4)
api.shot("vb_before")

-- ★ 把 species 改成 1（妙蛙种子）
api.probe{ addr = BMON, len = 0x20, tag = "before" }
api.poke{
    { addr = BMON + 0x00, width = 2, value = 1, note = "species 354->1" },
}
api.probe{ addr = BMON, len = 0x20, tag = "after" }
api.burst("vb_after", 20, 4)
api.shot("vb_final")

return api.S
