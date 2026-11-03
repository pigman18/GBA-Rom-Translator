-- ============================================================================
-- font_capture.lua — 字库定位专用场景（T3）
--
-- 【目的】把字模从 VRAM 里分离出来，且**字符集已知**。
--
-- 【关键设计】必须「背景不变、只有文字变」，否则差分抓到的是背景图块。
--   实测教训：
--     · overworld vs menu_top → 92 差异 tile，72 个转 1bpp 后是 `ff ff ff ff`
--       （纯色填充）= 菜单背景，不是字模
--     · bag_a vs bag_b        → 只有 10 差异 tile，多是光标高亮，文字没变
--   所以改用**图鉴**：滚动条目时，右侧名称与说明文字整体替换，背景不变。
--
-- 【采集序列】
--   baseline_overworld   野外（无文字）
--   dex_1..dex_4         图鉴连续 4 个条目   ← ★核心：同背景、不同文字
--   menu_top             开始菜单（另一组已知字符）
--   closed               退回野外
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("baseline_overworld")

-- ★ 核心：图鉴，连续滚动条目（背景不变，名称/说明文字整体变化）
L.open_menu_at(api, L.MENU.DEX)
api.tap("A", 4, 90)
api.shot("dex_1")
for i = 2, 4 do
    api.tap("DOWN", 4, 30)
    api.shot("dex_" .. i)
end
L.exit_to_overworld(api, 4, "dex_closed")

-- 另一组：开始菜单 8 项
L.open_menu_at(api, 1)
api.shot("menu_top")

L.exit_to_overworld(api, 4, "closed")
api.wait(40)
api.shot("baseline_after")

return api.S
