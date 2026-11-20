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
-- 【确定性遇敌】沿用 battle_full 已验证的写法（勿改）：
--   钉一次 RNG + hunt ⇒ 两侧都在第 5 格遇敌，帧对齐可靠。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ADDR_RNG = 0x03004818

L.preamble(api)
api.shot("ov_overworld")

-- ── 确定性遇敌（与 battle_full 同款）──────────────────────────────────────
api.poke{ { addr = ADDR_RNG, width = 4, value = 0x0000AAAA, note = "钉 RNG" } }
api.hunt{ dir = "DOWN", x = 68, y = 7, steps = 40, timeout = 120 }

api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 900, tag = "battle" }

-- ── 跳过开场台词，尽快进主菜单 ────────────────────────────────────────────
for i = 1, 3 do
    api.tap("A", 4, 40)
end
api.shot("mv_menu")

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

return api.S
