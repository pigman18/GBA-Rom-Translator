-- ============================================================================
-- _probe_obj_pos.lua — 验证「用 object 表坐标直接 warp 到 NPC 旁」是否可行
--
-- 【依据】scripts/list_objects.py 实测解出 object 结构：
--   0x03004800 + i*0x24，+0x04/+0x06 = 当前格坐标（s16）
--   道馆 map=3:3 帧里读到：
--     obj[0] (9,24)   obj[1] (8,17)   obj[2] (19,31)   obj[3] (12,31)
--   玩家当时在 (8,15) ⇒ obj[1] 距离玩家仅 2 格。
--
-- 本探针：直接 warp 到 obj[1] 旁边 (8,18)，面朝 UP 试 talk。
--   ⚠ 不能 warp 到 NPC 的格子上（会卡在 object 里），要落**相邻格**。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("op_start")

api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("op_outside")

-- 直接跳到 obj[1] (8,17) 的下方 (8,18)
api.warp{ map = "3:3", x = 8, y = 18, mon = 1 }
api.wait(60)
api.shot("op_at_npc")
api.burst("op_at_npc_f", 10, 6)

-- 面朝 UP 与 NPC 对话
api.tap("UP", 5, 25)
api.shot("op_facing")
api.talk{ timeout = 300 }
api.burst("op_dlg", 16, 6)
api.shot("op_dlg1")

for i = 1, 8 do
    api.tap("A", 5, 45)
    api.shot(string.format("op_dlg%d", i + 1))
end
api.shot("op_end")

return api.S
