-- ============================================================================
-- _lib.lua — 场景共用构建器（纯步骤生成器，不调模拟器）
--
-- ── 起点状态 ───────────────────────────────────────────────────────────────
--   118 号道路野外（Route118_68-7.sav），读档后可自由行动、无对话框。
--
-- ── 铁律：任何场景开头都不许无脑连按 A ────────────────────────────────────
--   主角身边有 NPC，连按 A 会打开对话框，而对话框会吞掉后续所有按键。
--   清场一律用 B（野外无副作用）。
--
-- ── 系统菜单顺序（AXVJ 开始菜单，自上而下）────────────────────────────────
--   図鑑 / ポケモン / バッグ / ポケナビ / ユウキ / レポート / せってい / とじる
--
-- ── 与 bot.lua 的契约 ──────────────────────────────────────────────────────
--   步骤 = { act = "A"|"B"|"SELECT"|"START"|"UP"|"DOWN"|"LEFT"|"RIGHT"|"R"|"L"
--                  |"wait"|"shot"|"prove",
--            n = 帧数（shot/prove 不用）, name = 截图名(shot 必填且唯一) }
--
--   ★ 2026-10-17：时序模型改为「状态驱动」。bot.lua 会在**每个步骤之后**
--     自动等画面连续 K 帧不变（SETTLE）才推进下一步。于是这里的帧数只承担
--     「跨过中间稳定态」的粗定位（例如版权画面本身就是静止的，纯 settle
--     会停在那里），真正的精定位由 settle 完成。
--     关键词：**等稳定，不等帧数**。
-- ============================================================================

local M = {}

