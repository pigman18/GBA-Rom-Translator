-- ============================================================================
-- _probe_whiteout.lua — 用「全员濒死 → 白屏」触发真正的 WarpIntoMap
--
-- 【为什么这条路可行（源码依据 pret/pokeruby src/overworld.c）】
--   static void DoWhiteOut(void) {
--       RunScriptImmediately(EventScript_WhiteOut);
--       gSaveBlock1.money /= 2;
--       ScrSpecial_HealPlayerParty();
--       Overworld_ResetStateAfterWhiteOut();
--       Overworld_SetWarpDestToLastHealLoc();   ← 用 SaveBlock1.lastHealLocation
--       WarpIntoMap();                          ← 真正的 warp
--   }
--
--   ⇒ WarpIntoMap 全文件只有三处调用（白屏 / 传送术 / 秘密基地），
--     普通走门走 CB2_LoadMap，**不读 gWarpDestination** —— 这就是
--     前六轮所有"改内存传送"全失败的根本原因。
--   ⇒ 但白屏这条路**用的是 lastHealLocation**，它在 SaveBlock1+0x1C，
--     可以直接 poke！白屏后就会落到我们指定的地图。
--
-- 【怎么造白屏】
--   把队伍里所有宝可梦的当前 HP 写成 0，然后打一场（必败），
--   战斗结束即触发白屏。
--   队伍结构（本项目实测）：SB1+0x234 = partyCount，SB1+0x238 起每只 100 字节
--   等级在 +0x54，当前 HP 在 party 数据区。这里用绝对地址 gPlayerParty
--   (0x03004360，KEEP-US 可信) 更直接：每只 100 字节，HP 偏移需要探测。
--
-- ⚠ 本轮**只验证「能不能把 HP 清零并触发白屏」**，目标地图先设成
--   已知的 Route118(0:33)，这样白屏后如果 map 变成 0:33 就证明整条路通了。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

-- ① 把 lastHealLocation 设成 Route118 (0:33) pos(68,7)
--    SaveBlock1 内偏移（diff_sav_heads.py 实证过布局）：
--      +0x04 location / +0x0C continueGameWarp / +0x14 dynamicWarp / +0x1C lastHealLocation
api.poke{
    { sb1 = 0x1C, width = 1, value = 0x00, note = "lastHeal.g=0" },
    { sb1 = 0x1D, width = 1, value = 0x21, note = "lastHeal.n=33" },
    { sb1 = 0x1E, width = 1, value = 0xFF, note = "lastHeal.warpId=-1" },
    { sb1 = 0x20, width = 1, value = 68, note = "lastHeal.x=68" },
    { sb1 = 0x21, width = 1, value = 7, note = "lastHeal.y=7" },
}
api.wait(10)
api.shot("wo_target_set")

-- ② 输出当前状态（坐标/地图），确认还在商店里
api.shot("wo_before")

return api.S
