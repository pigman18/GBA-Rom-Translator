-- ============================================================================
-- _probe_warp4.lua — 按权威源码改对地方：同时写 gWarpDestination 与 location
--
-- 【源码依据】pret/pokeruby src/overworld.c：
--     static void ApplyCurrentWarp(void) {
--         gLastUsedWarp = gSaveBlock1.location;
--         gSaveBlock1.location = gWarpDestination;   ← 关键：location 被覆盖
--         ...
--     }
--     struct WarpData { s8 mapGroup; s8 mapNum; s8 warpId; s8 x; s8 y; }  (8 字节，x/y 是 s8!)
--     void WarpIntoMap(void) { ApplyCurrentWarp(); LoadCurrentMapData(); SetPlayerCoordsFromWarp(); }
--
-- ⇒ 前两轮失败的原因找到了：
--   ① 只改 gSaveBlock1.location → ApplyCurrentWarp 用 gWarpDestination 覆盖它
--   ② 提前改 gWarpDestination → 门触发时 overworld 会自己 SetWarpData 写一遍
-- 所以必须**在门写完、WarpIntoMap 执行前**把 gWarpDestination 改成目标。
--
-- 【本探针做法】不用门。直接：
--   ① poke gWarpDestination = 目标图
--   ② 再走一步（任意移动都会让 overworld 走 LoadMapFromCameraTransition 之外的
--      正常路径；但更可靠的是**踩一个真实 warp 点**）
--   由于不能调函数，这里改成：poke 完之后**穿门**，并在穿门后的
--   **每一帧持续覆盖** gWarpDestination —— 抢窗口。
--
-- ⚠ 注意 WarpData 的 x/y 是 **s8**（不是 s16）！前两轮我按 s16 写，
--   x=68 被写成 44 00，只有低字节 0x44=68 生效是巧合，但结构是错的。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local G_WARP_DEST = 0x020297F8

L.preamble(api)
api.shot("w4_shop")                 -- map=10:7

-- 目标：Route118 = 0:33，坐标 (68,7)。x/y 是 s8，所以各写 1 字节。
-- 结构：+0 mapGroup, +1 mapNum, +2 warpId, +3 pad, +4 x(s8), +5 y(s8), +6..7 pad
api.poke{
    { addr = G_WARP_DEST + 0, width = 1, value = 0x00, note = "g=0" },
    { addr = G_WARP_DEST + 1, width = 1, value = 0x21, note = "n=33" },
    { addr = G_WARP_DEST + 2, width = 1, value = 0xFF, note = "warpId=-1" },
    { addr = G_WARP_DEST + 3, width = 1, value = 0x00, note = "pad" },
    { addr = G_WARP_DEST + 4, width = 1, value = 68, note = "x=68 (s8)" },
    { addr = G_WARP_DEST + 5, width = 1, value = 7, note = "y=7 (s8)" },
}
api.wait(10)
api.shot("w4_poked")

-- 穿门，随后**多轮**重新覆盖（每轮 poke 后会 settle，可能正好落在 warp 前）
for i = 1, 6 do
    api.tap("DOWN", 4, 4)
    api.poke{
        { addr = G_WARP_DEST + 0, width = 1, value = 0x00, note = "g=0" },
        { addr = G_WARP_DEST + 1, width = 1, value = 0x21, note = "n=33" },
        { addr = G_WARP_DEST + 4, width = 1, value = 68, note = "x=68" },
        { addr = G_WARP_DEST + 5, width = 1, value = 7, note = "y=7" },
    }
end
api.wait(60)
api.shot("w4_after")                -- ★ map 变 0:33 了吗
api.burst("w4_burst", 10, 10)

return api.S
