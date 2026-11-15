-- ============================================================================
-- bag_blank_rows.lua — 背包道具页下拉空白行取证
--
-- 用户路径：打开背包道具口袋 → 连续 DOWN 滚动
-- 现象：中间出现无名空白行，数量列残留「1」；「劲爽汽水」等像隔行重复
--
-- 相对 bag.lua：不跑「使用」说明/多口袋，专盯列表滚动每一格。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local function body(api)
    api.burst("bb_enter", 10, 5)
    api.shot("bb_open")

    -- 顶行起逐格下移；每格 shot + 短 burst（空白行只在滚动中出现）
    for i = 1, 16 do
        api.tap("DOWN", 4, 22)
        api.burst(string.format("bb_dn%d_f", i), 6, 3)
        api.shot(string.format("bb_dn%d", i))
    end

    -- 再滚一段到列表中后部（用户截图「丝绸围巾」附近空白）
    for i = 17, 28 do
        api.tap("DOWN", 4, 18)
        if i % 2 == 0 then
            api.burst(string.format("bb_dn%d_f", i), 5, 3)
            api.shot(string.format("bb_dn%d", i))
        end
    end
    api.burst("bb_mid_settle", 8, 4)
    api.shot("bb_mid")

    -- 回顶再下一次，对照是否「又出现」空白
    for _ = 1, 20 do api.tap("UP", 4, 10) end
    api.burst("bb_top_f", 8, 4)
    api.shot("bb_top")
    for i = 1, 10 do
        api.tap("DOWN", 4, 20)
        api.shot(string.format("bb_re%d", i))
    end
    api.shot("bb_re_end")
end

return L.make_scene(L.MENU.BAG, "bb", body)
