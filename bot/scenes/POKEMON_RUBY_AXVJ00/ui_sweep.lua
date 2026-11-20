-- ============================================================================
-- ui_sweep.lua — UI 全扫：图鉴各子界面 + ポケナビ 各子界面
--
-- 【目的】把「预渲染成图片的日文」尽可能摆到屏幕上，供 scene harvest 抓
--   图块集（scripts/misc/harvest_obj_assets.py）。这个场景不追 BUG，只负责
--   **把能进的界面都进一遍**：
--     图鉴：列表（滚动）→ 条目页 → 顶部四键
--           ぶんぶ(分布) / なきごえ / おおきさ / もどる
--     ポケナビ：主菜单 5 项 → ポケモンずかん / コンディション /
--           トレーナーアイ（列表 + 详情）/ きんりぼん
--
-- 【结构：一段一个 flow】每段都从野外 START 重新进，结尾 B 连按 + await
--   回到野外（DISPCNT=0x7F60）。这样某一段走歪只毁那一段，不会把后面全部
--   带进草丛打野生战（2026-11-20 第一版就是这么废掉的：图鉴 esa 退出后
--   一路 DOWN/A 走进草里，navigator 段全拍成遇敌画面）。
--
-- 【实测界面特征（2026-11-20 ui_sweep 第一版 + 20261119 navigator）】
--   野外       0x7F60  BG0=1F08
--   图鉴列表   0x9F40  BG0=0C00      （标题「ポケモンずかん」+ 捕获数 + 列表）
--   图鉴条目   0x1E40  BG0=0000      （顶部按钮带 ぶんぶ/なきごえ/おおきさ/もどる）
--   图鉴地区图 0x7741  BG0=1E0D
--   ポケナビ   0x3F40  BG0=1F01
--   进图鉴地区图有明显加载（第一版实测隔了 ~2000 帧才进），必须 await 而不是数帧。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local OW, DEX_LIST, DEX_ENTRY, DEX_AREA, NAV = 0x7F60, 0x9F40, 0x1E40, 0x7741, 0x3F40

-- 连按 B 退回野外（B 在野外无副作用），再等 DISPCNT 回到野外值
local function to_overworld(tag)
    for _ = 1, 6 do api.tap("B", 4, 40) end
    api.await{ dispcnt = OW, timeout = 1500, tag = tag .. "_ow" }
    api.wait(30)
    api.shot(tag .. "_overworld")
end

-- 从野外打开系统菜单，进第 index 项
local function menu_enter(index)
    L.open_menu_at(api, index)
    api.tap("A", 4, 60)
end

L.preamble(api)
api.shot("ui_ow")

-- ── ① 系统菜单 8 项逐项 ───────────────────────────────────────────────────
L.open_menu_at(api, 1)
api.shot("ui_menu_01")
for i = 2, L.MENU_COUNT do
    api.tap("DOWN", 4, 18)
    api.shot(string.format("ui_menu_%02d", i))
end
for _ = 1, L.MENU_COUNT - 1 do api.tap("UP", 4, 10) end
api.wait(20)
api.tap("B", 4, 45)
to_overworld("ui_menu")

-- ── ② 图鉴列表：滚动 + 左右翻 ─────────────────────────────────────────────
menu_enter(L.MENU.DEX)
api.await{ dispcnt = DEX_LIST, timeout = 800, tag = "dex_list" }
api.burst("ui_dexlist_open_f", 10, 8)
api.shot("ui_dexlist")
for i = 1, 4 do
    api.tap("DOWN", 4, 40)
    api.shot(string.format("ui_dexlist_dn%d", i))
end
for _ = 1, 4 do api.tap("UP", 4, 40) end
api.wait(20)
api.shot("ui_dexlist_top")
for i = 1, 2 do
    api.tap("RIGHT", 4, 40)
    api.burst(string.format("ui_dexlist_r%d_f", i), 6, 6)
    api.shot(string.format("ui_dexlist_r%d", i))
end
for _ = 1, 2 do api.tap("LEFT", 4, 40) end
api.wait(20)
api.shot("ui_dexlist_l2")
to_overworld("ui_dexlist")

