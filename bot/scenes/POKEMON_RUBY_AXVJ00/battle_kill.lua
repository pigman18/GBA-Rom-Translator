-- ============================================================================
-- battle_kill.lua — 火焰鸡 Lv36 用指定招式打死对手，全流程逐帧对比
--
-- 【用户需求（2026-11-27）】
--   1. 把 4 个招式的场景搭起来
--   2. 同等级下对方被打死的帧应该差不多 ⇒ 基于帧对齐做文本对比
--   3. 汇总不合理的译文 + 目标译文
--
-- 【我方火焰鸡 Lv36 的 4 个技能（实测解密，非猜测）】
--   move id  lexicon       中文        PP
--     10     ひっかく       抓          31
--     64     つつく         啄          31
--     24     にどげり       二连踢      24
--    299     ブレイズキック 火焰踢       3
--   来源：gPlayerParty[0] 解密 pers=DD380E3C species=282 lv=36
--         moves=(10,64,24,299) pp=(31,31,24,3) checksum OK
--   ★ 注意：lexicon 索引 = move id - 1，不能直接用 keys[move_id] 取。
--
-- 【对手】负电拍拍 Lv25（遇敌表注入，双侧同一只）
--   Lv25 时对方 maxHP≈72，我方任一招式都能一击必杀，且对方打不死我方
--   ⇒ 4 个招式都在**同一回合数**内击杀，帧位置天然接近，便于对齐比对。
--
-- 【招式序号由环境变量指定】
--   BOT_MOVE_IDX = 0..3（0=抓 1=啄 2=二连踢 3=火焰踢）
--   不设则默认 2（二连踢）。
--
-- 用法（4 个招式各跑一次）：
--   for i in 0 1 2 3; do
--     BOT_MOVE_IDX=$i python bot/run.py POKEMON_RUBY_AXVJ00 battle_kill \
--       --save roms/outputs/POKEMON_RUBY_AXVJ00_translated.sav \
--       --origin roms/origin/POKEMON_RUBY_AXVJ00.gba \
--       --translated roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba
--   done
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

-- ★ 遇敌表地址按运行侧区分（2026-11-27 实测比对）
--   美版汉化 ROM 的 land 表在 0x0839C838，产物在 0x083786D0，
--   两者字节内容完全相同（12 槽 × 4B），只是 ROM 布局不同。
--   BOT_SIDE：origin=美版、translated=我们的产物
local WILD
if os.getenv("BOT_SIDE") == "origin" then
    WILD = tonumber(os.getenv("BOT_WILD_TABLE") or "") or 0x0839C838
else
    WILD = tonumber(os.getenv("BOT_WILD_TABLE") or "") or 0x083786D0
end
local SPECIES  = tonumber(os.getenv("BOT_SPECIES") or "") or 354
-- ★ 2026-11-27：等级从 25 降到 2。
--   Lv25 时对手会先手「アンコール」(再来一次)+电系麻痹，
--   把火焰鸡的选招完全干扰掉（4 个 run 实际打出的都是「抓」）。
--   Lv2 时对手速度/威力都极低：不会干扰、打不动我方，
--   火焰鸡稳定先手、4 个招式都能干净地打出来 ⇒ 才是可对比的数据。
local LEVEL    = tonumber(os.getenv("BOT_LEVEL") or "") or 2
local MOVE_IDX = tonumber(os.getenv("BOT_MOVE_IDX") or "") or 2

-- 招式序号 → 名称（仅用于日志/文件名，方便认结果）
local MOVE_NAMES = { "hiikaku", "tsutsuku", "nidogeri", "blazekick" }
local MN = MOVE_NAMES[MOVE_IDX + 1] or ("mv" .. MOVE_IDX)

L.preamble(api)
api.shot("bk_ov")

-- ★ 注入遇敌表：12 槽全 = 负电拍拍 Lv25（消灭 RNG 选槽的随机性）
local word = (SPECIES << 16) | (LEVEL << 8) | LEVEL
api.pokecart{
    { addr = WILD + 0x00, width = 4, value = word, note = "s0" },
    { addr = WILD + 0x04, width = 4, value = word, note = "s1" },
    { addr = WILD + 0x08, width = 4, value = word, note = "s2" },
    { addr = WILD + 0x0C, width = 4, value = word, note = "s3" },
    { addr = WILD + 0x10, width = 4, value = word, note = "s4" },
    { addr = WILD + 0x14, width = 4, value = word, note = "s5" },
    { addr = WILD + 0x18, width = 4, value = word, note = "s6" },
    { addr = WILD + 0x1C, width = 4, value = word, note = "s7" },
    { addr = WILD + 0x20, width = 4, value = word, note = "s8" },
    { addr = WILD + 0x24, width = 4, value = word, note = "s9" },
    { addr = WILD + 0x28, width = 4, value = word, note = "s10" },
    { addr = WILD + 0x2C, width = 4, value = word, note = "s11" },
}

-- ── 香甜气息强制遇敌 ───────────────────────────────────────────────────────
L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("bk_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.tap("A", 4, 70)
api.shot("bk_action_menu")
api.tap("A", 4, 70)
api.burst("bk_cast", 8, 6)

-- ── 转场 ───────────────────────────────────────────────────────────────────
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 900, tag = "battle" }
api.burst("bk_transition", 20, 8)

-- ── 开场台词 ───────────────────────────────────────────────────────────────
for i = 1, 3 do
    api.tap("A", 4, 40)
    api.burst(string.format("bk_intro%d", i), 10, 8)
end
api.shot("bk_menu")

-- ── 进招式列表：★ 4 个招名 + PP + 属性行，文本比对核心 ────────────────────
api.tap("A", 4, 60)
api.burst("bk_moves", 12, 8)
api.shot("bk_move_list")

-- ★ 招式菜单导航（2026-11-27 第 3 次修正）
--   实测结论：
--     · 进菜单时光标**已在第 1 项「抓」**，不需要先按 UP 归位
--       （按了 UP 反而会把光标推到菜单外，画面 dispcnt=3F40 变黑）
--     · 只需按 DOWN 共 MOVE_IDX 次即可到目标项
--     · 每次按键后要给足等待（24 帧），否则游戏来不及响应
--   battle_full.lua 也是这个用法：连按 DOWN 遍历 4 个招式。
for _ = 1, MOVE_IDX do api.tap("DOWN", 4, 26) end
api.burst("bk_target", 10, 8)
api.shot("bk_target_" .. MN)
api.shot("bk_target_settled")

-- ===== 出招（一击必杀）=====
api.tap("A", 4, 50)
api.burst("bk_cast_frames", 40, 6)    -- ★ 出招文本/伤害/命中全过程
api.shot("bk_after_cast")

-- ===== 推完「打倒了」+ 经验结算 =====
for i = 1, 4 do api.tap("A", 4, 40) end
api.burst("bk_faint", 20, 6)          -- ★ 「倒下了」文本
for i = 1, 14 do api.tap("A", 4, 36) end
api.burst("bk_exp", 24, 8)            -- ★ 经验结算文本
api.shot("bk_exp_settled")

return api.S
