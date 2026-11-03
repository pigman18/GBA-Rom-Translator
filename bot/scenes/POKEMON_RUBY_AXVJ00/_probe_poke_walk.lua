-- ============================================================================
-- _probe_poke_walk.lua — poke 坐标后补一步走位，看相机是否跟随
--
-- 上一个探针发现：poke 写 pos 后 [POS] 日志立刻变（(4,15)/(10,10) 都对），
-- 但两张截图**像素级一样** —— 画面没跟着变。
--
-- 推断：Gen3 的相机（BG 卷动）跟着**角色对象**走，而角色对象的位置
--       是在走位逻辑里同步的。只改 SaveBlock1 的 pos，逻辑坐标变了，
--       但角色 sprite/相机没刷新，直到下一次真正走一格。
--
-- 本探针验证：poke 后**补按一下方向键**（走一格），相机是否跳到新位置。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("pw_shop")

api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("pw_out")                 -- (23,17) map=0:2

-- ① 只 poke，不按任何键
api.poke{
    { sb1 = 0x00, width = 2, value = 5, note = "x=5" },
    { sb1 = 0x02, width = 2, value = 12, note = "y=12" },
}
api.wait(20)
api.shot("pw_poke_only")           -- 预期：画面没变

-- ② 补一步走位（按一下 DOWN），让相机刷新
api.tap("DOWN", 8, 20)
api.wait(20)
api.shot("pw_after_step")          -- 预期：画面跳到 (5,12) 附近

-- ③ 再 poke 一次 + 补步，确认可重复
api.poke{
    { sb1 = 0x00, width = 2, value = 30, note = "x=30" },
    { sb1 = 0x02, width = 2, value = 12, note = "y=12" },
}
api.wait(12)
api.tap("DOWN", 8, 20)
api.wait(20)
api.shot("pw_poke2_step")

return api.S