function M.new()
    local S = {}
    local api = {
        S = S,
        tap = function(k, n, w)
            S[#S + 1] = { act = k, n = n or 4 }
            if w then S[#S + 1] = { act = "wait", n = w } end
            return api
        end,
        wait = function(n) S[#S + 1] = { act = "wait", n = n }; return api end,
        shot = function(name)
            S[#S + 1] = { act = "shot", n = 0, name = name }
            return api
        end,
        -- ★ 状态驱动等待：等「画面稳定 **且** 出现目标界面特征」。
        --   这是对「按固定帧数赌时序」的正面替代 —— 实测教训：
        --   版权/标题画面本身就是静止的，只靠 settle 会停在错误的地方；
        --   而固定 wait 又会在慢/快的路径上按早或按晚。
        --   用法：api.await{ dispcnt=0x1741, bg0=0x180B, timeout=3000, tag="title" }
        await = function(opt)
            opt = opt or {}
            assert(opt.dispcnt or opt.any_of,
                "await 需要 dispcnt（DISPCNT 实测值）或 any_of（候选值列表）")
            S[#S + 1] = {
                act = "await",
                n = opt.timeout or 3000,
                addr = 0x04000000,
                value = opt.dispcnt or (opt.any_of and opt.any_of[1]) or 0,
                any_of = opt.any_of,
                addr2 = opt.bg0 and 0x04000008 or nil, value2 = opt.bg0,
                tag = opt.tag or "await",
            }
            return api
        end,
        -- ★★ 走一格并等坐标对齐（移动场景的**唯一正确解法**）。
        --   实测教训：两侧从同一存档同一帧盲走 N 步后，画面相似度会从
        --   1.000 掉到 0.063 —— 走路是逐帧累积的，按键时序差一帧就走到
        --   不同格。await(dispcnt) 判得了「界面变了」，判不了「站在哪一格」。
        --   · `pos` 就是**格子坐标**（不是像素；踩坑两轮才定下来）
        --   · 2026-10-18 起按键策略 = **持续按住，一到位当帧松手**
        --     （旧版「按固定帧数再松手」把时长和格数绑死，换个方向就漂；
        --      现在每帧读坐标决定按不按，走几格都只管写目标格）
        --   · axis="y"/"x" 时判「该轴已到或已过」，nil 时两轴都须精确相等
        --   · 按住却 40 帧没挪格 ⇒ 判定被 NPC/墙挡住（日志会打 BLOCKED）
        --   用法：api.walk("DOWN", 68, 9, 300, true, 20, "y")
        --   ⚠ 必须先 prove（prove 会定位 SaveBlock2 的运行时地址）。
        walk = function(dir, gx, gy, timeout, soft, hold, axis)
            S[#S + 1] = { act = "walk", n = timeout or 600, dir = dir,
                          x = gx, y = gy, soft = soft or false,
                          hold = hold or 20, axis = axis }
            return api
        end,
        -- 纯等待坐标停稳（不按键）
        await_pos = function(x, y, timeout, soft)
            S[#S + 1] = { act = "await_pos", n = timeout or 600, x = x, y = y,
                          soft = soft or false }
            return api
        end,
        -- ★ 对话闸门：按 A，然后等**已验证的真实文本窗口**出现。
        --   为什么要有它：旧版 dialogue 场景原地按 A 打空（NPC 不在面前），
        --   截图却照样被记成合法对照 —— 场景「静默没走到」是采集里最贵的错。
        --   窗口校验（tpl 的 charBase/tileData/tilemap 必须对上真实 BGxCNT）
        --   把假阳性从 7/7 压到 0，因此这个信号可以直接当硬闸门用。
        --   用法：api.talk{ timeout = 300, soft = false }
        talk = function(opt)
            opt = opt or {}
            S[#S + 1] = { act = "talk", n = opt.timeout or 300,
                          press = opt.press or 4, soft = opt.soft or false }
            return api
        end,
        -- ★ 条件按键：当前 DISPCNT == want 时才按 key，否则直接跳过本步。
        --   用途：读档有两条合法路径（经「继续游戏」菜单 / 直接续玩进野外），
        --   哪条出现取决于 A 落在哪一帧。写死「等菜单再按 A」在另一条路径上
        --   会白等超时 + 按空（2026-11-03 selfcheck 实测）。
        tap_if_menu = function(want, key, n, w)
            S[#S + 1] = { act = "tap_if", want = want, key = key or "A", n = n or 4 }
            if w then S[#S + 1] = { act = "wait", n = w } end
            return api
        end,
        -- ★ 读档证明：在 EWRAM 里搜 .sav 的存档身份字节。
        --   ⚠ 语义边界：Gen3 在**标题画面**就已经把存档读进内存（用于画
        --     「继续游戏」摘要），所以 prove 通过 = **存档有效且被识别**，
        --     不等于「已经进入野外」。后者由 await 的画面特征负责。
        prove = function()
            S[#S + 1] = { act = "prove", n = 0 }
            return api
        end,
        -- ★★ 多帧连续采集：拍 n 张，每张间隔 every 帧（默认逐帧）。
        --   用途：单张 shot 只能证明「某个定型帧长这样」，证明不了过程连续。
        --   战斗转场、血条递减、逐字打印、菜单逐项高亮都必须看连续帧。
        --   落盘名：<prefix>_01.png、<prefix>_02.png …
        --   ⚠ 只出 PNG（不出 vram/ram 五件套）：全量 dump 每帧 ~385KB，
        --     连续 30 帧就 11MB，而 burst 是用来看画面演进的，不是逐帧做
        --     tile 级分析。需要 dump 的关键帧仍旧单用 shot。
        burst = function(prefix, n, every)
            S[#S + 1] = { act = "burst", n = n or 10, every = every or 1,
                          name = prefix }
            return api
        end,
        -- ★★ 金手指：把一组写操作打到**实时内存**。
        --   与 savestate 的本质区别（用户契约第 3 条）：savestate 是内存快照，
        --   会把 ROM 的 hook 改动一起冻住，验收失真；这里写的是正在跑的实时
        --   内存，ROM 是当次加载的。
        --
        --   ⚠⚠ 顺序铁律（2026-11-03 用户口径）：**必须先读档再改内存**。
        --     写早了（标题/主菜单阶段）改的是尚未被存档初始化的 EWRAM，
        --     读档时会被整个覆盖 ⇒ 表现成「按了没反应」；更糟的是可能
        --     写坏别的结构，让人误判成汉化有问题。
        --     bot.lua 侧有两道运行时门槛：SB2_RUNTIME 已定位（prove 命中）
        --     + DISPCNT 不在标题(1741)/继续菜单(3140)。这里再加一道**准备期**
        --     断言，让场景作者把顺序写错时在开跑前就炸，而不是跑到底才发现。
        --   用法：
        --     api.poke{ {sb1=0x00, width=2, value=0x0844, note="传送到 x"} }
        --     api.poke{ {addr=0x02024EA4, width=1, value=1} }
        --   sb1 = SaveBlock1 内偏移（推荐；跟存档走，地址由 prove 定位）
        --   addr= 绝对地址（VD 用）
        --   width = 1/2/4；value 会被截断到对应宽度；写后会复核读回值
        poke = function(writes)
            local proved = false
            for _, s in ipairs(S) do
                if s.act == "prove" then proved = true end
            end
            assert(proved,
                "poke 之前必须已有 prove 步骤：金手指只能在读档成功后执行，" ..
                "否则改到的是尚未被存档初始化的 EWRAM（等于没改，还可能写坏数据）")
            S[#S + 1] = { act = "poke", writes = writes }
            return api
        end,
        -- ★★ 遇敌搜捕：逐格走，一旦 DISPCNT 离开野外值就停手。
        --   为什么这样最好（2026-11-03 用户选定的方案）：
        --   实测 5 轮证明「第 N 格必遇敌」做不到 —— 两侧写入的 RNG 序列
        --   逐值相同、走位坐标逐格相同，遇敌格仍差 1（还有帧号相关判定）。
        --   与其继续攻，不如**一旦遇敌就停**：后面的采集从战斗画面开始，
        --   两侧都从同一个界面对齐，差值被吸收在 hunt 内部。
        --   用法：api.hunt{ dir="DOWN", x=68, y=7, steps=24 }
        hunt = function(opt)
            opt = opt or {}
            S[#S + 1] = { act = "hunt", dir = opt.dir or "DOWN",
                          x = opt.x, y = opt.y,
                          steps = opt.steps or 24,
                          n = opt.timeout or 120,
                          wild = opt.wild }
            return api
        end,
        -- ★★ 跨图漫游：只按方向推进，不依赖绝对格坐标。
        --   为什么必须有它（2026-11-03 实测）：
        --   换地图靠改 .sav **无效**，但**走位跨图有效** ——
        --   商店 (3,3) 向下走 ⇒ map=0:2 城市 (23,17)。
        --   而换图会把坐标重置，所以按绝对格坐标 walk 会立刻判「已到位/被挡」。
        --   本动作每方向连走 steps 格，撞墙（40 帧没挪格）自动换下一方向。
        --   用法：api.roam{ seq={"DOWN","LEFT","UP","UP","RIGHT"}, steps=8 }
        roam = function(opt)
            opt = opt or {}
            S[#S + 1] = { act = "roam", seq = opt.seq or { "DOWN" },
                          steps = opt.steps or 8, n = opt.timeout or 100 }
            return api
        end,
        -- ★★★ 精确跳图（2026-11-03 实测跑通）。
        --
        -- 原理：Gen3「传送术」的野外效果 = 回到 SaveBlock1.lastHealLocation，
        -- 走 Overworld_ResetStateAfterTeleport → WarpIntoMap
        -- （WarpIntoMap 全文件仅三处调用之一；普通走门走 CB2_LoadMap，不读它）。
        -- 所以先写 lastHealLocation，再让游戏自己传送，落点精确到格。
        --
        -- 实测：城市 map=0:2 (23,17) → warp{map="0:33",x=68,y=7}
        --       → 落地 map=0:33 grid=(68,7)，一字不差。
        --
        -- 前置：存档里必须有会「传送术(moveId=100)」的宝可梦：
        --   python scripts/warp_tool.py --apply --out <新存档>
        --   然后用这份存档跑场景。
        -- 用法：api.warp{ map = "0:33", x = 68, y = 7, mon = 1 }
        warp = function(opt)
            opt = opt or {}
            S[#S + 1] = { act = "warp", map = opt.map, x = opt.x, y = opt.y,
                          mon = opt.mon or 1, n = opt.timeout or 1200 }
            return api
        end,
    }
    return api
end

-- 实测界面特征（POKEMON_RUBY_AXVJ00，2026-10-17 探针 run 101655 采集）：
--   标题画面   dispcnt=1741（淡入态 B441） BG0CNT=180B BG1CNT=190A BG2CNT=4981
--   继续游戏   dispcnt=3140             BG0CNT=1F08 BG1/BG2=0000
-- 判据用 (DISPCNT, BG0CNT) 双条件 + settle 的 6 帧稳定，避开淡入过渡帧。
--
-- ⚠⚠ 读档序列里**不能夹 B**（B 会把「继续游戏」确认取消，实测会退回标题）。
function M.boot_and_load(api, opts)
    opts = opts or {}
    local boot = opts.boot or 0

    if boot > 0 then
        for _ = 1, boot do api.tap("A", 4, 24) end
        api.wait(120)
        api.wait(120)
        return api
    end

    -- ① 等标题画面站稳（不再赌 420 帧 —— 之前正是在版权画面就按了 A）
    api.await{ dispcnt = 0x1741, bg0 = 0x180B, timeout = 4000, tag = "title" }
    api.tap("A", 20, 30)

    -- ② 等「继续游戏」菜单 —— 但**它不一定出现**（2026-11-03 实测）
    --
    -- ★ 踩坑记录：selfcheck 场景里 A 命中的时机稍早/稍晚，游戏会
    --   直接续玩进野外（DISPCNT 从标题 1741 跳到野外 7F60），
    --   中间根本没有 3140 那个「继续游戏」菜单。
    --   旧写法硬等 0x3140 ⇒ 白等 4000 帧后整场失败，而那只说明
    --   「这次走了另一条合法路径」，不是 bot 坏了。
    --
    -- 新写法：等「3140（菜单）**或** 7F60（已进野外）」任一命中，
    --   然后按是否真的到了菜单，决定还要不要按 A。
    --   用 any_of 一次等手段，避免"先等菜单超时再补等野外"烧两倍帧数。
    api.await{ any_of = { 0x3140, 0x7F60 }, timeout = 4000, tag = "mainmenu" }

    -- 若停在菜单（3140），按 A 进去；已在野外就直接进第 ③ 步。
    -- 判据直接读当前 DISPCNT，不再靠场景里的猜测。
    api.tap_if_menu(0x3140, "A", 20, 30)

    -- ③ 等读档淡入 + 地图加载
    api.wait(400)
    return api
end

-- 完整前置：开机 → 标题 → 主菜单 → 读档 → **证明存档已被识别**
--
-- ⚠ B 只用于「确认已在野外后清掉任何残留对话框」，**不能放进读档序列**。
function M.preamble(api, opts)
    opts = opts or {}
    local out = opts.out or 0

    M.boot_and_load(api, opts)
    api.prove()                                     -- ★ 存档有效性证明
    for _ = 1, out do api.tap("B", 4, 45) end
    api.wait(30)
    return api
end

M.MENU = { DEX = 1, POKEMON = 2, BAG = 3, NAV = 4, TRAINER = 5,
           SAVE = 6, OPTION = 7, EXIT = 8 }
M.MENU_COUNT = 8
M.MENU_NAME = { "図鑑", "ポケモン", "バッグ", "ポケナビ", "ユウキ",
                "レポート", "せってい", "とじる" }

-- 打开系统菜单并停在第 index 项（1-based）。
-- 先上移足够多次保证到顶，再下移 index-1 —— 不依赖进入时光标位置。
function M.open_menu_at(api, index)
    api.tap("START", 4, 60)
    for _ = 1, M.MENU_COUNT do api.tap("UP", 4, 8) end
    for _ = 1, index - 1 do api.tap("DOWN", 4, 12) end
    api.wait(30)
    return api
end

-- 进入菜单第 index 项，进入后连拍 n 张兜住淡入过渡
function M.enter_menu_item(api, index, prefix, n)
    M.open_menu_at(api, index)
    api.shot(prefix .. "_on_item")
    api.tap("A", 4, 40)
    n = n or 3
    local tags = { "a", "b", "c", "d" }
    for i = 1, n do
        api.shot(string.format("%s_%s", prefix, tags[i] or tostring(i)))
        if i < n then api.wait(40) end
    end
    return api
end

-- 收尾：B 连按退回野外
function M.exit_to_overworld(api, presses, tag)
    for _ = 1, (presses or 4) do api.tap("B", 4, 45) end
    api.wait(60)
    api.shot(tag or "closed")
    return api
end

-- ── 场景模板 ────────────────────────────────────────────────────────────────
-- 全部场景共用同一条骨架：
--   preamble（读档 + prove）→ 打开系统菜单并进入第 index 项 → 采集 → 退回野外
--
-- ★ make_scene 存在的意义：**保证每个场景都带读档证明**，不会有人漏写。
--   没有 prove 的采集 = 无法证明存档被加载 = 不可用于验收。
function M.make_scene(index, prefix, body, opts)
    opts = opts or {}
    local api = M.new()
    M.preamble(api, opts)
    api.shot("overworld")

    M.open_menu_at(api, index)
    api.shot(prefix .. "_on_item")
    api.tap("A", 4, 60)
    api.shot(prefix .. "_enter")

    if body then body(api) end

    M.exit_to_overworld(api, opts.presses or 5, prefix .. "_closed")
    return api.S
end

-- 系统菜单逐项浏览（用于 start_menu 场景）
function M.browse_start_menu(api, prefix)
    M.open_menu_at(api, 1)
    api.shot(prefix .. "_top")
    for i = 1, M.MENU_COUNT - 1 do
        api.tap("DOWN", 4, 25)
        api.shot(string.format("%s_%d", prefix, i + 1))
    end
    return api
end

return M
