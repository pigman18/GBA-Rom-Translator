-- ============================================================================
-- _probe_rom_write.lua — 决定性测试：能否在运行时写 ROM 遇敌表？
--
-- 【为什么试这条】
--   已实测失败的两条路：
--     ① 写 gEnemyParty[0] 明文派生区（+0x54 level / +0x56 curHP / +0x5A atk）
--        → poke 复核成功，下一帧被游戏重算覆盖，血条不变
--     ② 写 gEnemyParty[0] 加密区（+0x20 起 48B，含 species/exp/IVs/moves）
--        → 17 条写入全成功，读回时 personality 已被换成别的值、species 变 367
--   说明 gEnemyParty 不是战斗显示的数据源，游戏会重建它。
--
--   本测试改走标准金手指原理：**在运行时把 ROM 的遇敌表改掉**。
--   ROM 在 GBA 上是只读掩膜，但模拟器通常允许写（供金手指用）。
--   若 mGBA 允许，这条路可以复用现有 fix_encounter 的 12 槽逻辑，
--   且完全不碰磁盘上的 ROM 文件。
--
-- 【表结构（fix_encounter.py 实测）】
--   map 0:25 (Route110)  wildPokemon = 0x083786D0，12 槽 × 4B
--   每槽：minLevel u8 | maxLevel u8 | species u16
--
-- 【判定】
--   · 若 poke 报「复核失败」→ mGBA 拒绝写 ROM，此路不通
--   · 若 poke 成功且随后遇到的怪变成 354(lv25) → 此路成立
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local WILD = 0x083786D0     -- map 0:25 land 表，12 槽
local SPECIES = 354          -- 负电拍拍
local LEVEL = 25

L.preamble(api)
api.shot("rw_ov")

-- 写前读一次基线
api.probe{ addr = WILD, len = 48, tag = "wild_before" }

-- ★ 12 槽全部改成 species 354 / lv25（消灭 RNG 选槽带来的随机性）
--   槽 = minLevel u8 | maxLevel u8 | species u16 → 0x0162_1919
api.pokecart{
    { addr = WILD + 0x00, width = 4, value = 0x01621919, note = "slot0" },
    { addr = WILD + 0x04, width = 4, value = 0x01621919, note = "slot1" },
    { addr = WILD + 0x08, width = 4, value = 0x01621919, note = "slot2" },
    { addr = WILD + 0x0C, width = 4, value = 0x01621919, note = "slot3" },
    { addr = WILD + 0x10, width = 4, value = 0x01621919, note = "slot4" },
    { addr = WILD + 0x14, width = 4, value = 0x01621919, note = "slot5" },
    { addr = WILD + 0x18, width = 4, value = 0x01621919, note = "slot6" },
    { addr = WILD + 0x1C, width = 4, value = 0x01621919, note = "slot7" },
    { addr = WILD + 0x20, width = 4, value = 0x01621919, note = "slot8" },
    { addr = WILD + 0x24, width = 4, value = 0x01621919, note = "slot9" },
    { addr = WILD + 0x28, width = 4, value = 0x01621919, note = "slot10" },
    { addr = WILD + 0x2C, width = 4, value = 0x01621919, note = "slot11" },
}

-- 写后读回（poke 已逐条复核，这里再整体确认一次）
api.probe{ addr = WILD, len = 48, tag = "wild_after" }

-- ★ 触发遇敌：START → 宝可梦 → 第 6 只 → 野外招式（香甜气息）
L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("rw_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.tap("A", 4, 70)
api.tap("A", 4, 70)
api.burst("rw_cast", 8, 6)
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("rw_in", 8, 6)
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("rw_menu", 12, 4)
api.shot("rw_settled")

return api.S
