-- ============================================================================
-- _probe_find_battle.lua — 定位 gBattleMons（日版）
--
-- 【已确认的事实链】
--   ① gPlayerParty = 0x03004290（实测，lv36 77/115 与截图一致）
--   ② gEnemyParty 的 E[0] 在 0x030044F0 附近（lv13）
--   ③ 改写 gEnemyParty 的明文区（level/maxHP/curHP/atk）
--      → poke 复核成功，但**下一帧就被游戏重算覆盖**，血条毫无变化
--   ④ 搜 species 354 在 0x02020000..0x02026000 命中 0 处
--
--   ⇒ 血条读的是战斗副本，且它在别的地方。必须把 EWRAM 大范围扫一遍。
--
-- 【做法】
--   战斗定态后，扫 EWRAM 0x02000000..0x02040000（256KB）里
--   所有「species=354 或 353」的 u16 命中，再结合结构特征定位 gBattleMons。
--   为控制日志体积，每个 512B 段只 dump 可能含目标的区域：
--   先用小步长粗扫，命中后由 Python 侧分析。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("fb_ov")

-- 进战斗
L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("fb_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.tap("A", 4, 70)
api.tap("A", 4, 70)
api.burst("fb_cast", 8, 6)
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("fb_in", 8, 6)
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("fb_menu", 10, 4)
api.shot("fb_settled")

-- ★ 扫 EWRAM 0x02000000..0x02040000，每 8KB 一次 dump（1024B）
--   覆盖 64 次 probe，日志约 64KB，可接受
for i = 0, 31 do
    local base = 0x02000000 + i * 0x2000
    api.probe{ addr = base,         len = 1024, tag = "e" .. i .. "a" }
    api.probe{ addr = base + 1024,  len = 1024, tag = "e" .. i .. "b" }
    api.probe{ addr = base + 2048,  len = 1024, tag = "e" .. i .. "c" }
    api.probe{ addr = base + 3072,  len = 1024, tag = "e" .. i .. "d" }
    api.probe{ addr = base + 4096,  len = 1024, tag = "e" .. i .. "e" }
    api.probe{ addr = base + 5120,  len = 1024, tag = "e" .. i .. "f" }
    api.probe{ addr = base + 6144,  len = 1024, tag = "e" .. i .. "g" }
    api.probe{ addr = base + 7168,  len = 1024, tag = "e" .. i .. "h" }
end

api.shot("fb_done")
return api.S
