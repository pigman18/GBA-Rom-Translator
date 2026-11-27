-- ============================================================================
-- battle_custom.lua — 自定义对手战斗场景（运行时注入，不改 ROM 文件）
--
-- 【与 battle_scent 的区别】
--   battle_scent：依赖预先改好的 ROM 副本（--origin work/_fixtest/origin_n354.gba）
--   本场景：用 api.pokecart 在运行时改写 ROM 域的遇敌表
--           ⇒ 两侧（origin/translated）用**同一份原版 ROM**，天然保证同一只怪
--
-- 【可调参数（改文件顶部即可）】
--   SPECIES / MIN_LV / MAX_LV
--
-- 【为什么 12 槽全改】
--   源码 chooseWildMonIndex_Land() = Random()%100 分 12 档 → 0..11。
--   12 槽同物种 ⇒ 无论 RNG 落哪档结果都一样，随机性被消灭。
--
-- 【已知边界】
--   物种/等级可控；技能随等级自动生成（间接可控）；
--   六维 IV/性格由游戏随机，无法指定。详见 docs/.../60-固定遇敌方案.md
--
-- 用法：
--   python bot/run.py POKEMON_RUBY_AXVJ00 battle_custom \
--     --save roms/outputs/POKEMON_RUBY_AXVJ00_translated.sav \
--     --origin roms/origin/POKEMON_RUBY_AXVJ00.gba \
--     --translated roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

-- ── 可调参数 ────────────────────────────────────────────────────────────────
local SPECIES = 354        -- 负电拍拍
local MIN_LV  = 50
local MAX_LV  = 50
local WILD    = 0x083786D0 -- map 0:25 (Route110) land 表，12 槽 × 4B
-- ────────────────────────────────────────────────────────────────────────────

L.preamble(api)
api.shot("bc_ov")

-- ★ 运行时改遇敌表（不改磁盘 ROM）
local word = (SPECIES << 16) | ((MAX_LV & 0xFF) << 8) | (MIN_LV & 0xFF)
api.pokecart{
    { addr = WILD + 0x00, width = 4, value = word, note = "slot0" },
    { addr = WILD + 0x04, width = 4, value = word, note = "slot1" },
    { addr = WILD + 0x08, width = 4, value = word, note = "slot2" },
    { addr = WILD + 0x0C, width = 4, value = word, note = "slot3" },
    { addr = WILD + 0x10, width = 4, value = word, note = "slot4" },
    { addr = WILD + 0x14, width = 4, value = word, note = "slot5" },
    { addr = WILD + 0x18, width = 4, value = word, note = "slot6" },
    { addr = WILD + 0x1C, width = 4, value = word, note = "slot7" },
    { addr = WILD + 0x20, width = 4, value = word, note = "slot8" },
    { addr = WILD + 0x24, width = 4, value = word, note = "slot9" },
    { addr = WILD + 0x28, width = 4, value = word, note = "slot10" },
    { addr = WILD + 0x2C, width = 4, value = word, note = "slot11" },
}

-- ① 进宝可梦菜单
L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("bc_party_enter", 8, 6)

-- ② 选第 6 只（带香甜气息）
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.shot("bc_party_last")

-- ③ 动作菜单 → 第 1 项（野外招式）
api.tap("A", 4, 70)
api.shot("bc_action_menu")
api.tap("A", 4, 70)
api.burst("bc_cast", 10, 6)
api.shot("bc_after_cast")

-- ④ 等进战斗
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("bc_battle_in", 8, 6)
api.shot("bc_in_battle")

-- ⑤ 推台词到主菜单，拍血条定态
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("bc_menu", 12, 4)
api.shot("bc_menu_settled")

-- ⑥ 打开招式列表（验证技能文本）
api.tap("A", 4, 60)
api.burst("bc_moves", 10, 4)
api.shot("bc_moves_settled")

return api.S
