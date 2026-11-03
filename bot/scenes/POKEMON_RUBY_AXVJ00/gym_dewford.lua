-- ============================================================================
-- gym_dewford.lua — Dewford 道馆（map=3:3，格斗系）
--
-- 【为什么之前采不到】（已解，2026-11-03）
--   这张图是**溜冰迷宫**：盲走到 (2,7) 后左侧是虚空，NPC 在墙的另一侧，
--   逐格四方向试 A 共 40+ 次全部超时（123 帧里仅 1 帧有窗口）。
--
-- 【解法】读 ObjectEventTemplate 拿到「带 script 的可交互对象」坐标，
--   直接 warp 到它旁边。日版布局是实测反推出来的：
--     SaveBlock1 + 0x0C0C 起，每项 0x18：
--       +0x00 s16 x   +0x02 s16 y   +0x0C u32 script
--   （与 pokeruby 的 /*0xC20*/ 差 0x14，字段顺序也不同 —— 日版就是不一样）
--   本图实测 5 个可交互对象：
--     [1](14,4) [2](2,17) [3](1,10) [4](12,24) [5](5,24)
--   脚本校验：读 ROM 得到 `0f 00 ... 09 02`（loadword+callstd+end），
--   是真脚本，不是随机数据。
--
-- 【本场景】落到最近的 [2](2,17) 下方 (2,18)，朝 UP 对话。
--   ⚠ 一个场景只 warp 一次，其余对象留给后续单独场景。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("gd_start")

-- 出门到城市（warp 需要先能自由行动）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("gd_outside")

-- 直接跳到目标 NPC [2](2,17) 的下方
api.warp{ map = "3:3", x = 2, y = 18, mon = 1 }
api.wait(60)
api.shot("gd_at_npc")
api.burst("gd_enter_f", 12, 8)

-- 朝 UP 对话（闸门：打空会当场失败）
api.tap("UP", 5, 25)
api.shot("gd_facing")
api.talk{ timeout = 300 }
api.burst("gd_dlg_open", 16, 6)
api.shot("gd_dlg1")

-- 逐句推进
for i = 1, 10 do
    api.tap("A", 5, 45)
    api.burst(string.format("gd_dlg%d_f", i + 1), 6, 6)
    api.shot(string.format("gd_dlg%d", i + 1))
end

-- 若触发战斗，把战斗界面也采一段
api.burst("gd_after_dlg", 10, 8)
api.shot("gd_end")
return api.S
