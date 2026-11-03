-- ============================================================================
-- _probe_detbattle3.lua — 收敛「确定性遇敌」的最后一点偏差
--
-- 上一轮实测：钉 RNG 后两侧 dispcnt 序列只差一格
--   origin     : 6 格野外 → BF40（第 7 格遇敌）
--   translated : 5 格野外 → BF40（第 6 格遇敌）
-- 差值来源：**poke 步骤自己要等 settle**，而两侧 settle 时长不同
--   （translated 侧字多、画面变化久），于是「写 RNG」与「开始走格」之间
--   的帧距不等，走格起步帧就差了。
--
-- 本轮改成：**一次 poke 写完所有需要的值**，然后连续走多格不插 poke。
-- 这样 RNG 差值的注入点只有一个，后面纯靠走位，两侧起点对齐即可。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ADDR_RNG = 0x03004818

L.preamble(api)
api.shot("db3_overworld")

-- 一次性把 RNG 钉死（后续不再写），然后连续走 10 格
api.poke{ { addr = ADDR_RNG, width = 4, value = 0x0000AAAA, note = "钉 RNG 一次" } }

for i = 1, 10 do
    api.walk("DOWN", 68, 7 + i, 200, true, 20, "y")
    api.shot(string.format("db3_step%02d", i))
end

api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 600, tag = "battle" }
api.burst("db3_battle", 14, 8)

return api.S
