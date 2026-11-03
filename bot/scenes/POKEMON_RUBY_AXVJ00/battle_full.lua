-- ============================================================================
-- battle_full.lua — 野生战斗全界面（Small 字体主战场）
--
-- 【为什么这个场景重要】
--   战斗是 Small（fontNum=4 / 8×8）最密集的一屏：
--     战斗主菜单四项（たたかう/バッグ/ポケモン/にげる）
--     招式名 + PP「15/15」、我方/敌方宝可梦名 + 等级、HP 数值
--   这些正是文档 §7.2 E/D 类窗口（`たたかう バッグ\nポケモン にげる`）。
--
-- 【确定性遇敌：本场景的关键设计】（2026-11-03 实测定型，勿再改）
--   实测 6 轮结论：
--     · 只钉 RNG（gRngValue @0x03004818）→ 遇敌格差 1
--     · 只 hunt（一遇敌就停）→ translated 侧 30 格都没遇到，纯随机
--     · **钉一次 RNG + hunt** → 两侧**都在第 5 格遇敌**，完全一致 ✅
--   所以顺序必须是：prove → poke 钉 RNG → hunt → await 战斗界面。
--   ⚠ poke 必须在 prove 之后（用户口径：先加载 .sav 再用金手指），
--     bot.lua 侧有两道硬门槛把关。
--
-- 【采集策略】每屏都 burst 多帧：
--   转场、台词打印、菜单四项逐项、招式列表 —— 单帧证明不了「过程连续」。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ADDR_RNG = 0x03004818

L.preamble(api)
api.shot("ov_overworld")

-- ── 确定性遇敌 ─────────────────────────────────────────────────────────────
api.poke{ { addr = ADDR_RNG, width = 4, value = 0x0000AAAA, note = "钉 RNG" } }
api.hunt{ dir = "DOWN", x = 68, y = 7, steps = 40, timeout = 120 }

-- ── 转场：连帧看「草丛抖动 → 黑场 → 战斗登场」 ────────────────────────────
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 900, tag = "battle" }
api.burst("bt_transition", 20, 8)

-- ── 开场台词「あ！ やせいの ○○が とびだしてきた！」逐字打印 ──────────────
for i = 1, 3 do
    api.tap("A", 4, 40)
    api.burst(string.format("bt_intro%d", i), 10, 8)
end

-- ── 战斗主菜单（四项，§7.2 E 类）─────────────────────────────────────────
api.shot("bt_menu")
for i = 2, 4 do
    api.tap("RIGHT", 4, 24)
    api.burst(string.format("bt_menu_%d", i), 6, 6)
end
-- 向左回到第 1 项
for _ = 1, 3 do api.tap("LEFT", 4, 24) end
api.shot("bt_menu_back")

-- ── 招式列表（§7.2 D 类：招式名 + PP + 属性）─────────────────────────────
api.tap("A", 4, 60)
api.burst("bt_moves", 12, 8)
api.shot("bt_move_list")
for i = 2, 4 do
    api.tap("DOWN", 4, 24)
    api.burst(string.format("bt_move_%d", i), 4, 6)
end
for _ = 1, 3 do api.tap("UP", 4, 16) end

-- ── 回主菜单看「宝可梦」子菜单（队伍 + HP + 等级）─────────────────────────
--    ⚠ 战斗主菜单是 2×2 布局：たたかう / バッグ
--                            ポケモン / にげる
--      所以「作战 → 宝可梦」是 **DOWN**（不是 RIGHT）。
--      2026-11-03 踩过：连按两次 RIGHT 进的是「背包」，采到的是道具列表。
api.tap("B", 4, 40)              -- 退出招式列表回主菜单
api.tap("DOWN", 4, 24)           -- たたかう → ポケモン
api.shot("bt_on_pokemon")
api.tap("A", 4, 70)
api.burst("bt_party", 12, 8)
api.shot("bt_party_menu")

-- ── 逃跑收尾（不改变存档、不消耗道具）───────────────────────────────────
--   从宝可梦子菜单退回主菜单，再移到「にげる」（第 2 行右侧）
api.tap("B", 4, 40)
api.tap("DOWN", 4, 24)           -- 到第 2 行
api.tap("RIGHT", 4, 24)          -- 右列 = にげる
api.shot("bt_on_flee")
api.tap("A", 4, 80)
api.burst("bt_flee", 16, 8)

return api.S
