-- ============================================================================
-- _probe_battle2.lua — 稳定拿到「战斗主菜单」并连帧采集
--
-- 上一轮实测：草丛走 6 步就触发遇敌（DISPCNT 7F60 → BF40），战斗确实能进。
-- 问题只是遇敌后没等它就绪，后面全在转场里乱按。
--
-- 本轮做法：
--   ① 进草丛直到 DISPCNT 变成战斗值（用 await 硬等，不靠帧数）
--   ② 战斗开场按 A 推过「野生的 X 跳出来了」→ 战斗主菜单
--   ③ 主菜单四项逐个连帧采集（这四项是 PCS 文本，§7.2 的 E 类窗口）
--   ④ 进「招式」看招式名 + PP（D 类窗口）
--   ⑤ 逃跑收尾
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("b2_overworld")

-- ① 走进下方草丛（Route118 起点 68,7；实测草丛在 y>=10）
--    ⚠ 上一轮踩的坑：写成 walk("RIGHT", 67, ...) 方向与目标反了，
--      结果 5 帧就「到位」（其实原地没动），一路没进草丛、也没遇敌。
--      这里改成**一格一格真实移动**：先向下 10 格，再在草丛里上下往返。
api.walk("DOWN", 68, 17, 600, true)
api.shot("b2_grass")

-- ② 草丛里上下往返走（每格都是真实移动，才会累计遇敌判定）
--    ⚠ 一旦遇敌，角色坐标就被战斗系统接管，walk 必然超时 —— 用 soft 继续。
for i = 1, 18 do
    local ty = (i % 2 == 1) and 18 or 16
    api.walk("DOWN", 68, ty, 200, true, 20, "y")
end

-- ③ 等战斗界面：黑屏转场(0x0000) 或 战斗画面(0xBF40) 任一命中
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 900, tag = "battle" }
api.burst("b2_transition", 12, 6)

-- ③ 推过开场台词，进战斗主菜单
api.tap("A", 6, 40)
api.burst("b2_intro", 10, 8)
api.tap("A", 6, 40)
api.shot("b2_menu")            -- ★ 战斗主菜单四项（たたかう/バッグ/ポケモン/にげる）

-- ④ 主菜单四项逐个连帧
for i = 2, 4 do
    api.tap("DOWN", 4, 20)
    api.burst(string.format("b2_menu_%d", i), 4, 6)
end

-- ⑤ 回第 1 项进招式（招式名 + PP）
for _ = 1, 3 do api.tap("UP", 4, 12) end
api.tap("A", 6, 50)
api.burst("b2_moves", 8, 6)

return api.S
