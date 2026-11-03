-- ============================================================================
-- _probe_rng.lua — 验证「钉住 gRngValue 能否让两侧遇敌完全一致」
--
-- 问题：野外遇敌是 RNG 判定，origin 与 translated 的文本打印耗时不同 ⇒
--       按键落在不同游戏帧 ⇒ 遇敌判定分岔。历史上这直接把对照废掉过。
--
-- 方案：每走一步前后都把 gRngValue（0x03004818，符号表 KEEP-US 可信）
--       写成同一个定值。这样每格步进的判定输入完全相同，两侧必然同结果。
--
-- 本场景只做验证：走 6 格草丛，打印每格前后的 RNG 与坐标，看两侧是否一致。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local RNG_ADDR = 0x03004818
local SEED = 0x00001234

L.preamble(api)
api.shot("rng_overworld")

-- 每格开始前钉 RNG，然后走一格
for i = 1, 8 do
    api.poke{ { addr = RNG_ADDR, width = 4, value = SEED + i, note = "钉 RNG" } }
    api.walk("DOWN", 68, 7 + i, 240, true, 20, "y")
    api.shot(string.format("rng_step%d", i))
end

api.burst("rng_end", 6, 8)
return api.S
