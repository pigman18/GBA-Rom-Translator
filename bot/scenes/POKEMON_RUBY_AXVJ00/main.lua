-- mGBA --script 入口。场景步骤由 bot.lua 从
--   bot/scenes/<gameId>/<scene>.lua
-- 读取并回放。本文件只做衔接，不含任何逻辑。
local root = assert(os.getenv("BOT_ROOT"), "BOT_ROOT missing; use bot/run.py")
dofile(root:gsub("\\", "/"):gsub("/+$", "") .. "/bot.lua")
