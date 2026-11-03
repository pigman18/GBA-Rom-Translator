-- ============================================================================
-- _probe_obj_pos3.lua — 按坐标系修正：NPC 在 (8,17)，落到 (8,18) 要朝 DOWN
--
-- 【依据】scripts/obj_delta.py 实测（两个不同帧对照）：
--   gym_dewford 的 object 坐标在两帧里**完全相同**：
--     (8,17) (9,24) (12,31) (19,31)
--   ⇒ 它们是固定 NPC，且与 SaveBlock1.pos **同一坐标系**（不需要偏移）。
--   玩家当时 (8,15) ⇒ NPC (8,17) 在其下方 2 格。
--
-- 【上一轮为什么失败】
--   warp 到 (8,18) 后 NPC 在**上方**一格，而我朝 UP 试 talk —— 看起来对，
--   但 talk 超时。截图显示 NPC 实际在主角**下方**，说明 (8,18) 那格
--   屏幕上的相对位置与预期相反 ⇒ 该格可能不是我以为的 (8,18)，
--   或者 (8,17) 这个 object 不是可对话 NPC（可能是门/告示牌）。
--
-- 【本轮做法】不猜方向：落在 (8,18) 后，**4 方向各试一次 talk(soft)**，
--   并逐格向 DOWN 推进 3 格，每格都试。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("o3_start")

api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("o3_outside")

api.warp{ map = "3:3", x = 8, y = 18, mon = 1 }
api.wait(60)
api.shot("o3_arrive")
api.burst("o3_arrive_f", 8, 6)

local dirs = { "DOWN", "UP", "LEFT", "RIGHT" }
for step = 1, 4 do
    for _, d in ipairs(dirs) do
        api.tap(d, 5, 18)
        api.talk{ timeout = 100, soft = true }
        api.shot(string.format("o3_s%d_%s", step, d))
        api.burst(string.format("o3_s%d_%s_f", step, d), 5, 5)
        for i = 1, 2 do api.tap("A", 5, 30) end
        api.tap("B", 4, 22)
    end
    api.roam{ seq = { "DOWN" }, steps = 1 }
    api.shot(string.format("o3_step%d", step))
end

api.shot("o3_end")
return api.S
