-- ============================================================================
-- _probe_warpcheat.lua — 验证「金手指改 warp 目的地，出门直接到别的地图」
--
-- 用户口径（2026-11-03）：「我印象中是可以注入金手指，出商店门直接就去到
--   别的地方的」。
--
-- 我前面的测试**只测了改 pos（坐标）**，没测「改 location 再走门」。
-- 这两件事在 Gen3 里是不同的机制，不能混为一谈。本探针专门测后者。
--
-- 做法：
--   ① 读档落在商店 map=10:7
--   ② poke SaveBlock1.location（+0x04 mapGroup / +0x05 mapNum /
--      +0x06 warpId / +0x08 x / +0x0A y）改成 Route118 = 0:33
--   ③ 走回商店门口的 warp，走出去
--   ④ 看落地地图是不是变成了 0:33（日志 [POS] 直接打 map=g:n）
--
-- 若 ④ 是 0:33 ⇒ 用户记忆正确，以后跳场景就用这条：
--   先 poke 目的地，再随便踩一个门/洞口触发 warp。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("wc_shop")                 -- 应在 map=10:7

-- ② 把 location 改成 Route118 = mapGroup 0 / mapNum 33
--    WarpData 8 字节：+0x04 g, +0x05 n, +0x06 warpId, +0x07 pad,
--                     +0x08 x(s16), +0x0A y(s16)
api.poke{
    { sb1 = 0x04, width = 1, value = 0x00, note = "location.mapGroup=0" },
    { sb1 = 0x05, width = 1, value = 0x21, note = "location.mapNum=33" },
    { sb1 = 0x06, width = 1, value = 0xFF, note = "location.warpId=-1" },
    { sb1 = 0x08, width = 2, value = 0xFFFF, note = "location.x=-1" },
    { sb1 = 0x0A, width = 2, value = 0xFFFF, note = "location.y=-1" },
}
api.wait(20)
api.shot("wc_poked")                -- 值应已写入（画面还没变）

-- ③ 走到门口并穿门（商店门在下方，实测 DOWN 能穿出）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.wait(60)
api.shot("wc_after_door")           -- ★ 关键：这里 map 是 0:33 还是 0:2？

-- 再多走几步确认稳定
api.roam{ seq = { "DOWN" }, steps = 4 }
api.burst("wc_after_burst", 10, 10)
api.shot("wc_final")

return api.S
