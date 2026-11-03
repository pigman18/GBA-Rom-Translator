-- ============================================================================
-- title_menu.lua — 标题画面 + 继续游戏主菜单（对照 验收效果/1.PNG）
--
-- 【到达目标】开机 → 版权 → 标题（POKEMON RUBY / PUSH START）
--             → A → 「つづきから はじめる / さいしょから はじめる /
--                    せっていを かえる」三行主菜单
--
-- 【时序】★ 全部走状态驱动 await，不再赌帧数：
--   标题   DISPCNT=1741 且 BG0CNT=180B   （实测特征，见 _lib.lua 顶部）
--   主菜单 DISPCNT=3140 且 BG0CNT=1F08
--
-- ⚠ 本场景**不复用 preamble** —— preamble 会一路读档到野外，
--   而这里要停在主菜单上采集。读档证明仍然要做（主菜单就会加载存档摘要）。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

-- 1) 等标题画面站稳
api.await{ dispcnt = 0x1741, bg0 = 0x180B, timeout = 4000, tag = "title" }
api.shot("title")                    -- 标题画面

-- 2) A 进主菜单（标题只认 A / START，长按 20 帧才有确定的按下沿）
api.tap("A", 20, 30)

-- 3) 等主菜单出现
api.await{ dispcnt = 0x3140, bg0 = 0x1F08, timeout = 4000, tag = "mainmenu" }
api.shot("mainmenu")                 -- ★ 对照 验收效果/1.PNG

-- 4) 存档有效性证明（主菜单会读存档摘要画「つづきから」）
api.prove()

-- 5) 光标下移 / 回顶，验证选中高亮的重绘
api.tap("DOWN", 8, 40)
api.shot("mainmenu_down")
api.tap("DOWN", 8, 40)
api.shot("mainmenu_down2")
api.tap("UP", 8, 40)
api.tap("UP", 8, 40)
api.shot("mainmenu_back_top")

return api.S
