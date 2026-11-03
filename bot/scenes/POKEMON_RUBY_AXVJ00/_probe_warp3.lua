-- ============================================================================
-- _probe_warp3.lua — 抢「门已触发、warp 尚未执行」的窗口改写目的地
--
-- 前两轮实测（都是负面结果，但把机制说清了）：
--   ① 改 SaveBlock1.location → 一穿门就变 0:2（门自带固定目标，覆盖 location）
--   ② 提前改 gWarpDestination(0x020297F8) → 穿门时被游戏整个重写
--      实测 002 帧确实是我写的 00 21 ff 00 44 00 07 00，
--      到 003 帧变成 0e 04 0e 04...（warp 流程把它覆盖了）
--
-- ⇒ 机制明确：**门在触发时会自己写 gWarpDestination**，
--   所以必须抢「门已写、warp 未执行」这一小段窗口才能改。
--
-- 本轮做法：按住 DOWN 穿门，**每 2 帧**就把 gWarpDestination 改成目标图，
--   连续覆盖一段时间。只要有一帧落在窗口里，落地就会变。
--   目标用 Route118 (0:33) —— 它是已知能正常加载的地图（不会白屏），
--   这样"变没变"一眼可辨。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local G_WARP_DEST = 0x020297F8

L.preamble(api)
api.shot("w3_shop")                 -- map=10:7

-- 连续：poke 目的地 → 走一小步 → 再 poke → ...
-- 目的是在穿门的过程中持续把目的地钉在 0:33
for i = 1, 10 do
    api.poke{
        { addr = G_WARP_DEST + 0, width = 1, value = 0x00, note = "g=0" },
        { addr = G_WARP_DEST + 1, width = 1, value = 0x21, note = "n=33" },
        { addr = G_WARP_DEST + 2, width = 1, value = 0xFF, note = "warpId=-1" },
        { addr = G_WARP_DEST + 4, width = 2, value = 68, note = "x=68" },
        { addr = G_WARP_DEST + 6, width = 2, value = 7, note = "y=7" },
    }
    api.tap("DOWN", 3, 2)           -- 极短间隔，尽量贴近门触发
end
api.wait(80)
api.shot("w3_after")                -- ★ map 变了吗
api.burst("w3_burst", 8, 10)

return api.S
