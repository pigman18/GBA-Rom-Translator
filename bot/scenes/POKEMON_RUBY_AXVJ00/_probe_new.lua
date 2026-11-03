-- ============================================================================
-- _probe_new.lua — 新动作自检（burst / poke）
--
-- 目的只有一个：证明 bot.lua 新加的两个 act 真的能跑，再拿去写正式场景。
--   ① poke：写 SaveBlock1 的坐标字段 → 读回确认 → 用 [POS] 日志验证游戏认账
--   ② burst：连续拍 6 张，确认落盘名是 <prefix>_01..06 且帧号严格递增
--
-- ⚠ 本场景会改坐标，**不产出对照**，只用 --no-prove 之外不需要额外开关；
--   跑法：python bot/run.py POKEMON_RUBY_AXVJ00 _probe_new --no-verify
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("overworld_before")

-- ① burst 基础验证：连拍 6 张
api.burst("b_six", 6, 1)

-- ② poke 基础验证：把坐标改成 (60, 7)，误差范围内游戏应立刻把角色挪过去
api.poke{
    { sb1 = 0x00, width = 2, value = 60, note = "pos.x" },
    { sb1 = 0x02, width = 2, value = 7,  note = "pos.y" },
}
api.wait(30)
api.shot("after_poke_x60")

-- ③ 再改回来，证明写的是实时内存而不是存档副本
api.poke{
    { sb1 = 0x00, width = 2, value = 68, note = "pos.x 还原" },
    { sb1 = 0x02, width = 2, value = 7,  note = "pos.y 还原" },
}
api.wait(30)
api.shot("after_poke_back")

-- ④ burst 带间隔：每 4 帧一张，验证 every 生效
api.burst("b_gap", 4, 4)

return api.S