-- ── ③ 图鉴条目页 + 顶部四键（一次进到底，用 RIGHT 在标签间横跳）───────────
-- 【实测 2026-11-20】顶部那排 ぶんぶ/なきごえ/おおきさ/もどる 本身就是一个
--   横向 tab 条：在子界面里按 RIGHT 直接切到下一个标签页（地区图 → なきごえ
--   → おおきさ），不必退回条目页重新选。于是只进一次，靠 RIGHT 连跳。
--   ⚠ 以前「菜单只进一次 + UP×6 归顶」翻车的根因也在这里：**这些列表是
--     循环的**，多按会绕回起点（6 次 UP 落在第 3 项），必须按精确步数走。
menu_enter(L.MENU.DEX)
api.await{ dispcnt = DEX_LIST, timeout = 800, tag = "dex_entry_list" }
api.tap("A", 4, 80)
api.await{ dispcnt = DEX_ENTRY, timeout = 800, tag = "dex_entry_page" }
api.wait(30)
api.shot("ui_entry_bar")
api.tap("A", 4, 80)
api.await{ dispcnt = DEX_AREA, timeout = 1600, tag = "dex_area_map" }
api.burst("ui_area_map_f", 12, 8)
api.wait(30)
api.shot("ui_area_map")

-- ③a 地区图：方向键挪光标（UP/DOWN 在图内移动，不切标签）
for i, d in ipairs({ "DOWN", "DOWN", "UP", "UP", "UP" }) do
    api.tap(d, 4, 40)
    api.burst(string.format("ui_area_pan%d_f", i), 6, 5)
    api.shot(string.format("ui_area_pan%d", i))
end

-- ③b なきごえ（RIGHT 切标签）
api.tap("RIGHT", 4, 40)
api.wait(60)
api.shot("ui_cry")
api.burst("ui_cry_f", 12, 8)
api.wait(150)                       -- 叫声播放期间画面在动
api.shot("ui_cry_end")

-- ③c おおきさ（和训练家比高）
api.tap("RIGHT", 4, 40)
api.wait(40)
api.shot("ui_size")
api.tap("RIGHT", 4, 40)
api.shot("ui_size_r")
api.tap("LEFT", 4, 40)
api.shot("ui_size_l")

-- ③d もどる 标签
api.tap("RIGHT", 4, 40)
api.wait(40)
api.shot("ui_modoru")
to_overworld("ui_dex")

-- ── ④ ポケナビ：一次会话里逐行 A 扫，走完所有子界面 ────────────────────────
-- 【为什么一次进到底】2026-11-20 实测（_probe_nav_reentry）：nav 一旦用 B 关掉，
--   再从 START 菜单重进，START 会被吞掉（一直停在野外，等 0x3F40 超时）。
--   所以整段只能在一次 nav 会话里做完。
-- 【键盘纪律】实测「按住 4 帧偶尔被判成两格」（光标跳行，v3 就因此跑飞），
--   方向键统一 tap(k, 2, 60)。
-- 【不按下标记账】主菜单是循环的，取模记账一错就全盘错位。改成「走一格就 A 进
--   一次」，位置由实测决定：退出子界面后光标停在刚进的那一行，所以每步只按一次
--   DOWN 就落到下一行。实测命中顺序（20261120T111717）：
--     row1 マップ / row2 ずかん / row3 コンディション / row4 トレーナーアイ /
--     row5 きんりぼん / row6 スイッチオフ，row6 再 DOWN 绕回 row1。
--   マップ排最后：从 map 退回来时偶发多跳一格，这样它跳不跳都不影响别人。
menu_enter(L.MENU.NAV)
api.await{ dispcnt = NAV, timeout = 2000, tag = "nav_open" }
api.burst("ui_nav_boot_f", 16, 8)
api.wait(60)
api.shot("ui_nav_home")

local function nav_back(tag, backs)
    for _ = 1, backs do api.tap("B", 2, 60) end
    api.await{ dispcnt = NAV, timeout = 1200, tag = tag .. "_main" }
    api.wait(40)
    api.shot(tag .. "_back_home")
end

local function nav_enter(tag, body)
    api.shot(tag .. "_on")
    api.tap("A", 4, 90)
    api.burst(tag .. "_enter_f", 12, 8)
    api.wait(70)
    api.shot(tag .. "_screen")
    if body then body() end
