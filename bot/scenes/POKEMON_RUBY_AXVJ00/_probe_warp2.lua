-- ============================================================================
-- _probe_warp2.lua — 测「gWarpDestination」这条经典 warp 码路线
--
-- 上一轮结论（已实测）：
--   poke SaveBlock1.location 改目的地 → 值写进去了（wc_poked map=0:33），
--   但一穿门就变成 0:2 —— 因为**商店门自己带固定 warp 目标**，会把
--   location 覆盖掉。所以改 location 无效。
--
-- 本轮改测真正的「待执行 warp」：
--   gWarpDestination @0x020297F8 (KEEP-US，符号可信) 8 字节 WarpData：
--     +0 g, +1 n, +2 warpId, +3 pad, +4 x(s16), +6 y(s16)
--   这是 WarpIntoMap / ApplyCurrentWarp 读的结构。
--
-- 做法：poke 这个结构，然后走商店门（触发 warp 流程），看落地是否变成目标图。
-- 目标先设 Route118 (0:33)。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local G_WARP_DEST = 0x020297F8

L.preamble(api)
api.shot("w2_shop")                 -- map=10:7

-- 把「待执行 warp」设成 Route118 (0:33)
api.poke{
    { addr = G_WARP_DEST + 0, width = 1, value = 0x00, note = "warp.g=0" },
    { addr = G_WARP_DEST + 1, width = 1, value = 0x21, note = "warp.n=33" },
    { addr = G_WARP_DEST + 2, width = 1, value = 0xFF, note = "warp.warpId=-1" },
    { addr = G_WARP_DEST + 3, width = 1, value = 0x00, note = "warp.pad" },
    { addr = G_WARP_DEST + 4, width = 2, value = 68, note = "warp.x=68" },
    { addr = G_WARP_DEST + 6, width = 2, value = 7, note = "warp.y=7" },
}
api.wait(20)
api.shot("w2_poked")

-- 走门触发 warp
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.wait(80)
api.shot("w2_after_door")           -- ★ 关键：map 变成 0:33 了吗？

api.roam{ seq = { "DOWN" }, steps = 3 }
api.burst("w2_burst", 10, 10)
api.shot("w2_final")

return api.S
