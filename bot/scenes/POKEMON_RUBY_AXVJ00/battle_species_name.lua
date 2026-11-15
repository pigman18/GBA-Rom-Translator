-- ============================================================================
-- battle_species_name.lua — 野生遇敌：种名（对话 + 血条）取证
--
-- 验收点（origin vs translated 看图）：
--   · 开场句「啊！野生的×××跳出来了！」种名完整中文，无「溶+」「落+」截断
--   · 敌方血条名完整，无乱码/半字/假名残片
--   · 推完台词后主菜单稳定一帧（对照种名仍在血条）
--
-- 确定性遇敌：与 battle_menu_audit 同构（hunt 逐步钉 RNG）。
-- 物种以 ram 为准：enemy @ 0x02024AD8（analyze 可复用）。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ADDR_RNG = 0x03004818
local FIXED_RNG = 0x0000AAAA

L.preamble(api)
api.shot("ov_overworld")

-- 与 battle_full 同构：prove 后先 poke 再 hunt（勿只靠 hunt.rng_*）
api.poke{ { addr = ADDR_RNG, width = 4, value = FIXED_RNG, note = "钉 RNG" } }
api.hunt{ dir = "DOWN", x = 68, y = 7, steps = 40, timeout = 120 }

api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1200, tag = "battle" }
api.burst("sp_transition", 12, 5)
api.shot("sp_in_battle")

-- 开场台词：密 burst，盯种名逐字出现与终态
for i = 1, 4 do
    api.burst(string.format("sp_intro_pre%d", i), 10, 4)
    api.shot(string.format("sp_intro_pre%d_s", i))
    api.tap("A", 4, 36)
    api.burst(string.format("sp_intro_post%d", i), 12, 4)
    api.shot(string.format("sp_intro_post%d_s", i))
end

-- 主菜单：血条名仍应完整
api.burst("sp_menu_settle", 10, 5)
api.shot("sp_menu")
api.shot("sp_enemy_name_box")  -- 同帧；审图时裁左上血条

return api.S
