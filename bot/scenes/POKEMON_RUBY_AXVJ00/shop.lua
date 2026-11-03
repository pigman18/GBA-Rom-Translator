-- shop.lua — 商店菜单/购买列表（Mart 存档）
-- 与 dialogue.lua 的区别：只走到商店菜单 + 购买列表，不做二次重开。
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("overworld")

-- 转向柜台（Mart 起点 3,3，店员在左侧）
api.tap("LEFT", 6, 40)
api.talk{ timeout = 300 }
api.wait(60)
api.shot("shop_welcome")

-- 欢迎语 -> 商店主菜单 -> 购买列表
api.tap("A", 4, 50)
api.shot("shop_menu")
api.tap("A", 4, 50)
api.shot("shop_buylist")

-- 逐项下移（购买列表每项重绘）
for i = 2, 4 do
    api.tap("DOWN", 4, 30)
    api.shot(string.format("shop_item%d", i))
end

-- 退出：购买列表 -> 商店菜单 -> 告别 -> 关闭
api.tap("B", 4, 45)
api.shot("shop_menu_back")
api.tap("B", 4, 45)
api.shot("shop_farewell")
api.tap("A", 4, 45)
api.shot("shop_closed")

return api.S
