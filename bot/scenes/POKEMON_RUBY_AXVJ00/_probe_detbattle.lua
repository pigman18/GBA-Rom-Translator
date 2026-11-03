-- ============================================================================
-- _probe_detbattle.lua — 确定性遇敌实验（三种手段逐个试，看哪个可靠）
--
-- 背景：野外遇敌是 RNG，两侧文本打印耗时不同 ⇒ 按键落在不同帧 ⇒ 判定分岔。
--       上一轮实测：钉住 gRngValue 后两侧走位**逐格一致**，但遇敌格仍差 1
--       （origin 第7格、translated 第8格）—— 因为两边进入每格的帧号还差几帧。
--
-- 本轮试三种「确定性」手段，逐个看效果：
--   ① 关掉随机遇敌（gWildEncountersDisabled @0x0202FF7C = 1）
--   ② 把免疫步数设大（sWildEncounterImmunitySteps @0x0202E8C0）
--   ③ 在①的前提下，用固定 RNG 走草丛 → 应当**永远不遇敌**
--      这本身就是确定性：之后由别的场景按需触发战斗。
--
-- ⚠ 这两个符号标 KEEP-US（日美地址一致），可信度高，但仍以实测为准。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ADDR_RNG        = 0x03004818   -- gRngValue
local ADDR_ENCOUNTERS = 0x0202FF7C   -- gWildEncountersDisabled
local ADDR_IMMUNITY   = 0x0202E8C0   -- sWildEncounterImmunitySteps
local SEED            = 0x00001234

L.preamble(api)
api.shot("db_overworld")

-- ① 关掉随机遇敌
api.poke{ { addr = ADDR_ENCOUNTERS, width = 1, value = 1, note = "禁用随机遇敌" } }
-- ② 免疫步数设到很大（0xFF 以上，1 字节）
api.poke{ { addr = ADDR_IMMUNITY, width = 1, value = 0xFF, note = "免疫步数" } }

-- ③ 固定 RNG 后走满 20 格草丛：若两个开关都生效，应当一格都不遇敌
for i = 1, 20 do
    api.poke{ { addr = ADDR_RNG, width = 4, value = SEED + i, note = "钉 RNG" } }
    local ty = 7 + i
    api.walk("DOWN", 68, ty, 240, true, 20, "y")
    if i % 5 == 0 then
        api.shot(string.format("db_step%02d", i))
    end
end

api.burst("db_end", 6, 8)
return api.S
