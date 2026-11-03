-- ============================================================================
-- _probe_detbattle4.lua — 每格钉同一个 RNG 值（不是递增）
--
-- 前几轮实测：
--   · 每格钉**递增**值（SEED+i）→ 两侧遇敌格差 1
--   · 只钉一次整个序列 → 这次干脆没遇敌
-- 差值来源：poke 步骤自身要等 settle，而两侧 settle 时长不同（译文更长），
--          于是「写 RNG」到「开始走格」之间的帧距不等。
--
-- 本轮把变更点压到最小：**每格都写同一个值**（不是递增）。
-- 这样即使两侧写 RNG 的时机差几帧，写入后游戏看到的 RNG 状态**完全相同**，
-- 每一步的遇敌判定输入也就完全相同。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ADDR_RNG = 0x03004818
local FIXED    = 0x0000AAAA

L.preamble(api)
api.shot("db4_overworld")

for i = 1, 14 do
    api.poke{ { addr = ADDR_RNG, width = 4, value = FIXED, note = "钉同一 RNG" } }
    api.walk("DOWN", 68, 7 + i, 200, true, 20, "y")
    api.shot(string.format("db4_step%02d", i))
end

api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 600, tag = "battle" }
api.burst("db4_battle", 14, 8)

return api.S
