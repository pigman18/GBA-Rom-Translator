-- ============================================================================
-- navigator.lua — ポケナビ（领航员）主菜单 + トレーナーアイ（训练家信息图）
--
-- 【到达目标】野外 → START → 第 4 项「ポケナビ」→ A → 主菜单逐项浏览
--   → 第 3 项「トレーナーアイ」→ A → 训练家列表逐项下移
--   → 列表顶项再 A → 训练家详情（作战 / 持有宝可梦 / 自我介绍）→ B 退回
--
-- 【为什么必须做这个场景】（BUG 3 + 详情混合 BUG）
--   1) 主菜单 5 项每换一项，底部说明文字整句重画（长句 12px）—— 换项时
--      旧句的**半格残影**最容易留在新句左侧，是「文字残留」的典型现场。
--   2) 主菜单左栏「メインメニュー」框 + 齿轮底图是**有花纹的背景**；汉字
--      绘制若用不透明底色铺格子，会把花纹涂成一片紫 —— 这就是
--      「领航员左侧背景颜色很怪」。
--   3) トレーナーアイ 一屏里同时有：左侧信息栏（地名 / 注册人数 / 对战次数）、
--      右侧训练家列表（两列：职业 + 名字）、底部工具栏。三块共用同一个
--      背景 charblock，撞 tile 一眼可见。
--   4) 详情页：红条标题乱码/粘连、标签旁正文叠日文残片、左栏数字底色——
--      与列表页不同的打印路径，必须单独进详情采集。
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
-- 2026-11-03：开机动画 + 主菜单淡入，连帧覆盖（单帧会停在黑屏/logo）
api.burst("nav_boot_f", 20, 8)
api.shot("nav_boot")            -- 开机动画帧（可能还是黑屏/logo）
api.wait(60)
api.shot("nav_home")            -- 主菜单首项

-- ── 主菜单 5 项逐项下移：每项都会重画底部说明（最长句在这里）──────────────
-- 说明句整句重画是 BUG 3（左侧背景被涂）的标准现场，必须连帧看
for i = 2, 5 do
    api.tap("DOWN", 4, 30)
    api.burst(string.format("nav_item%d_f", i), 8, 6)
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
api.burst("nav_trainer_enter_f", 14, 8)
api.shot("nav_trainer_enter")

-- 列表逐项下移：左栏背景 + 选中高亮 + 底部工具栏同时重绘
for i = 2, 6 do
    api.tap("DOWN", 4, 30)
    api.burst(string.format("nav_trainer_%d_f", i), 6, 6)
    api.shot(string.format("nav_trainer_%d", i))
end
for _ = 1, 5 do api.tap("UP", 4, 10) end
api.wait(20)
api.shot("nav_trainer_top")

-- ── 第一训练家详情（列表顶项 A）────────────────────────────────────────────
-- 对照点：红条标题（职业+名间距/乱码）、作战/持有/自我介绍正文叠字、
-- 左侧注册/对战数字底色、与日版同屏布局。调研用，勿当修完验收。
api.tap("A", 4, 90)
api.burst("nav_detail_enter_f", 16, 8)
api.shot("nav_detail")
api.wait(30)
api.shot("nav_detail_settle")
-- BUG-A 回归：详情内切换训练家时地点名是否跟随变动（原场景未覆盖）。
-- 逐个按键试，origin 侧看哪种触发切换（标题/红条/地点变化），translated 对照。
for _, k in ipairs({"L", "R", "LEFT", "RIGHT", "UP"}) do
    api.tap(k, 4, 25)
    api.burst(string.format("nav_detail_%s_f", k:lower()), 6, 6)
    api.shot(string.format("nav_detail_%s", k:lower()))
end
-- 详情内若可下翻说明（自我介绍多行）
for i = 1, 3 do
    api.tap("DOWN", 4, 25)
    api.burst(string.format("nav_detail_down%d_f", i), 6, 6)
    api.shot(string.format("nav_detail_down%d", i))
end
api.tap("B", 4, 50)
api.burst("nav_detail_back_f", 10, 6)
api.shot("nav_detail_back")

-- ── 退回：列表 → 主菜单 → 野外 ──────────────────────────────────────────────
api.tap("B", 4, 45)
api.shot("nav_back")
api.tap("B", 4, 45)
api.shot("nav_closed")

return api.S
