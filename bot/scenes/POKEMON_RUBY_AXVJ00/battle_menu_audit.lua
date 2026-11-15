-- ============================================================================
-- battle_menu_audit.lua — 战斗主菜单 / 四招式 / PP+类型 取证（调研专用）
--
-- 相对 battle_full：
--   · 仍用「钉 RNG + hunt」确定性遇敌（两侧同宠；物种从 ram 复核）
--   · 遇敌后金手指再钉一次 RNG，减少转场后分岔
--   · 主菜单 / 招式列表关键帧全部 shot（带 dumps），burst 更密便于逐帧描述
--   · 四招式各 shot 一次（含 PP/类型面板），不做逃跑/队伍以免冲淡样本
--
-- 配合：BOT_DUMP_ALLWINS=1 + bot/analyze_battle_menu_frames.py
--       + run.py --gdb InitTextPrinter --gdb-side both
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ADDR_RNG = 0x03004818
local FIXED_RNG = 0x0000AAAA
-- 物种离线读：player 0x02024A80 / enemy 0x02024AD8（gBattleMons KEEP-US）

L.preamble(api)
api.shot("ov_overworld")

-- ── 确定性遇敌（hunt 内逐步钉 RNG）────────────────────────────────────────
-- 仅钉一次：同格遇敌仍可能野宠种不同（无 GDB 已复现拉电 vs 长翅鸥）。
-- hunt.rng_*：每走一格前写同一 gRngValue，把遇敌判定输入拉齐。
api.hunt{
    dir = "DOWN", x = 68, y = 7, steps = 40, timeout = 120,
    rng_addr = ADDR_RNG, rng_value = FIXED_RNG,
}

api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 900, tag = "battle" }
api.poke{ { addr = ADDR_RNG, width = 4, value = FIXED_RNG, note = "转场后重钉 RNG" } }
api.burst("bt_transition", 16, 6)
api.shot("bt_in_battle")

-- 开场台词推到主菜单（A×3）
for i = 1, 3 do
    api.tap("A", 4, 40)
    api.burst(string.format("bt_intro%d", i), 8, 6)
end
api.shot("bt_menu")
-- 敌我 species：勿 poke 覆盖。离线从 bt_menu*.ram.bin 读
--   player @ 0x02024A80、enemy @ 0x02024AD8（analyze_battle_menu_frames.py）

-- 主菜单四项：每格 shot + 短 burst
for i = 2, 4 do
    api.tap("RIGHT", 4, 24)
    api.shot(string.format("bt_menu_%d", i))
    api.burst(string.format("bt_menu_%d_b", i), 6, 4)
end
for _ = 1, 3 do api.tap("LEFT", 4, 24) end
api.shot("bt_menu_fight")

-- 招式列表：进菜单后立刻全量 dump，再逐格四招式
api.tap("A", 4, 70)
api.burst("bt_moves_enter", 14, 5)
api.shot("bt_move_1")
for i = 2, 4 do
    api.tap("DOWN", 4, 28)
    api.shot(string.format("bt_move_%d", i))
    api.burst(string.format("bt_move_%d_b", i), 6, 4)
end
for _ = 1, 3 do api.tap("UP", 4, 16) end
api.shot("bt_move_back")

-- 回到主菜单再拍一次（背包/逃跑列对照）
api.tap("B", 4, 40)
api.shot("bt_menu_again")
api.tap("RIGHT", 4, 24)
api.shot("bt_menu_bag")
api.tap("DOWN", 4, 24)
api.shot("bt_menu_run")

return api.S
