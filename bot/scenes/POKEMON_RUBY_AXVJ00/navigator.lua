-- ============================================================================
-- navigator.lua — ポケナビ（领航员）主菜单 + トレーナーアイ（训练家信息图）
--
-- 【到达目标】野外 → START → 第 4 项「ポケナビ」→ A → 主菜单逐项浏览
--   → 第 3 项「トレーナーアイ」→ A → 训练家列表逐项下移
--
-- 【为什么必须做这个场景】（BUG 3）
--   1) 主菜单 5 项每换一项，底部说明文字整句重画（长句 12px）—— 换项时
--      旧句的**半格残影**最容易留在新句左侧，是「文字残留」的典型现场。
--   2) 主菜单左栏「メインメニュー」框 + 齿轮底图是**有花纹的背景**；汉字
--      绘制若用不透明底色铺格子，会把花纹涂成一片紫 —— 这就是
--      「领航员左侧背景颜色很怪」。
--   3) トレーナーアイ 一屏里同时有：左侧信息栏（地名 / 注册人数 / 对战次数）、
--      右侧训练家列表（两列：职业 + 名字）、底部工具栏。三块共用同一个
--      背景 charblock，撞 tile 一眼可见。
--
-- 【观察点】每帧都保留 VRAM dump，可事后核对「哪些 tile 被汉字写入」，
--   因此这里**不做任何裁剪**，把整个界面连同边框一起拍下来。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("overworld")

-- ── 进 ポケナビ（系统菜单第 4 项）────────────────────────────────────────────
L.open_menu_at(api, L.MENU.NAV)
api.shot("nav_on_item")
api.tap("A", 4, 90)
api.shot("nav_boot")            -- 开机动画帧（可能还是黑屏/logo）
api.wait(60)
api.shot("nav_home")            -- 主菜单首项

-- ── 主菜单 5 项逐项下移：每项都会重画底部说明（最长句在这里）──────────────
for i = 2, 5 do
    api.tap("DOWN", 4, 30)
    api.shot(string.format("nav_item%d", i))
end
-- 回顶：反向再走一遍，检查「选中态高亮 + 说明句」重绘后有没有残影
for _ = 1, 4 do api.tap("UP", 4, 10) end
api.wait(20)
api.shot("nav_back_top")

-- ── 第 3 项「トレーナーアイ」→ 训练家信息图 ────────────────────────────────
for _ = 1, 2 do api.tap("DOWN", 4, 20) end
api.shot("nav_on_trainer")
api.tap("A", 4, 90)
api.shot("nav_trainer_enter")

-- 列表逐项下移：左栏背景 + 选中高亮 + 底部工具栏同时重绘
for i = 2, 6 do
    api.tap("DOWN", 4, 30)
    api.shot(string.format("nav_trainer_%d", i))
end
for _ = 1, 5 do api.tap("UP", 4, 10) end
api.wait(20)
api.shot("nav_trainer_top")

-- ── 退回：列表 → 主菜单 → 野外 ──────────────────────────────────────────────
api.tap("B", 4, 45)
api.shot("nav_back")
api.tap("B", 4, 45)
api.shot("nav_closed")

return api.S
