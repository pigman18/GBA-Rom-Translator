-- ============================================================================
-- battle_dialog.lua — 战斗内确认框 + 战斗结算（覆盖文档 §7.2 C 类与 B 类）
--
-- 【要覆盖什么】
--   C 类（战斗中确认框，5 个调用点，文本 `はい\nいいえ`）：
--     · 投球动作确认（0x08028EEC）
--     · 学新招确认（0x08021118）
--     · 招式效果切换（0x08020D58）
--     · 通信待机（0x0802B658，无网络时到不了）
--   B 类（战斗胜负横幅，13 个调用点，文本 `かち`/`まけ`/`ひきわけ`）：
--     · 打完一整场 → 结算画面
--
-- 【怎么触发】
--   ① 确定性遇敌（prove → poke 钉 RNG → hunt → await），与 battle_full 同款
--   ② 进战斗后用「背包 → 投球」触发**投球确认框**（はい/いいえ）
--   ③ 连续打，直到一方倒下，进结算看胜负横幅
--
-- ⚠ 不改变存档：投球会消耗精灵球，但这份 teleport.sav 是专用于采集的副本，
--   且每个场景都重新读档，不影响其他场景。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local ADDR_RNG = 0x03004818

L.preamble(api)
api.shot("bd_overworld")

-- ① 确定性遇敌
api.poke{ { addr = ADDR_RNG, width = 4, value = 0x0000AAAA, note = "钉 RNG" } }
api.hunt{ dir = "DOWN", x = 68, y = 7, steps = 40, timeout = 120 }
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 900, tag = "battle" }
api.burst("bd_transition", 16, 8)
api.shot("bd_battle_in")

-- ② 推过开场台词，进主菜单
for i = 1, 3 do
    api.tap("A", 5, 45)
    api.burst(string.format("bd_intro%d", i), 8, 8)
end
api.shot("bd_menu")

-- ③ 主菜单 → 背包（右列上方 = バッグ）
api.tap("RIGHT", 5, 25)          -- たたかう → バッグ
api.shot("bd_on_bag")
api.tap("A", 6, 60)
api.burst("bd_bag_open", 14, 8)
api.shot("bd_bag")

-- ⚠ 实测：这份存档的战斗背包里**没有精灵球**（只有学习装置/好伤药/
--   先制之爪等道具），所以「投球确认框」触发不了。
--   改选「好伤药」—— 使用道具会弹「要用在谁身上 / はい・いいえ」确认框，
--   同样能采到 C 类的 `はい\nいいえ` 窗口。
--   列表顺序（截图实测）：学习装置 / PP单项小补剂 / 活力碎片 / 好伤药 /
--   先制之爪 / 奇迹种子 / 小蘑菇 / 丝绸围巾
api.tap("DOWN", 4, 26)           -- 学习装置 → PP单项
api.tap("DOWN", 4, 26)           -- → 活力碎片
api.tap("DOWN", 4, 26)           -- → 好伤药
api.shot("bd_on_potion")
api.burst("bd_potion_f", 6, 6)

-- 选「好伤药」按 A → 先出**道具子菜单**（使用/取消），见 087.png
api.tap("A", 6, 60)
api.burst("bd_item_menu", 16, 6)
api.shot("bd_item_menu_shot")

-- ⚠ 关键：子菜单里再选「使用」才会弹 **はい / いいえ** 确认框。
--   第一次按 A 只是开子菜单（实测截图：只有「使用」「取消」两项），
--   这里第二次按 A 才真正执行。
api.tap("A", 6, 60)
api.burst("bd_ball_confirm", 20, 6)
api.shot("bd_ball_confirm_shot")

-- 确认框上左右移动，把「はい」「いいえ」都采到
api.tap("RIGHT", 4, 25)
api.shot("bd_confirm_no")
api.burst("bd_confirm_no_f", 8, 5)
api.tap("LEFT", 4, 25)
api.shot("bd_confirm_yes")
api.burst("bd_confirm_yes_f", 8, 5)

-- 选「はい」使用
api.tap("A", 6, 80)
api.burst("bd_throw", 20, 8)
api.shot("bd_throw_shot")

-- ④ 连打：一直按 A 推进战斗，直到结束（受伤/倒下/逃跑都会出横幅）
for i = 1, 24 do
    api.tap("A", 5, 50)
    api.burst(string.format("bd_fight%02d", i), 4, 8)
end
api.shot("bd_fight_end")

-- ⑤ 结算画面：胜负横幅
api.burst("bd_result", 24, 10)
api.shot("bd_result_shot")

-- 再多推几步，穿过结算
for i = 1, 8 do
    api.tap("A", 5, 60)
    api.burst(string.format("bd_after%d", i), 6, 10)
end
api.shot("bd_end")

return api.S
