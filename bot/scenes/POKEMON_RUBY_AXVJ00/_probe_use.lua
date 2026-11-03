-- ============================================================================
-- _probe_use.lua — 探针：背包「学习装置 → 使用」到底弹几个框、几页、怎么退
--
-- 用户实测：背包第 1 项「学习装置」→ A 出子菜单（使用/携带/丢弃/取消）
--   → 再 A 选「使用」→ 弹出**长说明对话框**，文字横着压到背包列表上。
-- 这是 BUG 1/BUG 2 最严重的一帧，必须进 bag 场景。
--
-- 本探针按 A/B 各推进几下、每下都拍一张，用来确定：
--   ① 说明框是一页还是多页；② 每页文字有没有打印动画（要不要等）
--   ③ 关掉以后回到列表还是回子菜单（决定后续步骤怎么接）
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local function body(api)
    api.shot("bag_open")

    -- 子菜单
    api.tap("A", 8, 45)
    api.shot("p_sub")
    api.tap("A", 8, 40)
    api.shot("p_sub2")

    -- 「使用」→ 说明框
    api.tap("A", 8, 40)
    api.shot("p_use_1")
    api.tap("A", 8, 40)
    api.shot("p_use_2")
    api.tap("A", 8, 40)
    api.shot("p_use_3")
    api.tap("A", 8, 40)
    api.shot("p_use_4")

    -- 退：看是回列表还是回子菜单
    api.tap("B", 8, 40)
    api.shot("p_back_1")
    api.tap("B", 8, 40)
    api.shot("p_back_2")
    api.tap("B", 8, 40)
    api.shot("p_back_3")
end

return L.make_scene(L.MENU.BAG, "p_use", body)
