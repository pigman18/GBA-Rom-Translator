-- ============================================================================
-- party.lua — 火红队伍界面（对照 BUG-13 的中文名 + 字体大小）
--
-- 【为什么做这个场景】
--   用户 2026-11-23：要把火红汉化的队伍界面截图，与 ruby 汉化版对比
--   「宝可梦名字的字号大小」。ruby 侧队伍名字是 fontNum=4（Small 8px），
--   火红汉化怎么处理需要实测对照。
--
-- 【时序】沿用 fr_party_dump.lua 里已验证可进队伍界面的驱动：
--   标题(0x9F40) → A → 主菜单(0x3140) → UP → A → 存档确认(0x7F60)
--   → 连按 B 退掉 → START 开菜单 → DOWN → A 进队伍
--   进队伍后 DISPCNT 实测 0x1740。
--
-- 【产物】party_list 等截图，走 bot/run.py 的标准五件套（png/vram/pal/io/ram），
--   可与 ruby 侧同名场景逐像素对照。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local api = L.new()

-- ① 标题画面：DISPCNT 0x9F40 是火红标题实测值
api.await({ dispcnt = 0x9F40, timeout = 3000, tag = "title" })
api.shot("title")

-- ② 标题 → A → 主菜单
api.tap("A", 16, 60)
api.await({ dispcnt = 0x3140, timeout = 2000, tag = "mainmenu" })
api.shot("main_menu")

-- ③ 主菜单：UP 到「继续」→ A → 存档确认框
api.tap("UP", 10, 25)
api.tap("A", 16, 80)
api.await({ dispcnt = 0x7F60, timeout = 2500, tag = "saveconfirm" })
api.shot("save_confirm")

-- ④ 连按 B 退掉存档确认/主菜单，回到野外
for _ = 1, 11 do api.tap("B", 10, 40) end
-- 读档已完成（存档身份字节应已在 EWRAM）→ 出证明，否则 run.py 判"对照无效"
api.prove()
api.shot("overworld")

-- ⑤ 野外 → START 开菜单 → DOWN → A 进队伍
api.tap("START", 16, 90)
api.burst("start_menu_enter", 6, 6)
api.tap("DOWN", 8, 30)
api.tap("A", 16, 120)

-- ⑥ 队伍列表（★ 本场景的核心帧）
api.await({ dispcnt = 0x1740, timeout = 3000, tag = "party" })
api.burst("party_enter", 10, 6)
api.shot("party_list")

-- ⑦ 光标逐只下移：每只的名字都要重绘一次，逐个抓
for i = 2, 6 do
    api.tap("DOWN", 4, 30)
    api.burst(string.format("party_sel%d_f", i), 4, 5)
    api.shot(string.format("party_sel%d", i))
end
for _ = 1, 5 do api.tap("UP", 4, 15) end
api.shot("party_back_top")

return api.S
