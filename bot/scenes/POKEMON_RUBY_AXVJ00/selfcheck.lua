-- ============================================================================
-- selfcheck.lua — bot 自检场景（框架健康度，不是汉化验收场景）
--
-- 目的：一次跑完就能判断 bot 的四根支柱是否都成立
--   1) await 能等到标题 / 主菜单（状态驱动时序有效）
--   2) prove 能在 EWRAM 里找到存档身份字节（存档真的被加载）
--   3) 读档后确实停在野外，且按键有响应（START 能开菜单、B 能关掉）
--   4) settle 能把截图落在稳定画面上（settled=yes/soft，而不是 NO）
--
-- 跑法：python bot/run.py POKEMON_RUBY_AXVJ00 selfcheck --verify
-- 预期：3 张截图、两侧 dispcnt 轨迹一致、日志里 [PROVE] OK
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)                       -- 含 prove
api.shot("overworld")                 -- 应在 118 号道路野外

api.tap("START", 4, 60)
api.shot("menu_open")                 -- 系统开始菜单

api.tap("B", 4, 45)
api.shot("menu_closed")               -- 回到野外

return api.S
