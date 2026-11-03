-- ============================================================================
-- _probe_talk.lua — 探针：四个方向各按一次 A，看哪一面有 NPC 可对话
--
-- 为什么需要：室内地图（商店）里 NPC 站位肉眼难判（斜对角看起来像正对），
--   与其靠截图数格子，不如让 bot 把四个方向都试一遍，用 [TALK] 日志直接
--   告出「哪一面文本真的推进了」。跑完看 scene.log 的 [TALK] hit 行即可。
--
-- ⚠ 这是诊断场景，不进验收：它**故意**包含打空的 A。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("p0_start")

for _, d in ipairs({ "RIGHT", "DOWN", "UP", "LEFT" }) do
    api.tap(d, 6, 40)                            -- 只转身（6 帧不够走一格）
    api.talk{ timeout = 200, soft = true }
    api.wait(40)
    api.shot("try_" .. d)
    api.tap("B", 4, 40)
    api.tap("B", 4, 40)
end
api.shot("p9_end")

return api.S
