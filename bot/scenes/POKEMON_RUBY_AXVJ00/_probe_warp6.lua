-- ============================================================================
-- _probe_warp6.lua — 按用户给的 GameShark warp 码地址原样测试
--
-- 用户提供（来自其他 AI，待验证）：
--   瞬移码 02031F84:XXXX  （16 位写入）
--     天元市 = 0008     道吉镇 = 0002     卡那市 = 0100
--     南方孤岛 = 0A1A   狩猎区 = 0017     冠军之路 = 3811
--   备用地址 020322E4:XXXX
--   用法关键：**开码 → 进一扇门/山洞 → 出来就在目标地点**
--
-- 我之前查过 0x02031F84 读到 0000，但**没有写入后再穿门试**。
-- 本探针按原样做：
--   ① 写 02031F84 = 0008（天元市，即 Petalburg City）
--   ② 走商店门出去
--   ③ 看落地 map 是不是天元市
--   若不行，用备用地址 020322E4 再来一遍。
--
-- ⚠ 这个码是 16 位写入（width=2），和 WarpData(s8) 不是一回事 ——
--   说明它指向的不是 struct WarpData，而是别的（历史版本的内存布局）。
--   日版布局可能与美版不同，所以两个地址都试。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local A1 = 0x02031F84     -- 首选
local A2 = 0x020322E4     -- 备用

L.preamble(api)
api.shot("w6_shop")                 -- map=10:7 (3,7)

-- ① 写首选地址 = 0x0008（天元市）
api.poke{ { addr = A1, width = 2, value = 0x0008, note = "02031F84=0008 天元市" } }
api.wait(10)
api.shot("w6_set")

-- ② 穿门
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.wait(80)
api.shot("w6_after_door")           -- ★ 落地是哪里？

-- ③ 若没到天元市，试备用地址再来一遍（先回商店不可能了，直接在城外设）
api.poke{ { addr = A2, width = 2, value = 0x0008, note = "020322E4=0008 天元市" } }
api.wait(10)
api.shot("w6_set2")

-- 找一扇门再进：往左走找建筑门
api.roam{ seq = { "LEFT", "LEFT", "LEFT", "UP", "UP" }, steps = 6 }
api.tap("A", 6, 60)
api.wait(60)
api.burst("w6_try2", 12, 10)
api.shot("w6_after2")

return api.S
