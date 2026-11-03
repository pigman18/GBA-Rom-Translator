-- ============================================================================
-- font_talk.lua — 对话态连拍（字库定位用）
--
-- 与 font_probe 相同的读档流程，但走 bot/run.py 的正式通道，
-- 每张 shot 都会产出 png + vram.bin + pal.bin + io.bin + ram.bin。
--
-- 目的：拿到「对话文字不断变化」的 VRAM 序列，离线 diff 出字模 tile 地址。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("overworld_before")

-- 触发对话（存档点在 118 号道路，主角身边有 NPC）
api.tap("A", 10, 60)
api.shot("talk_1")
api.tap("A", 8, 50)
api.shot("talk_2")
api.tap("A", 8, 50)
api.shot("talk_3")
api.tap("A", 8, 50)
api.shot("talk_4")
api.tap("A", 8, 50)
api.shot("talk_5")
api.tap("A", 8, 50)
api.shot("talk_6")

L.exit_to_overworld(api, 4, "closed")
return api.S
