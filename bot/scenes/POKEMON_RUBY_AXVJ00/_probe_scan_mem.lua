-- ============================================================================
-- _probe_scan_mem.lua — 扫描战斗内存，找日版真实地址
--
-- 【为什么需要】
--   符号表 configs/.../pokeruby_jp.sym 里 gPlayerParty=0x03004360 /
--   gEnemyParty=0x030045C0 都标着 KEEP-US（沿用美版地址），
--   但实测 prove 得到的 SaveBlock2=0x02024C04 与美版布局不同
--   ⇒ IWRAM/EWRAM 的其余地址不能想当然沿用，必须实测。
--
--   上一次 probe 读 0x030045C0(len=100) 与 0x02024A80(len=96) 全是 0，
--   而截图明确显示已在战斗中（敌方 正电拍拍 Lv12、我方 火焰鸡 Lv36 77/115）
--   ⇒ 那两个地址在日版是空的，必须重新定位。
--
-- 【做法】
--   进战斗后，扫 IWRAM(0x03000000..0x03008000) 与 EWRAM 相关段的大块内存，
--   把非零区域 dump 到 scene.log，本地用脚本找「100B 队伍结构」的特征：
--     · 6 只为 1 组，每组 100B
--     · 每只 +0x54 是 level（1..100）
--     · +0x56 curHP / +0x58 maxHP 合理（curHP <= maxHP，且 maxHP > 0）
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("sm_ov")

-- 进战斗（同 _probe_battle_mem）
L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("sm_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.tap("A", 4, 70)
api.tap("A", 4, 70)
api.burst("sm_cast", 8, 6)
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("sm_in", 8, 6)
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("sm_menu", 10, 4)
api.shot("sm_settled")

-- ★ 扫描：IWRAM 整段（32KB，分 8 次 × 4KB）
--   0x03000000..0x03008000
for i = 0, 7 do
    api.probe{ addr = 0x03000000 + i * 0x1000, len = 1024, tag = "iram_" .. i .. "a" }
    api.probe{ addr = 0x03000000 + i * 0x1000 + 1024, len = 1024, tag = "iram_" .. i .. "b" }
    api.probe{ addr = 0x03000000 + i * 0x1000 + 2048, len = 1024, tag = "iram_" .. i .. "c" }
    api.probe{ addr = 0x03000000 + i * 0x1000 + 3072, len = 1024, tag = "iram_" .. i .. "d" }
end

-- 扫描 EWRAM 前 64KB 里战斗相关段（0x02020000..0x02026000，每 4KB 取首尾 512B）
for i = 0, 11 do
    local base = 0x02020000 + i * 0x1000
    api.probe{ addr = base, len = 512, tag = "ewram_" .. i .. "a" }
    api.probe{ addr = base + 2048, len = 512, tag = "ewram_" .. i .. "b" }
end

api.shot("sm_done")
return api.S
