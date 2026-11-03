-- ============================================================================
-- _probe_detbattle2.lua — 用「钉 RNG + 同格步进」拿确定性遇敌
--
-- 已实证的事实（不要再试别的）：
--   ✅ 钉 gRngValue（0x03004818）后，两侧走位**逐格完全一致**
--      （origin/translated 的 [POS] 序列一字不差，span 也相同）
--   ❌ gWildEncountersDisabled / sWildEncounterImmunitySteps 写了无效
--      （游戏每帧重算，poke 进去立刻被覆盖）
--   ❌ gWildMonHeaders 结构未定死，改 ROM 有污染产物的风险，不采用
--
-- 本场景做法：**每一步之前都钉同一个 RNG 值**，让「这一步是否遇敌」
-- 成为同一格上的同一判定。走位已证明同步 ⇒ 遇敌格也必然同步。
-- 遇敌后用 await 等战斗界面（黑屏与战斗都认），再连帧采集。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ADDR_RNG = 0x03004818
local SEED     = 0x00001234

L.preamble(api)
api.shot("db2_overworld")

-- 一步步往下走草丛（Route118 起点 68,7，草丛在 y>=10）
-- 每步：钉 RNG → 走一格 → 截图。遇敌后 walk 会 soft-timeout，继续即可。
for i = 1, 24 do
    api.poke{ { addr = ADDR_RNG, width = 4, value = SEED + i, note = "钉 RNG" } }
    api.walk("DOWN", 68, 7 + i, 200, true, 20, "y")
    api.shot(string.format("db2_step%02d", i))
end

-- 等战斗界面：黑屏转场(0x0000) / 战斗画面(0xBF40) / 战斗菜单
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 600, tag = "battle" }
api.burst("db2_battle_in", 16, 8)

return api.S
