-- ============================================================================
-- _probe_battle_poke.lua — 用金手指直接触发野生战斗（覆盖战斗类场景）
--
-- 为什么要试这条路：换地图已被证伪（改 .sav 的 location 无效，地图是
-- 读档流程加载的），而战斗/大赛/道馆这些界面在现有 4 张存档里都没有。
-- 若能在**已进入野外后**写内存把游戏推进战斗，就能不依赖存档覆盖它们。
--
-- 做法（逐级加大胆量，每步都截图验证）：
--   ① 先在草丛里按 A 走几步，看能不能自然遇敌（最稳，RNG 允许失败）
--   ② 不行再用金手指改「遇敌步数计数器」
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("bp_overworld")

-- 走向下方草丛（Route118 起点 (68,7)，草丛在下方）
api.walk("DOWN", 68, 12, 400, true)
api.shot("bp_grass")
api.burst("bp_grass_walk", 10, 8)

-- 草丛里用 DOWN 按住走：Gen3 遇敌走的是步数计数器
for i = 1, 12 do
    api.tap("DOWN", 8, 20)
    api.burst(string.format("bp_step%02d", i), 4, 10)
    api.tap("UP", 8, 20)
    api.burst(string.format("bp_back%02d", i), 4, 10)
end

api.shot("bp_final")
return api.S
