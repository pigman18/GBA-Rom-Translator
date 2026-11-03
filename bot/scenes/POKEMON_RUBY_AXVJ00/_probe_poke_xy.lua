-- ============================================================================
-- _probe_poke_xy.lua — 最小验证：同图内 poke 坐标是否真能把角色挪过去
--
-- 只做三件事：
--   ① 出门
--   ② poke 到 (23,10)（街道北侧一点）→ 截图
--   ③ poke 到 (23,20)（街道南侧）→ 截图
-- 若两张图角色位置明显不同，说明金手指坐标跳转在城市里成立，
-- 之后就可以用它直接跳道馆/大赛会场，不必走位。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("px_shop")

api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("px_out")                 -- (23,17) map=0:2

api.poke{
    { sb1 = 0x00, width = 2, value = 23, note = "x=23" },
    { sb1 = 0x02, width = 2, value = 10, note = "y=10" },
}
api.wait(12)
api.shot("px_y10")

api.poke{
    { sb1 = 0x00, width = 2, value = 23, note = "x=23" },
    { sb1 = 0x02, width = 2, value = 20, note = "y=20" },
}
api.wait(12)
api.shot("px_y20")

api.poke{
    { sb1 = 0x00, width = 2, value = 10, note = "x=10" },
    { sb1 = 0x02, width = 2, value = 15, note = "y=15" },
}
api.wait(12)
api.shot("px_x10y15")

return api.S
