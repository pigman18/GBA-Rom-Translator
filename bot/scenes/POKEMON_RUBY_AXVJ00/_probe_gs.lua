-- ============================================================================
-- _probe_gs.lua — 最小验证：GameShark warp 码地址写入后能否存活
--
-- 只做一件事：
--   ① 读 0x02031F84 / 0x020322E4 的原值
--   ② 写入 0x0008
--   ③ 立刻读回（验证 poke 生效）
--   ④ 走几步，再读回（验证游戏是否把它覆盖掉）
--
-- 为什么要先做这一步：如果地址在日版是「没被任何代码读写」的空区，
-- 写了也会立刻被游戏覆盖，穿门自然无效 —— 那就是地址不对，
-- 直接换下一个，不必每轮都跑完整穿门流程（一轮好几分钟）。
--
-- 备注：bot 的 poke 会自动打 old->new，并复核读回值。
--       这里额外用 shot 让日志记录当前 POS/map。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("gs_shop")

-- ① 写首选地址
api.poke{ { addr = 0x02031F84, width = 2, value = 0x0008, note = "A1=0008" } }
api.shot("gs_a1_written")

-- ② 走几步（不穿门，只让游戏跑一会儿再看值还在不在）
for i = 1, 4 do
    api.tap("DOWN", 4, 10)
end
api.shot("gs_a1_after_walk")

-- ③ 写备用地址
api.poke{ { addr = 0x020322E4, width = 2, value = 0x0008, note = "A2=0008" } }
api.shot("gs_a2_written")

for i = 1, 4 do
    api.tap("DOWN", 4, 10)
end
api.shot("gs_a2_after_walk")

-- ④ 真穿门
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.wait(60)
api.shot("gs_after_door")
api.burst("gs_burst", 8, 10)

return api.S
