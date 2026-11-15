-- ============================================================================
-- battle_already_out.lua — 战斗中对「已在场」宝可梦再派出
--
-- 用户路径：遇敌 → 主菜单「宝可梦」→ 选当前场上那只 →「いれかえる」
-- 现象：先空白框，再「已经在战斗中出场了！」换行把「了！」挤出/超框
--
-- ⚠ 主菜单是 2×2：战斗/背包 ；宝可梦/逃跑。必须先确认在「战斗」再 DOWN。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ADDR_RNG = 0x03004818
local FIXED_RNG = 0x0000AAAA

L.preamble(api)
api.shot("ov_overworld")

api.poke{ { addr = ADDR_RNG, width = 4, value = FIXED_RNG, note = "钉 RNG" } }
api.hunt{ dir = "DOWN", x = 68, y = 7, steps = 40, timeout = 120 }

api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1200, tag = "battle" }
api.burst("ao_transition", 10, 5)

for i = 1, 3 do
    api.tap("A", 4, 40)
    api.burst(string.format("ao_intro%d", i), 6, 5)
end
api.shot("ao_menu")

-- 归一：左上「战斗」（防 intro 后光标漂到别格）
api.tap("LEFT", 4, 16)
api.tap("UP", 4, 16)
api.shot("ao_menu_fight")

-- DOWN → 「宝可梦」
api.tap("DOWN", 4, 28)
api.shot("ao_on_pokemon")
api.tap("A", 4, 80)
api.burst("ao_party_enter", 16, 5)
api.shot("ao_party")

-- A → 子菜单；再 A →「いれかえる」→ 已在场提示
api.shot("ao_before_select")
api.tap("A", 4, 55)
api.burst("ao_submenu", 10, 4)
api.shot("ao_submenu_s")
api.tap("A", 4, 14)
api.burst("ao_msg_blankish", 28, 3)
api.shot("ao_msg_1")
api.burst("ao_msg_print", 20, 4)
api.shot("ao_msg_2")
api.burst("ao_msg_done", 14, 5)
api.shot("ao_msg_final")

-- 关提示回队伍再试一次
api.tap("A", 4, 40)
api.tap("B", 4, 45)
api.burst("ao_party_again_f", 8, 5)
api.shot("ao_party_again")
api.tap("A", 4, 50)
api.shot("ao_retry_submenu")
api.tap("A", 4, 12)
api.burst("ao_retry_msg", 28, 3)
api.shot("ao_retry_final")

return api.S
