-- ============================================================================
-- _probe_warp.lua — 验证「离线改 .sav 落点」是否真的能把游戏推进目标地图
--
-- 用途：换地图是覆盖室内/商店/大赛等场景的唯一可靠手段（金手指改
--       mapGroup/mapNum 不会让游戏重新加载地图，画面不动）。
-- 本场景只做一件事：读档 → 截图 → 报告 [POS] / [PROVE] 里的地图与坐标。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.wait(120)
api.shot("warp_check")
api.burst("warp_burst", 6, 6)

return api.S
