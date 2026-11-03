-- ============================================================================
-- contest_lilycove.lua — Lilycove 华丽大赛会场（map=13:5）
--
-- 【为什么之前采不到】（已解，2026-11-03）
--   盲走到 (12,4) 也没开出对话（103 帧仅 1 帧有窗口）。
--   放大截图后才看清：会场里那两个"人形"其实是**盆栽装饰**，
--   右上角深色物是家具 —— 真正可对话的对象不在那儿。
--
-- 【解法】读 ObjectEventTemplate 拿坐标（日版布局实测反推）：
--     SaveBlock1 + 0x0C0C 起，每项 0x18：
--       +0x00 s16 x   +0x02 s16 y   +0x0C u32 script
--   本图实测 **32 个**可交互对象，最近的是 [2](11,7)。
--   （会场很大，对象分布在 (8..40, 7..30) 的网格上）
--
-- 【本场景】落到 [2](11,7) 下方 (11,8)，朝 UP 对话；
--   再依次去最近的几个（同一次 warp 内靠走位，不再二次 warp）。
--   ⚠ 一个场景只 warp 一次（连续第二次 TIMEOUT，实测）。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("cl_start")

-- 出门到城市（warp 需要先能自由行动）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("cl_outside")

-- 直接跳到最近的 NPC [2](11,7) 下方
api.warp{ map = "13:5", x = 11, y = 8, mon = 1 }
api.wait(60)
api.shot("cl_at_npc")
api.burst("cl_enter_f", 12, 8)

local dirs = { "UP", "LEFT", "RIGHT", "DOWN" }

-- 在落点四方向试 talk（NPC 朝向未知）
for _, d in ipairs(dirs) do
    api.tap(d, 5, 20)
    api.talk{ timeout = 150, soft = true }
    api.burst(string.format("cl_dlg_%s_f", d), 10, 5)
    api.shot(string.format("cl_dlg_%s", d))
    for i = 1, 3 do
        api.tap("A", 5, 40)
        api.shot(string.format("cl_dlg_%s_%d", d, i))
    end
    api.tap("B", 4, 28)
end

-- 会场很大：再走几格覆盖其他对象（不改落点，只走位）
api.roam{ seq = { "LEFT", "LEFT", "DOWN", "DOWN" }, steps = 3 }
api.shot("cl_moved")
for _, d in ipairs(dirs) do
    api.tap(d, 5, 20)
    api.tap("A", 6, 45)
    api.shot(string.format("cl2_%s", d))
    api.burst(string.format("cl2_%s_f", d), 6, 5)
    api.tap("B", 4, 25)
end

-- 再往右扫一段
api.roam{ seq = { "RIGHT", "RIGHT", "RIGHT", "RIGHT" }, steps = 3 }
api.shot("cl_right")
for _, d in ipairs(dirs) do
    api.tap(d, 5, 20)
    api.tap("A", 6, 45)
    api.shot(string.format("cl3_%s", d))
    api.tap("B", 4, 25)
end

api.shot("cl_end")
return api.S
