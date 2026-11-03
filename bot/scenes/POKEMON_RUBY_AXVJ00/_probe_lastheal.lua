-- ============================================================================
-- _probe_lastheal.lua — 验证 lastHealLocation 写入后能否保持（白屏方案的基石）
--
-- 【为什么这条路才是对的（源码依据，已查 pret/pokeruby overworld.c）】
--   static void DoWhiteOut(void) {
--       ...
--       Overworld_SetWarpDestToLastHealLoc();   /* 读 SaveBlock1.lastHealLocation */
--       WarpIntoMap();                          /* 真正的 warp */
--   }
--   void WarpIntoMap(void) { ApplyCurrentWarp(); LoadCurrentMapData(); SetPlayerCoordsFromWarp(); }
--     static void ApplyCurrentWarp(void) {
--         gSaveBlock1.location = gWarpDestination;   /* location 被覆盖 */
--     }
--   ⇒ WarpIntoMap 全文件只有三处调用：白屏 / 传送术 / 秘密基地。
--     普通走门走 CB2_LoadMap，**不读 gWarpDestination** ⇒ 前六轮改内存传送
--     全失败的根因。
--   ⇒ 但白屏这条路走 lastHealLocation，它在 SaveBlock1+0x1C，可以直接 poke。
--
-- 【偏移已实证】两份存档的 +0x1C 都是 `00 02 ff 00 16 00 06 00`
--   （mapGroup=0 mapNum=2 warpId=-1 x=22 y=6，即 Route118 附近的回复点）。
--
-- 本探针只验证「写进去 + 保住」，不真打仗（造白屏要另一步）。
--   写目标 = Route118 0:33 pos(68,7)
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("lh_before")

-- 写 lastHealLocation = Route118(0:33) pos(68,7)
api.poke{
    { sb1 = 0x1C, width = 1, value = 0x00, note = "g=0" },
    { sb1 = 0x1D, width = 1, value = 0x21, note = "n=33" },
    { sb1 = 0x1E, width = 1, value = 0xFF, note = "warpId=-1" },
    { sb1 = 0x1F, width = 1, value = 0x00, note = "pad" },
    { sb1 = 0x20, width = 1, value = 68, note = "x=68" },
    { sb1 = 0x21, width = 1, value = 7, note = "y=7" },
}
api.shot("lh_written")

-- 走几步让游戏跑一会儿，看值是否被覆盖
for i = 1, 6 do api.tap("DOWN", 4, 12) end
api.shot("lh_after_walk")

return api.S
