-- ============================================================================
-- battle.lua — 野生宝可梦遭遇战  ★★ fontNum=4 / Small 字体的主战场
--
-- 【为什么必须做这个场景】
--   用户口径点名：「fontNum=4 场景使用 Small 字体，渲染 8×8px，主要用在
--   **队伍名称显示**、**战斗宝可梦名显示**等」。
--   队伍名已在 pokemon_menu 采集；**战斗宝可梦名**只能在这里拿到。
--   战斗界面是 Small 字体最密集的一屏：
--     · 我方宝可梦名 + 等级（左下状态框）  · 敌方宝可梦名 + 等级（左上状态框）
--     · HP 数值 "17/17"                    · 招式名 + PP "15/15"
--
-- ════════════════════════════════════════════════════════════════════════════
-- 【★ 移动场景的对齐难题 —— 本文件的核心设计】
--   实测教训（2026-10-17）：两侧从同一存档、同一帧号出发，盲走 4 步之后
--   画面相似度从 **1.000 掉到 0.063**。原因：走路是逐帧累积的，
--   origin 与 translated 的 ROM 不同（hook 改动），按键响应时序差一帧，
--   角色就走到**不同的格子**。`await` 只判「界面变了」，判不了「站在哪一格」。
--
--   正确解法 = **walk(dir, gx, gy)**：等待期间持续按住方向键，直到运行时
--   SaveBlock1 的 `pos` 等于目标格中心。两侧即使帧号漂移，也必然停在同一格。
--     · 坐标来源：SaveBlock1 = SaveBlock2 + 0x890（符号表实证）
--     · pos 是**像素**坐标：第 (gx,gy) 格 → (gx*16+8, gy*16+8)
--       （踩坑记录：一开始拿格子号直接比，永远不相等，卡了 71 万帧）
--     · 起始位置（存档实测）：Route118 野外 (68,7)，草丛在**下方**
-- ════════════════════════════════════════════════════════════════════════════
--
-- ⚠ 遇敌是**随机**的（Route118 每步约 10%）。预定的走动走完仍未遭遇时，
--   场景正常结束，由 verify 把野外帧标成 suspect —— **绝不伪造战斗画面**。
-- ⚠ soft=true：遭遇后角色坐标会被战斗系统接管，walk 必然超时；
--   此时只记警告并继续，而不是让整个场景崩掉。
-- ⚠⚠ 绝不用即时存档（用户契约第 4 条）；全程只用 .sav 读档。
-- ============================================================================

local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local api = L.new()

L.preamble(api)                    -- 含 prove（walk 依赖它定位 SB2）
api.shot("overworld")              -- (68,7) 起点，两侧必须逐像素相同

local X, Y = 68, 7

-- ── 逐格向下走进草丛（每格对齐）──────────────────────────────────────────
for step = 1, 8 do
    api.walk("DOWN", X, Y + step, 300, true)
    if step % 4 == 0 then
        api.shot(string.format("walk_y%d", Y + step))
    end
end

-- ── 草丛深处左右来回，增加遭遇机会 ────────────────────────────────────────
for step = 1, 10 do
    local xx = X + ((step % 2 == 0) and 1 or -1)
    api.walk("RIGHT", xx, Y + 8, 260, true)
    api.walk("LEFT", X, Y + 8, 260, true)
end

-- ── 战斗采集 ───────────────────────────────────────────────────────────────
api.wait(90)
api.shot("battle_intro")           -- ★ 敌方宝可梦名 + 等级（Small 字体）
api.wait(45)
api.shot("battle_intro_b")

api.wait(60)
api.shot("battle_menu")            -- ★ 战斗菜单 4 项

api.tap("A", 4, 60)
api.shot("move_list")              -- ★ 招式名 + PP（Small 字体）
api.tap("DOWN", 4, 30)
api.shot("move_2")
api.tap("B", 4, 50)
api.shot("move_back")

api.tap("RIGHT", 4, 50)
api.shot("battle_pokemon")         -- ★ 我方队伍（Small 字体）
api.tap("LEFT", 4, 50)
api.shot("battle_menu_back")

-- にげる（第 4 项）
api.tap("DOWN", 4, 30)
api.tap("DOWN", 4, 30)
api.tap("DOWN", 4, 30)
api.tap("A", 4, 150)
api.wait(120)
api.shot("fled")

return api.S
