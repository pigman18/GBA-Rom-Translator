-- ============================================================================
-- _probe_do_suru.lua — 定位「X怎么办?」这句话的真实文本来源
--
-- 【背景】用户截图指出战斗菜单每回合都显示「バシャーモ怎么办?」：
--   ① バシャーモ 未翻译（应为「火焰鸡」）
--   ② 「怎么办?」是生硬直译
--
-- texts.json 里 4 条候选：
--   0x083DC980  \0Fは どうする？   → 译文 \0F怎么办?
--   0x083DC98A  \20は どうする？   → 译文 \20怎么办?
--   0x083DC994  ミツルは どうする？ → 译文 小智要怎么做?
--   0x083EA622  \02を どうする？   → 译文 要做什么？
-- 但都不含「バシャーモ」——说明名字是运行时由 \0F/\20 参数填入。
--
-- 【本场景要确认】
--   战斗菜单显示时，把 EWRAM 里所有「どうする」的残留串捞出来，
--   再 dump 对应的中文译文位置，看用的是哪条。
--
-- 说明：这次只读数、不改任何东西，纯诊断。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

local WILD = tonumber(os.getenv("BOT_WILD_TABLE") or "") or 0x083786D0

L.preamble(api)
api.shot("ds_ov")

local word = (354 << 16) | (25 << 8) | 25
api.pokecart{
    { addr = WILD + 0x00, width = 4, value = word },
    { addr = WILD + 0x04, width = 4, value = word },
    { addr = WILD + 0x08, width = 4, value = word },
    { addr = WILD + 0x0C, width = 4, value = word },
    { addr = WILD + 0x10, width = 4, value = word },
    { addr = WILD + 0x14, width = 4, value = word },
    { addr = WILD + 0x18, width = 4, value = word },
    { addr = WILD + 0x1C, width = 4, value = word },
    { addr = WILD + 0x20, width = 4, value = word },
    { addr = WILD + 0x24, width = 4, value = word },
    { addr = WILD + 0x28, width = 4, value = word },
    { addr = WILD + 0x2C, width = 4, value = word },
}

L.open_menu_at(api, L.MENU.POKEMON)
api.tap("A", 4, 90)
api.burst("ds_party", 6, 6)
for i = 1, 5 do api.tap("DOWN", 4, 26) end
api.tap("A", 4, 70)
api.tap("A", 4, 70)
api.burst("ds_cast", 8, 6)
api.await{ any_of = { 0x0000, 0xBF40 }, timeout = 1500, tag = "battle" }
api.burst("ds_in", 8, 6)
for i = 1, 3 do api.tap("A", 4, 40) end
api.burst("ds_menu", 10, 4)
api.shot("ds_menu_ready")

-- ★ 此时屏幕上正是「X怎么办?」。dump 文本缓冲区。
--   GBA 战斗对话框的文本先在 EWRAM 解码成字形索引，
--   但也可能保留原始 byte 串。全段 dump 后离线搜。
-- probe 单次上限 1024B，按 1KB 分段 dump 前 32KB（文本缓冲通常在低区）
for i = 0, 31 do
    api.probe{ addr = 0x02000000 + i * 0x400, len = 0x400,
               tag = string.format("ew%02d", i) }
end
api.shot("ds_done")

return api.S
