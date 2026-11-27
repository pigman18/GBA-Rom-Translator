-- ============================================================================
-- battle_kill.lua — 火焰鸡 Lv36 打死对方的全流程帧对比
--
-- 【用户需求】
--   「按 火焰鸡-Lv36-{技能名称} 出场景，从头到尾打死对方，切成帧对比翻译」
--
-- 【我方火焰鸡 Lv36 的 4 个技能（实测解密，非猜测）】
--   编号 10  はさむ        夹住        PP 31
--   编号 64  ドリルくちばし 啄钻        PP 31
--   编号 24  メガトンキック 百万吨重踢  PP 24
--   编号 299 どろあそび    玩泥巴      PP 3
--   来源：gPlayerParty[0] 解密 pers=DD380E3C species=282 lv=36
--         moves=(10,64,24,299) pp=(31,31,24,3) checksum OK
--
-- 【对手】负电拍拍 Lv25（遇敌表注入，双侧同一只）
--   为什么不是 Lv50：实测 Lv50 时对方速度更快，先手把火焰鸡打到 6/115，
--   我方反而先死。Lv25：maxHP≈72，我方百万吨重踢一击≈175 ⇒ 一击必杀，
--   且对方一击只打我≈21，不会反杀。
--   一击必杀同样能看到完整过程：出招→命中→伤害数字→倒下→经验结算。
--
-- 【出招】百万吨重踢（第 3 项）
--   5 个汉字，是最长招名，最能暴露宽度/换行/截断问题。
--
-- 【节奏】完全对齐 battle_full.lua（已验证可用的那个）：
--   tap("A", 4, 60) 进招式列表、burst(n, 8) 逐帧、每步后 shot
--   之前用 burst(n, 2) 太密 + 等待过短，导致卡在队伍列表没进战斗。
--
-- 用法：
--   python bot/run.py POKEMON_RUBY_AXVJ00 battle_kill \
--     --save roms/outputs/POKEMON_RUBY_AXVJ00_translated.sav \
--     --origin roms/origin/POKEMON_RUBY_AXVJ00.gba \
--     --translated roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local WILD    = tonumber(os.getenv("BOT_WILD_TABLE") or "") or 0x083786D0
local ADDR_RNG = 0x03005000 + 0x0   -- 占位，实际用 hunt 不依赖它
local SPECIES = 354
local LEVEL   = 25
local MOVE_IDX = 2                  -- 0=夹住 1=啄钻 2=百万吨重踢 3=玩泥巴

L.preamble(api)
api.shot("bk_ov")

-- ★ 注入遇敌表：12 槽全 = 负电拍拍 Lv50（消灭 RNG 选槽的随机性）
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

-- ── 香甜气息强制遇敌（比走草丛 hunt 可靠；battle_custom 已验证）─────────────
L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("bk_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.shot("bk_party_last")
api.tap("A", 4, 70)
api.shot("bk_action_menu")
api.tap("A", 4, 70)
api.burst("bk_cast", 8, 6)

-- ── 转场 ───────────────────────────────────────────────────────────────────
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 900, tag = "battle" }
api.burst("bk_transition", 20, 8)

-- ── 开场台词逐句推进 ───────────────────────────────────────────────────────
for i = 1, 3 do
    api.tap("A", 4, 40)
    api.burst(string.format("bk_intro%d", i), 10, 8)
end

-- ── 战斗主菜单（2×2：战斗/背包/宝可梦/逃跑）────────────────────────────────
api.shot("bk_menu")

-- ── 进招式列表 ─────────────────────────────────────────────────────────────
api.tap("A", 4, 60)
api.burst("bk_moves", 12, 8)          -- ★ 4 个招名 + PP + 属性（重点比对）
api.shot("bk_move_list")

-- 逐个招式移动光标，每个都拍（招名文本逐项验证）
for i = 2, 4 do
    api.tap("DOWN", 4, 24)
    api.burst(string.format("bk_move_%d", i), 4, 6)
    api.shot(string.format("bk_move_sel_%d", i))
end
-- 回到目标招式
for _ = 1, (4 - MOVE_IDX - 1) do api.tap("UP", 4, 24) end
api.shot("bk_move_target")

-- ===== 第 1 回合：出招 =====
api.tap("A", 4, 50)
api.burst("bk_r1_cast", 40, 8)        -- ★ 攻击动画/伤害/台词全过程
api.shot("bk_r1_after")

-- 推台词回菜单
for i = 1, 4 do api.tap("A", 4, 40) end
api.burst("bk_r1_end", 10, 8)
api.shot("bk_r1_menu")

-- ===== 收尾：若一击未死则再打一次（Lv25 通常已死，这里是兜底）=====
api.tap("A", 4, 60)
api.burst("bk_r2_moves", 8, 8)
for _ = 1, (MOVE_IDX + 1 - 1) do api.tap("DOWN", 4, 24) end
api.shot("bk_r2_target")
api.tap("A", 4, 50)
api.burst("bk_r2_cast", 60, 8)        -- ★ 第2次攻击 + 对方倒下
api.shot("bk_r2_after")

-- ── 胜利 / 经验结算 ────────────────────────────────────────────────────────
for i = 1, 14 do api.tap("A", 4, 36) end
api.burst("bk_win", 24, 8)
api.shot("bk_win_settled")

return api.S
