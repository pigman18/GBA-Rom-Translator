-- ============================================================================
-- _probe_teleport2.lua — 修正 WarpData 偏移后，正式验证「传送术跳图」
--
-- 【上一轮的重大突破】传送成功了！
--   读档城市 map=0:2 → 按 A 之后 map 变成 **0:33（Route118）**，
--   画面弹出「118号道路」地名框。这是本轮第一次真正跨图成功。
--
-- 【唯一的问题】落点坐标错：读到 (1860,6)，角色站在水上。
--   1860 = 0x0744，低字节 0x44=68（我想要的 x），高字节 0x07（我写的 y）。
--   原因：我把 y 写到了 +0x05，而权威结构是
--
--     struct WarpData {           // include/global.h（pret/pokeruby）
--         s8  mapGroup;   // +0
--         s8  mapNum;     // +1
--         s8  warpId;     // +2
--         s16 x, y;       // +4(x), +6(y)   ← s16 对齐后是 +4 和 +6
--     };
--
--   ⇒ x 在 lastHealLocation+0x04（SB1+0x20），y 在 +0x06（SB1+0x22）。
--     上一轮我写了 0x20/0x21，把 y 塞进了 x 的高字节。
--
-- 【本场景】用正确偏移再来一次，落点应当是干净的地面。
-- ============================================================================
local L = dofile((os.getenv("BOT_ROOT") or "."):gsub("\\", "/"):gsub("/+$", "")
                 .. "/scenes/" .. os.getenv("BOT_GAME_ID") .. "/_lib.lua")
local api = L.new()

L.preamble(api)
api.shot("tp2_start")                -- 商店内 map=10:7

-- ① 正确写 lastHealLocation：g/n/warpId 各 1 字节，x/y 各 2 字节
--    lastHealLocation 起始 = SB1+0x1C
--      +0x00 g, +0x01 n, +0x02 warpId, +0x03 pad,
--      +0x04 x(s16) → SB1+0x20, +0x06 y(s16) → SB1+0x22
api.poke{
    { sb1 = 0x1C, width = 1, value = 0x00, note = "lastHeal.g=0" },
    { sb1 = 0x1D, width = 1, value = 0x21, note = "lastHeal.n=33" },
    { sb1 = 0x1E, width = 1, value = 0xFF, note = "lastHeal.warpId=-1" },
    { sb1 = 0x1F, width = 1, value = 0x00, note = "pad" },
    { sb1 = 0x20, width = 2, value = 68, note = "lastHeal.x=68 (s16)" },
    { sb1 = 0x22, width = 2, value = 7,  note = "lastHeal.y=7  (s16)" },
}
api.shot("tp2_target_set")

-- ② 出商店到城市（传送术要野外）
api.roam{ seq = { "DOWN", "DOWN" }, steps = 8 }
api.shot("tp2_outside")              -- map=0:2

-- ③ 开菜单 → 宝可梦 → 第 2 只 → 查看能力（用 A 推到底即可触发？）
--    上一轮实测：传送是在「按 A 进 summary」那一步触发的，
--    说明使用的不是传送术，而是别的机制（很可能是菜单里的某个默认动作）。
--    所以本轮**只推 A，不盲目翻页**，把触发点定位清楚。
api.tap("START", 4, 60)
for _ = 1, 8 do api.tap("UP", 4, 6) end
api.tap("DOWN", 4, 12)
api.tap("A", 4, 80)
api.shot("tp2_party")

api.tap("DOWN", 4, 24)               -- 第 2 只
api.shot("tp2_sel2")
api.tap("A", 4, 70)                  -- DoWhat 菜单
api.shot("tp2_dowhat")

-- 关键：上一轮传送就在这一步之后发生，本轮逐帧盯死
api.tap("A", 4, 40)
api.burst("tp2_trigger", 20, 4)
api.wait(60)
api.shot("tp2_after")

return api.S