end

local function nav_next()
    api.tap("DOWN", 2, 60)
    api.wait(20)
end

-- ① コンディション（子菜单 てもちポケモン / ポケモンサーチ + てもちポケモン 列表）
--   实测：从 nav 首行按一次 DOWN（光标会走两格）正好落到 コンディション。
nav_next()
nav_enter("ui_navcond", function()
    api.tap("DOWN", 2, 60)              -- てもちポケモン → ポケモンサーチ
    api.shot("ui_navcond_sub_dn")
    api.tap("UP", 2, 60)
    api.wait(20)
    api.tap("A", 4, 80)                 -- 进 てもちポケモン
    api.burst("ui_navcond_list_f", 10, 8)
    api.wait(60)
    api.shot("ui_navcond_list")
    api.tap("DOWN", 2, 60)
    api.shot("ui_navcond_list_dn")
    api.tap("B", 2, 60)                 -- 列表 → 子菜单
    api.shot("ui_navcond_sub_back")
    api.wait(30)
end)
nav_back("ui_navcond", 1)

-- ③ row4 トレーナーアイ：列表 + 详情（左右切人）
nav_next()
nav_enter("ui_navtr", function()
    for i = 2, 4 do
        api.tap("DOWN", 2, 60)
        api.shot(string.format("ui_navtr_%d", i))
    end
    for _ = 1, 3 do api.tap("UP", 2, 60) end
    api.wait(20)
    api.shot("ui_navtr_top")
    api.tap("A", 4, 90)
    api.burst("ui_navtr_detail_f", 14, 8)
    api.wait(30)
    api.shot("ui_navtr_detail")
    for i, k in ipairs({ "RIGHT", "RIGHT", "LEFT" }) do
        api.tap(k, 2, 60)
        api.burst(string.format("ui_navtr_sw%d_f", i), 6, 5)
        api.shot(string.format("ui_navtr_sw%d", i))
    end
    api.tap("DOWN", 2, 60)
    api.shot("ui_navtr_detail_dn")
    api.tap("B", 2, 60)                 -- 详情 → 列表，剩一层由 nav_back 收
    api.shot("ui_navtr_detail_back")
    api.wait(30)
end)
nav_back("ui_navtr", 1)

-- ④ きんりぼん（列表 + 单条详情）
--   实测（v8）：从 トレーナーアイ 退回主菜单后光标仍停在 トレーナーアイ，
--   再按一次 DOWN 才到 きんりぼん；再按一次就是 スイッチオフ（按 A 会关掉 nav）。
nav_next()
nav_enter("ui_navrib", function()
    for i = 1, 3 do
        api.tap("DOWN", 2, 60)
        api.shot(string.format("ui_navrib_dn%d", i))
    end
    for _ = 1, 3 do api.tap("UP", 2, 60) end
    api.wait(20)
    api.shot("ui_navrib_top")
    api.tap("A", 4, 90)                 -- リボンを見る
    api.burst("ui_navrib_detail_f", 10, 8)
    api.wait(50)
    api.shot("ui_navrib_detail")
    api.tap("B", 2, 60)                 -- 详情 → 列表
    api.shot("ui_navrib_detail_back")
    api.wait(30)
end)
nav_back("ui_navrib", 1)

-- ⑤ row6 スイッチオフ：只看高亮，不按 A（按了会把 nav 关掉）
nav_next()
api.shot("ui_nav_off_on")

-- ⑥ 绕回 row1 ポケナビマップ（地区图：放大/缩小/挪光标）
nav_next()
nav_enter("ui_navmap", function()
    for i, d in ipairs({ "RIGHT", "RIGHT", "DOWN", "LEFT", "UP" }) do
        api.tap(d, 2, 60)
        api.burst(string.format("ui_navmap_%s%d_f", d:lower(), i), 6, 5)
        api.shot(string.format("ui_navmap_%s%d", d:lower(), i))
    end
end)
api.tap("B", 2, 60)
to_overworld("ui_nav")

-- ── ⑤ 结束 ────────────────────────────────────────────────────────────────
api.await{ dispcnt = OW, timeout = 800, tag = "ui_end" }
api.shot("ui_end")

return api.S
