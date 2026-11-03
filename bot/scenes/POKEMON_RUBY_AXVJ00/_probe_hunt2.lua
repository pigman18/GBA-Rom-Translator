-- ============================================================================
-- _probe_hunt2.lua — hunt + 固定 RNG（两者结合）
--
-- 单独 hunt 的问题：遇敌本身随机，translated 侧 30 格没遇到、origin 6 格就遇到。
-- 单独钉 RNG 的问题：能大幅提升一致率，但遇敌格仍差 1。
-- 两者结合：
--   · 每格开走之前钉同一个 RNG 值 → 让「这一步是否遇敌」的输入完全相同
--   · hunt 一遇敌就停 → 把残余的 ±1 格差异吸收在内部
-- 只要两侧**至少都遇到了**，就从同一个战斗画面对齐。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ADDR_RNG = 0x03004818

L.preamble(api)
api.shot("h2_overworld")

-- 先钉一次 RNG（hunt 内部逐格移动，不再逐格写，避免 poke 的 settle 影响走位）
api.poke{ { addr = ADDR_RNG, width = 4, value = 0x0000AAAA, note = "钉 RNG" } }

api.hunt{ dir = "DOWN", x = 68, y = 7, steps = 40, timeout = 120 }

api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 900, tag = "battle" }
api.burst("h2_transition", 16, 8)
api.shot("h2_in_battle")

return api.S
