-- ============================================================================
-- _probe_warp_action.lua — 验证 bot 新增的 warp 动作（封装版）
--
-- 前置：用 warp_tool.py 植入过传送术的存档（work/_probe/teleport.sav）
--
-- 本场景验证三件事：
--   ① warp 动作能在城市里直接跳到 Route119 (0:34)
--   ② 落点坐标是否精确
--   ③ 再跳一次到别的坐标，确认可重复
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("wa_start")                -- 商店内 10:7

-- ① 出门到城市（warp 需要先在可自由行动的地方）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("wa_outside")              -- 0:2

-- ② 跳到 Route118
api.warp{ map = "0:33", x = 68, y = 7, mon = 1 }
api.wait(60)
api.shot("wa_route118")
api.burst("wa_a", 10, 8)

-- ③ 再跳到 Route119（另一张图，证明可复用）
api.warp{ map = "0:34", x = 8, y = 100, mon = 1 }
api.wait(60)
api.shot("wa_route119")
api.burst("wa_b", 10, 8)

return api.S
