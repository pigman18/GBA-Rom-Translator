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
            assert(opt.dispcnt, "await 需要 dispcnt（DISPCNT 实测值）")
            S[#S + 1] = {
                act = "await",
                n = opt.timeout or 3000,
                addr = 0x04000000, value = opt.dispcnt,
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
        -- ★ 读档证明：在 EWRAM 里搜 .sav 的存档身份字节。
        --   ⚠ 语义边界：Gen3 在**标题画面**就已经把存档读进内存（用于画
        --     「继续游戏」摘要），所以 prove 通过 = **存档有效且被识别**，
        --     不等于「已经进入野外」。后者由 await 的画面特征负责。
        prove = function()
            S[#S + 1] = { act = "prove", n = 0 }
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

    -- ② 等「继续游戏」菜单出现
    api.await{ dispcnt = 0x3140, bg0 = 0x1F08, timeout = 4000, tag = "mainmenu" }
    api.tap("A", 20, 30)

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
