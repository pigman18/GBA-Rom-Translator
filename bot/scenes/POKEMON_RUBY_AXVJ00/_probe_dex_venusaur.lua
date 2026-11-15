-- ============================================================================
-- _probe_dex_venusaur.lua — 图鉴条目「妙蛙花」说明缺字复现（调研/回归）
--
-- origin：PageScreen Menu_PrintText(desc, left=2, top=13) → 三行 y=13/15/17。
-- 列表可能不在 001：先 UP 回顶，再找带球的 No.003（本档已收服）。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local function body(api)
    api.burst("dex_list", 14, 6)
    api.shot("dex_list")

    -- 回列表顶（未见种会显示 -----，光标仍可上下）
    for _ = 1, 20 do api.tap("UP", 4, 10) end
    api.burst("dex_top_f", 6, 4)
    api.shot("dex_top")

    -- 本档列表顶可见「妙蛙花」+球（未见种为 -----）。
    -- 光标常停在下方未见项；再 UP 几次保证停在有名字的那一行再 A。
    for _ = 1, 8 do api.tap("UP", 4, 10) end
    api.burst("dex_on_caught_f", 8, 4)
    api.shot("dex_on_caught")

    api.tap("A", 4, 50)
    -- 条目页淡入较慢：多 burst
    api.burst("dex_venusaur_f", 24, 6)
    api.shot("dex_venusaur")
end

return L.make_scene(L.MENU.DEX, "_probe_dex_venusaur", body)
