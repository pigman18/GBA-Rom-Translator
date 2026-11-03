-- _diag2.lua — 按 A 进主菜单的现场取证（逐 60 帧快拍）
--
-- 已知：标题 await 两侧都 hit f=3664；按 A 后 origin 在 f=3880 进主菜单，
--   translated 停在 step=4 直到超时。
-- 本场景：await 标题 → 按 A → 立刻逐 60 帧快拍 20 张，
--   **不用 await 门控**（await 超时会 stop 并拒绝出图），
--   只为看到「按 A 之后到底画成什么样」。
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

-- 等到标题（这里 await 是安全的：两侧都已在 f=3664 命中）
api.await{ dispcnt = 0x1741, bg0 = 0x180B, timeout = 6000, tag = "title" }
api.shot("before_A")

-- 按 A（长按 20 帧，与 selfcheck 一致）
api.tap("A", 20, 30)

-- 逐 60 帧快拍，覆盖「按 A 之后」的完整过程
for i = 1, 20 do
    api.wait(60)
    api.shot(string.format("afterA%02d", i))
end

return api.S
