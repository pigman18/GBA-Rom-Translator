-- ============================================================================
-- battle_move_anim.lua — 出招动画全程逐帧（BUG-10 撕裂专项）
--
-- 【为什么需要这个场景】（用户 2026-11-19 19:03 明确要求）
--   出招时有几帧画面撕裂：屏幕上下半区不同步、底部出现纯黑带、
--   或上屏是冻结的过渡帧（UI 已上移但菜单框还是空的）。
--   这类问题**只能靠连续帧**看出来，单张 shot 一定会漏。
--   旧记录见 docs/research/FIX_PLAN_BATTLE_BAG_20261116.md 的 B11：
--     「帧 090–104 底部 y112–159 纯黑带；上屏是冻结的过渡帧」
--
-- 【与 battle_full 的区别】
--   battle_full 采的是「各界面定型帧」（菜单、招式列表、队伍）；
--   本场景**只专注出招那一下的逐帧演进**，用 every=1 全帧采集，
--   覆盖：选招式 → 确认 → 动画播放 → 伤害结算 → 返回菜单。
--
-- 【确定性遇敌】2026-11-23 重写。旧注释声称「钉一次 RNG + hunt ⇒ 两侧都在
--   第 5 格遇敌，完全一致」——**实测不成立**，两侧对手不同。
--   正确做法与门槛见下方 §确定性遇敌 注释块；对手一致性必须离线比对 ram。
--   详见 docs/POKEMON_RUBY_AXVJ00/30-问题与验证.md 的 BUG-10 定案。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

-- ── 确定性遇敌：写死对手物种（2026-11-23 定案，取代此前三种失败写法）──
--
-- 【为什么之前三种写法全失败】
--   ① poke 一次 + hunt 40 步（旧法，battle_full 注释曾标「勿改 ✅完全一致」）
--   ② 每走一格 poke 再 walk 一格（_probe_detbattle4 写法）
--   ③ poke -> hunt -> await -> 转场后重钉（battle_menu_audit 写法）
--   三种都做不到「两侧同对手」。原因：两侧 settle 时长不同（译文更长），
--   poke 只决定**写入那一瞬**的 RNG；从写入到「遇敌判定」之间还要跑几十帧，
--   RNG 早被消耗掉。_lib.lua 里也早写过「第 N 格必遇敌做不到」。
--
-- 【实测证据（本次用它量出了 BUG-10 的真根因）】
--   同一帧 bd_battle_in，读 gBattleMons：
--     origin     player=282 Blaziken Lv36 / enemy=338 Lv26
--     translated player=282 Blaziken Lv36 / enemy=288 Lv26
--   我方完全一致，**敌方物种不同**（338 vs 288），等级都是 26。
--   ⇒ 战斗类场景所有同号帧都不可比，BUG-10 的「黑带」就是这么来的。
--
-- 【现在的做法】直接写死敌方 species。
--   gBattleMons 真实地址 = 0x020247E0（不是符号表的 0x02024A80，差 0x2A0）。
--   结构 0x58 字节/battler：species 在 +0x00（u16），level 在 +0x2A（u8）。
--   推导方法：用「我方 Lv36 / 敌方 Lv26」+ 物种 282/288 反查，两级跨度
--   正好 0x58，且六项能力值紧跟在 species 之后 —— 见 docs 的 BUG-10 定案。
--
--   ⚠ 写入时机：`await battle` 之后、进菜单之前。实测 bd_battle_in 帧时
--     species 已填充（=288），此时改不会影响敌方**模型/图鉴**的加载
--     （模型由 species 决定，改了会换外观，但这正是我们要的：两侧同一只）。
local ADDR_RNG      = 0x03004818
local RNG_FIXED     = 0x0000AAAA
local ADDR_BATTLE   = 0x020247E0   -- gBattleMons（实测，非符号表值）
local BATTLER_SZ    = 0x58
local SPECIES_FIXED = 288          -- Zigzagoon：Route118 常见，两侧都写它

L.preamble(api)
api.shot("ov_overworld")

api.hunt{ dir = "DOWN", x = 68, y = 7, steps = 40, timeout = 120 }
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 900, tag = "battle" }

-- ★ 写死敌方物种（battler1 = 对手）+ 转场后重钉 RNG
--   ⚠ 要写**两次**：转场中写一次（尽量赶在模型加载前），进菜单后再写一次。
--     实测只写转场那次无效 —— 那时 gBattleMons 还在被游戏初始化覆盖，
--     写完又被自己的初始化流程刷回去了。
api.poke{
    { addr = ADDR_BATTLE + BATTLER_SZ, width = 2, value = SPECIES_FIXED,
      note = "写死敌方 species（转场中）" },
    { addr = ADDR_RNG, width = 4, value = RNG_FIXED, note = "转场后重钉 RNG" },
}

-- ── 跳过开场台词，尽快进主菜单 ────────────────────────────────────────────
for i = 1, 3 do
    api.tap("A", 4, 40)
end
api.shot("mv_menu")

-- ★ 二次写入：此时 gBattleMons 已定型（实测帧 2 读得出 species/level），
--   这一次一定生效。
api.poke{
    { addr = ADDR_BATTLE + BATTLER_SZ, width = 2, value = SPECIES_FIXED,
      note = "写死敌方 species（进菜单后，确保生效）" },
}

-- ★ 对手校验：进菜单时先拍一张带 dump 的定型帧，离线读 gBattleMons 比对。
--   判据（2026-11-23 定）：player/enemy species 两侧必须相等；
--   enemy 应为 288。不一致即本次采集不可比，重跑。

-- ── 选「战斗」（左上第一项）→ 进招式列表 ──────────────────────────────────
api.tap("A", 4, 60)
api.burst("mv_list", 8, 8)
api.shot("mv_list_settled")

-- ── 选中第 1 个招式并确认 ─────────────────────────────────────────────────
api.tap("A", 4, 20)

-- ★ 核心：出招动画逐帧全采（every=1）
--   40 帧足够覆盖「确认闪光 → 冲向对手 → 命中特效 → 伤害数字 → 血条递减」
--   这一段正是撕裂高发区（B11 记录的 090–104 帧就在这里）
api.burst("mv_cast", 40, 1)

-- ── 动画收尾 + 返回菜单（再看 20 帧，确认没有残留冻结帧）──────────────────
api.burst("mv_settle", 20, 2)
api.shot("mv_back_menu")

-- ── 再出一招（换第 2 个招式），确认撕裂是否与特定招式相关 ─────────────────
api.tap("A", 4, 40)              -- 进招式列表
api.tap("DOWN", 4, 24)           -- 选第 2 个招式
api.tap("A", 4, 20)
api.burst("mv_cast2", 40, 1)
api.burst("mv_settle2", 20, 2)

-- ★ 收尾 dump：黑带类问题必须能读 IO/VRAM 才能定案。
--   burst 帧只落 PNG（bot.lua 的 burst 未接 dumps 参数），
--   所以关键时刻一律补 shot。
api.shot("mv_end")

return api.S
