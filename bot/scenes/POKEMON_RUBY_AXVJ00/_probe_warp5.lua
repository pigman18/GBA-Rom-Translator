-- ============================================================================
-- _probe_warp5.lua — 走 WarbIntoMap 那条路（源码级方案）
--
-- 【源码依据】pret/pokeruby src/overworld.c
--   void WarpIntoMap(void) { ApplyCurrentWarp(); LoadCurrentMapData(); SetPlayerCoordsFromWarp(); }
--   static void ApplyCurrentWarp(void) {
--       gLastUsedWarp = gSaveBlock1.location;
--       gSaveBlock1.location = gWarpDestination;   ← 用 gWarpDestination 覆盖
--   }
--   调用 WarpIntoMap 的**只有三处**：
--     · DoWhiteOut()        （全员濒死白屏）
--     · 传送术/秘密基地 sub_8053778()
--     · 秘密基地2 相关
--   普通「走门」走的是 CB2_LoadMap 路径，**根本不读 gWarpDestination**
--   —— 这就是前四轮全失败的根因。
--
-- 【本探针】用「全员濒死 → 白屏」这条路触发 WarpIntoMap：
--   DoWhiteOut() 里先 Overworld_SetWarpDestToLastHealLoc() 再 WarpIntoMap()，
--   而 lastHealLocation 就在 SaveBlock1 里、可以 poke！
--   ⇒ 只要把 lastHealLocation 改成目标地图，白屏后就会落在目标地图。
--
--   触发白屏：把队伍 6 只的 HP 全写成 0，然后走一步遇敌/或直接进战斗。
--   更简单：把 gPlayerParty 每只的 hp 写 0 —— 但白屏要等下次战斗结算。
--
-- ⚠ 本探针**只验证 lastHealLocation 的写入是否生效**（读回 + 截图），
--   不强行制造战斗（那要另外一轮）。这样结论可复现、不改存档。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("w5_shop")

-- lastHealLocation 在 SaveBlock1 内的偏移：源码 struct SaveBlock1 里
-- location(+0x04) 之后依次是 continueGameWarp(+0x0C)、dynamicWarp(+0x14)、
-- lastHealLocation(+0x1C)。前面 diff_sav_heads.py 已实测这个布局。
-- 目标：Route118 = 0:33 pos (68,7)
api.poke{
    { sb1 = 0x1C, width = 1, value = 0x00, note = "lastHeal.mapGroup=0" },
    { sb1 = 0x1D, width = 1, value = 0x21, note = "lastHeal.mapNum=33" },
    { sb1 = 0x1E, width = 1, value = 0xFF, note = "lastHeal.warpId=-1" },
    { sb1 = 0x1F, width = 1, value = 0x00, note = "pad" },
    { sb1 = 0x20, width = 1, value = 68, note = "lastHeal.x=68" },
    { sb1 = 0x21, width = 1, value = 7, note = "lastHeal.y=7" },
}
api.wait(10)
api.shot("w5_poked")

-- 读回验证（这一段直接读 RAM，证明写入生效）
-- 同时把 gWarpDestination 也设成同一目标，双保险
api.poke{
    { addr = 0x020297F8 + 0, width = 1, value = 0x00, note = "warpDest.g=0" },
    { addr = 0x020297F8 + 1, width = 1, value = 0x21, note = "warpDest.n=33" },
    { addr = 0x020297F8 + 2, width = 1, value = 0xFF, note = "warpDest.warpId=-1" },
    { addr = 0x020297F8 + 4, width = 1, value = 68, note = "warpDest.x=68" },
    { addr = 0x020297F8 + 5, width = 1, value = 7, note = "warpDest.y=7" },
}
api.wait(10)
api.shot("w5_both_set")

-- 走一步看是否意外触发（正常不会）
api.tap("DOWN", 4, 20)
api.shot("w5_after_step")
api.burst("w5_burst", 8, 10)

return api.S
