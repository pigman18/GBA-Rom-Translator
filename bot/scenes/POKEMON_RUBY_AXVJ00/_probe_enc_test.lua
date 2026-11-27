-- ============================================================================
-- _probe_enc_test.lua — 写加密区能否改变战斗画面
--
-- 【背景（实测确认）】
--   写 gEnemyParty[0] 的明文派生区（level/maxHP/curHP/atk）无效：
--   poke 复核成功，但下一帧游戏从加密区重算后覆盖，血条不变。
--   真正决定 species/exp/IVs/moves 的是 +0x20 起的 48B 加密区。
--   加密算法已用真实内存反解验证：species=354、checksum 0xA781 精确匹配。
--
-- 【本次验证】
--   把 build_mon.py 生成的 100B 结构（species 354 / lv50 / IV全31 /
--   技能 45,86,98,270）写入 gEnemyParty[0]，看血条 Lv 是否变成 50。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ENEMY0 = 0x030044F0

L.preamble(api)
api.shot("et_ov")

L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("et_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.tap("A", 4, 70)
api.tap("A", 4, 70)
api.burst("et_cast", 8, 6)
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("et_in", 8, 6)
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("et_menu", 10, 4)
api.shot("et_before")

api.probe{ addr = ENEMY0, len = 100, tag = "before" }

-- ★ 写 personality + checksum + 加密区 + level
api.poke{
    { addr = ENEMY0 + 0x00, width = 4, value = 0x1A2B3C4C, note = "+00 personality" },
    { addr = ENEMY0 + 0x10, width = 4, value = 0x00020000, note = "+10 lang" },
    { addr = ENEMY0 + 0x1C, width = 4, value = 0x0000D3F6, note = "+1C checksum" },
    { addr = ENEMY0 + 0x20, width = 4, value = 0x1A2B3D2E, note = "+20" },
    { addr = ENEMY0 + 0x24, width = 4, value = 0x1A2AD404, note = "+24" },
    { addr = ENEMY0 + 0x28, width = 4, value = 0x1A2B7A4C, note = "+28" },
    { addr = ENEMY0 + 0x2C, width = 4, value = 0x3B19254C, note = "+2C" },
    { addr = ENEMY0 + 0x30, width = 4, value = 0x25D4C3B3, note = "+30" },
    { addr = ENEMY0 + 0x34, width = 4, value = 0x1A2B3C4C, note = "+34" },
    { addr = ENEMY0 + 0x38, width = 4, value = 0x1A7D3C61, note = "+38" },
    { addr = ENEMY0 + 0x3C, width = 4, value = 0x1B253C2E, note = "+3C" },
    { addr = ENEMY0 + 0x40, width = 4, value = 0x0E3F2858, note = "+40" },
    { addr = ENEMY0 + 0x44, width = 4, value = 0x1A2B3C4C, note = "+44" },
    { addr = ENEMY0 + 0x48, width = 4, value = 0x1A2B3C4C, note = "+48" },
    { addr = ENEMY0 + 0x4C, width = 4, value = 0x1A2B3C4C, note = "+4C" },
    { addr = ENEMY0 + 0x54, width = 4, value = 0x00000032, note = "+54 level=50" },
}

api.probe{ addr = ENEMY0, len = 100, tag = "after" }
api.burst("et_after", 20, 4)
api.shot("et_final")
return api.S
