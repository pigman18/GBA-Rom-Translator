-- ============================================================================
-- bag_pockets.lua — 背包「左右切口袋」扫描
--
-- 刚需来源：
--   口袋名条（どうぐ / ボール / わざマシン / きのみ / たいせつなもの…）是
--   预渲染的 BG 图块，光靠 bag_sweep（上下翻物品）只采得到「どうぐ」一条，
--   其余口袋名永远采不到。用户明确要求把技能、重要品、树果这些口袋补齐。
--
-- 做法：进背包后先拍当前口袋，再逐次 RIGHT 切到下一个口袋，各拍一张；
--       随后逐次 LEFT 切回来也各拍一张（用于确认「同一口袋两次进入一致」）。
--       切口袋时画面会换名条 + 换列表，settle 会等它定型。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")

local function body(api)
    -- 起始口袋（どうぐ）
    api.shot("bag_pockets_00_start")

    -- 向右切：AXVJ 口袋顺序 どうぐ → ボール → わざマシン → きのみ → たいせつなもの
    for i = 1, 6 do
        api.tap("RIGHT", 4, 45)
        api.shot(string.format("bag_pockets_%02d_right", i))
    end

    -- 向左切回，验证循环一致性
    for i = 1, 6 do
        api.tap("LEFT", 4, 45)
        api.shot(string.format("bag_pockets_%02d_left", i))
    end

    api.shot("bag_pockets_99_back_start")
end

return L.make_scene(L.MENU.BAG, "bag_pockets", body)
