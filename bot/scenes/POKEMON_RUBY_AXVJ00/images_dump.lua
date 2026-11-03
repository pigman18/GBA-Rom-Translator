-- ============================================================================
-- images_dump.lua — 图片启发式导出的**运行时采样器**（mGBA --script 入口）
--
-- 由 src/util/images_patcher.py --mgba 拉起：
--     mGBA.exe --script images_dump.lua <rom.gba>
--
-- ── 为什么需要它（而不是纯扫描 ROM）─────────────────────────────────────────
--   纯 ROM 扫描只能看到「这段字节长得像图」，看不到「游戏到底加载了什么、
--   用哪张调色板画」。而 Gen3 的图标调色板是**运行时按精灵编号生成的**，
--   在 ROM 里根本不存在（实测 0x087EE9C8 的 5 种颜色全 ROM 搜不出一条 16 色
--   调色板）。所以只有把**运行中的 VRAM / OAM / 调色板 / EWRAM / IWRAM**
--   原样抓下来，再由 Python 拿来做 ROM 反查，才能得到真实配色。
--
-- ── 采样时机：画面稳定（settle）之后 ────────────────────────────────────────
--   游戏每进一个界面（野外 / 菜单 / 背包 / 图鉴 / 战斗 …）就抓一帧。
--   「稳定」判定沿用 bot/bot.lua 的教训：VRAM+PAL+IO 连续 K 帧不变才算稳定；
--   野外地图自带动画会让 VRAM 每帧都变，所以超时后**照样抓一帧**并标记
--   unstable（野外恰恰是最需要它的场景），只是不重复抓同样的内容。
--
-- ── 按键脚本 ────────────────────────────────────────────────────────────────
--   bot/run.py 用「每进一个界面等稳定 → 按键」的序列把游戏走遍各个界面。
--   本采样器直接复用同一套 `.sav` + 按键序列的思想，但**不截图**，只抓内存。
--
-- ── 产出（落在 IMG_OUT 目录）────────────────────────────────────────────────
--   dump_0000.bin  … 每个稳定界面一个文件，布局见下
--   index.json     机器可读索引（帧号 / 稳定性 / 各段地址与长度）
--
--   单帧文件布局（little-endian）:
--     u32 magic "IMGF" u32 version(=1) u32 frame u32 flags(bit0=unstable)
--     u32 seq
--     然后依次 8 段： vram(0x06000000,0x18000) pal(0x05000000,0x400)
--                     oam(0x07000000,0x400) ewram(0x02000000,0x40000)
--                     iwram(0x03000000,0x8000) io(0x04000000,0x060)
--                     rom_head(0x08000000,0x200) 备用(全 0)
--
-- ── 结束 ────────────────────────────────────────────────────────────────────
--   必须写 `done f=<帧号> seq=<n>`（工具靠它判断采样完成）。
-- ============================================================================

local OUT = assert(os.getenv("IMG_OUT"), "IMG_OUT missing; 请用 images_patcher.py --mgba 启动")

-- 参数（全部可配，默认值针对 Pokemon Ruby 的通用流程）
local MAX_SHOT      = tonumber(os.getenv("IMG_MAX_SHOT"))      or 120
local SETTLE_NEED   = tonumber(os.getenv("IMG_SETTLE_NEED"))   or 8
local SETTLE_TIMEOUT= tonumber(os.getenv("IMG_SETTLE_TIMEOUT"))or 900
local MAX_FRAMES    = tonumber(os.getenv("IMG_MAX_FRAMES"))    or 3000000
local LUA_PATH      = os.getenv("IMG_LUA")   -- 可选：自定义按键脚本

local function slash(s) return (s:gsub("\\", "/"):gsub("/+$", "")) .. "/" end
OUT = slash(OUT)

local lg = assert(io.open(OUT .. "images_dump.log", "w"), "cannot open images_dump.log")
local function log(s) lg:write(s .. "\n"); lg:flush() end

local function stop(code, msg)
    log(msg)
    lg:close()
    os.exit(code)
end

-- ── 段定义 ──────────────────────────────────────────────────────────────────
local SEGS = {
    { name = "vram",    addr = 0x06000000, len = 0x18000 },
    { name = "pal",     addr = 0x05000000, len = 0x400   },
    { name = "oam",     addr = 0x07000000, len = 0x400   },
    { name = "ewram",   addr = 0x02000000, len = 0x40000 },
    { name = "iwram",   addr = 0x03000000, len = 0x8000  },
    { name = "io",      addr = 0x04000000, len = 0x060   },
    { name = "romhead", addr = 0x08000000, len = 0x200   },
}

local function read_all()
    local t = {}
    for i, s in ipairs(SEGS) do
        local ok, v = pcall(function() return emu:readRange(s.addr, s.len) end)
        t[i] = (ok and v) or string.rep("\0", s.len)
    end
    return t
end

local function same(a, b)
    if a == nil or b == nil or #a ~= #b then return false end
    return a == b
end

-- 采样指纹：VRAM+PAL+IO 拼起来的哈希（只做快速比较，不用精确哈希）
local function fingerprint(t)
    return (t[1] or "") .. (t[2] or "") .. (t[6] or "")
end

-- ── 落盘 ────────────────────────────────────────────────────────────────────
local SEQ = 0
local FILES = {}

local function u32(v)
    v = v % 4294967296
    return string.char(v % 256, math.floor(v / 256) % 256,
                       math.floor(v / 65536) % 256, math.floor(v / 16777216) % 256)
end

local function dump(t, frame, unstable)
    SEQ = SEQ + 1
    local name = string.format("dump_%04d.bin", SEQ - 1)
    local f = assert(io.open(OUT .. name, "wb"), "cannot write " .. name)
    f:write("IMGF", u32(1), u32(frame), u32(unstable and 1 or 0), u32(SEQ - 1))
    for i = 1, #SEGS do f:write(t[i] or "") end
    -- 占位段，保持段数与声明一致
    f:write(string.rep("\0", 0))
    f:close()
    FILES[#FILES + 1] = name
    log(string.format("[DUMP] seq=%d f=%d unstable=%s", SEQ - 1, frame,
                      tostring(unstable or false)))
end

-- ── 按键脚本 ────────────────────────────────────────────────────────────────
-- 与 bot/scenes/POKEMON_RUBY_AXVJ00/_lib.lua 保持同一套时序模型：
--   ★「等状态，不等帧数」。
--   固定帧数会在版权画面/淡入过渡里按 A，把按键全吃掉（_lib.lua 原话：
--   「之前正是在版权画面就按了 A」）。所以关键节点一律等 DISPCNT/BG0CNT。
--
-- 实测界面特征（_lib.lua 注释，2026-10-17 探针）：
--   标题画面   dispcnt=0x1741  bg0=0x180B
--   继续游戏   dispcnt=0x3140  bg0=0x1F08
--
-- 系统菜单顺序（AXVJ，自上而下）：
--   図鑑 / ポケモン / バッグ / ポケナビ / ユウキ / レポート / せってい / とじる
--
-- ⚠ 读档序列里**不能夹 B**（B 会把「继续游戏」确认取消，退回标题）。
local MENU = { DEX = 1, POKEMON = 2, BAG = 3, NAV = 4, TRAINER = 5,
               SAVE = 6, OPTION = 7, EXIT = 8 }
local MENU_COUNT = 8

-- "await" 步骤：等到 IO 里的 (dispcnt, bg0cnt) 匹配才算这一步完成
local function await(dispcnt, bg0, tag)
    return { act = "await", want = { dispcnt = dispcnt, bg0 = bg0 }, tag = tag }
end

-- 读档序列（照抄 _lib.boot_and_load 的判据）
local function boot_steps()
    return {
        await(0x1741, 0x180B, "title"),   -- ① 等标题站稳
        { act = "A", n = 20, tag = "title_a" },
        await(0x3140, 0x1F08, "mainmenu"), -- ② 等「继续游戏」
        { act = "A", n = 20, tag = "continue" },
        { act = "WAIT", n = 400, tag = "load" }, -- ③ 读档淡入 + 地图加载
    }
end

-- 打开系统菜单并停在第 index 项（1-based）：先上移到顶，再下移 index-1
local function menu_at(index, tag)
    local S = {}
    S[#S + 1] = { act = "START", n = 4, tag = tag .. "_open" }
    for _ = 1, MENU_COUNT do
        S[#S + 1] = { act = "UP", n = 4, tag = tag .. "_top" }
    end
    for _ = 1, index - 1 do
        S[#S + 1] = { act = "DOWN", n = 4, tag = tag .. "_sel" }
    end
    S[#S + 1] = { act = "WAIT", n = 30, tag = tag .. "_settle" }
    return S
end

-- 进入菜单第 index 项并停留（n 帧后再抓，兜住淡入）
local function enter(index, tag, wait)
    local S = menu_at(index, tag)
    S[#S + 1] = { act = "A", n = 4, tag = tag .. "_enter" }
    S[#S + 1] = { act = "WAIT", n = wait or 150, tag = tag .. "_view" }
    return S
end

-- 退回野外：B 连按（野外无副作用，_lib.lua 铁律）
local function to_overworld(n, tag)
    local S = {}
    for _ = 1, n or 6 do S[#S + 1] = { act = "B", n = 4, tag = tag .. "_b" } end
    S[#S + 1] = { act = "WAIT", n = 100, tag = tag .. "_out" }
    return S
end

local function default_steps()
    local S = {}
    local function ext(list) for _, v in ipairs(list) do S[#S + 1] = v end end

    ext(boot_steps())                       -- 开机 → 标题 → 继续游戏 → 野外

    -- ① 野外本身（地图 tile、NPC 行走图）
    ext({ { act = "WAIT", n = 120, tag = "overworld" } })

    -- ② 系統菜单逐项（每条都要抓「菜单本身」和「进入后」两个界面）
    for i = 1, MENU_COUNT do
        ext(menu_at(i, "menu" .. i))        -- 光标停在第 i 项时的菜单画面
        ext(to_overworld(2, "menu" .. i))
    end

    -- ③ 图鉴：列表 + 往下翻几页
    ext(enter(MENU.DEX, "dex", 200))
    for _ = 1, 6 do ext({ { act = "DOWN", n = 4, tag = "dex_page" } }) end
    ext({ { act = "WAIT", n = 120, tag = "dex_page_view" } })
    ext(to_overworld(6, "dex"))

    -- ④ 精灵：列表 + 详情 + 翻页
    ext(enter(MENU.POKEMON, "pm", 200))
    for _ = 1, 5 do ext({ { act = "DOWN", n = 4, tag = "pm_sel" } }) end
    ext({ { act = "WAIT", n = 120, tag = "pm_browse" } })
    ext({ { act = "A", n = 4, tag = "pm_detail" } })
    ext({ { act = "WAIT", n = 200, tag = "pm_detail_view" } })
    for _ = 1, 3 do ext({ { act = "DOWN", n = 4, tag = "pm_detail_page" } }) end
    ext({ { act = "WAIT", n = 120, tag = "pm_detail_page_view" } })
    ext(to_overworld(8, "pm"))

    -- ⑤ 背包：列表 + 物品说明
    ext(enter(MENU.BAG, "bag", 200))
    for _ = 1, 8 do ext({ { act = "DOWN", n = 4, tag = "bag_sel" } }) end
    ext({ { act = "WAIT", n = 120, tag = "bag_browse" } })
    for _ = 1, 4 do ext({ { act = "RIGHT", n = 4, tag = "bag_pocket" } }) end
    ext({ { act = "WAIT", n = 120, tag = "bag_pocket_view" } })
    ext(to_overworld(6, "bag"))

    -- ⑥ 宝可表
    ext(enter(MENU.NAV, "nav", 200))
    for _ = 1, 4 do ext({ { act = "RIGHT", n = 4, tag = "nav_page" } }) end
    ext({ { act = "WAIT", n = 120, tag = "nav_view" } })
    ext(to_overworld(6, "nav"))

    -- ⑦ 训练家卡（含徽章、头像）
    ext(enter(MENU.TRAINER, "card", 220))
    for _ = 1, 3 do ext({ { act = "RIGHT", n = 4, tag = "card_page" } }) end
    ext({ { act = "WAIT", n = 150, tag = "card_view" } })
    ext(to_overworld(6, "card"))

    -- ⑧ 设置（字体、窗口边框等 UI 资源）
    ext(enter(MENU.OPTION, "opt", 180))
    ext(to_overworld(6, "opt"))

    ext({ { act = "WAIT", n = 100, tag = "end" } })
    return S
end

local STEPS = default_steps()
if LUA_PATH and LUA_PATH ~= "" then
    local ok, v = pcall(dofile, LUA_PATH)
    if ok and type(v) == "table" then
        STEPS = v
        log("[INI] 使用自定义按键脚本: " .. LUA_PATH)
    else
        log("[WRN] 自定义脚本加载失败，改用默认流程: " .. tostring(v))
    end
end

-- ── 主循环（keysRead：实测 frame 回调里 setKeys 不生效）──────────────────────
local KEYBIT = { A = 0, B = 1, SELECT = 2, START = 3, RIGHT = 4,
                 LEFT = 5, UP = 6, DOWN = 7, R = 8, L = 9 }

local FRAME_BASE = nil
local IDX = 0
local PHASE = "settle"      -- settle | hold | release | done
local HOLD = 0
local MASK = 0
local SETTLE_T = 0
local STABLE = 0
local LAST_FP = nil
local UNSTABLE = false
local LAST_DUMP_FP = nil
local DONE = false

local function keys_down(act)
    local b = KEYBIT[act]
    if not b then return 0 end
    return bit and (1 << b) or (2 ^ b)
end

-- 读 IO 里的 (DISPCNT, BG0CNT)。state 回调里每次现读，不缓存 ——
-- 淡入过渡会让它们逐帧变化，缓存就永远等不到目标值。
local function io_state()
    local ok, s = pcall(function()
        return { dispcnt = emu:read16(0x04000000), bg0 = emu:read16(0x04000008) }
    end)
    return ok and s or nil
end

local function await_ok(want)
    local s = io_state()
    if not s then return true end       -- 读不到就别卡死
    if want.dispcnt and s.dispcnt ~= want.dispcnt then return false end
    if want.bg0 and s.bg0 ~= want.bg0 then return false end
    return true
end

local function finish(fr)
    DONE = true
    emu:setKeys(0)
    log(string.format("done f=%d seq=%d", fr, SEQ))
    lg:close()
    os.exit(0)
end

callbacks:add("keysRead", function()
    if DONE then return end
    local fr = emu:currentFrame()
    if FRAME_BASE == nil then
        FRAME_BASE = fr
        log(string.format("[BASE] f=%d steps=%d need=%d timeout=%d",
                          fr, #STEPS, SETTLE_NEED, SETTLE_TIMEOUT))
    end

    if fr - FRAME_BASE > MAX_FRAMES then
        stop(1, string.format("[ERR] frame cap f=%d idx=%d/%d", fr, IDX, #STEPS))
        return
    end

    -- 开局：先抓一张（标题/版权画面本身的图也常常是真图）
    if IDX == 0 and PHASE == "settle" then
        PHASE = "pre"
        SETTLE_T = fr
        STABLE = 0
        LAST_FP = nil
        return
    end

    -- settle 阶段
    if PHASE == "settle" or PHASE == "pre" then
        local t = read_all()
        local fp = fingerprint(t)
        if LAST_FP and fp == LAST_FP then
            STABLE = STABLE + 1
        else
            STABLE = 0
            LAST_FP = fp
        end
        local elapsed = fr - SETTLE_T
        local got = STABLE >= SETTLE_NEED
        local timeout = elapsed >= SETTLE_TIMEOUT
        if got or timeout then
            UNSTABLE = (not got) and true or false
            -- 与上次落盘内容相同就不重复写（野外动画会一直变，但内容高度相似）
            if fp ~= LAST_DUMP_FP or SEQ == 0 then
                dump(read_all(), fr, UNSTABLE)
                LAST_DUMP_FP = fp
            else
                log(string.format("[SKIP] f=%d 内容与上次一致", fr))
            end
            if IDX >= #STEPS then
                finish(fr)
                return
            end
            IDX = IDX + 1
            local st = STEPS[IDX]
            if SEQ >= MAX_SHOT then
                log("[STOP] 达到 max_shot")
                finish(fr)
                return
            end
            if st.act == "WAIT" then
                SETTLE_T = fr
                STABLE = 0
                LAST_FP = nil
                PHASE = "settle"
            elseif st.act == "await" then
                PHASE = "await"
                SETTLE_T = fr
                STABLE = 0
            else
                MASK = keys_down(st.act)
                HOLD = st.n or 4
                PHASE = "hold"
                emu:setKeys(MASK)
            end
        end
        return
    end

    -- await 阶段：等 (DISPCNT, BG0CNT) 匹配；超时后照样往前走，不让流程卡死
    if PHASE == "await" then
        local st = STEPS[IDX]
        if await_ok(st.want) then
            log(string.format("[AWAIT] f=%d %s 命中", fr, st.tag or "?"))
            SETTLE_T = fr
            STABLE = 0
            LAST_FP = nil
            PHASE = "settle"
        elseif fr - SETTLE_T >= (SETTLE_TIMEOUT * 2) then
            local s = io_state() or {}
            log(string.format("[AWAIT] f=%d %s 超时 (dispcnt=%s bg0=%s 期望 %s/%s)",
                              fr, st.tag or "?",
                              tostring(s.dispcnt), tostring(s.bg0),
                              tostring(st.want.dispcnt), tostring(st.want.bg0)))
            SETTLE_T = fr
            STABLE = 0
            LAST_FP = nil
            PHASE = "settle"
        end
        return
    end

    if PHASE == "hold" then
        emu:setKeys(MASK)
        HOLD = HOLD - 1
        if HOLD <= 0 then
            PHASE = "release"
            HOLD = 3
            emu:setKeys(0)
        end
        return
    end

    if PHASE == "release" then
        emu:setKeys(0)
        HOLD = HOLD - 1
        if HOLD <= 0 then
            SETTLE_T = fr
            STABLE = 0
            LAST_FP = nil
            PHASE = "settle"
        end
        return
    end
end)

-- 兜底：keysRead 停摆也要退出而不是挂死
local LAST_TICK = 0
callbacks:add("frame", function()
    if DONE then return end
    local fr = emu:currentFrame()
    if LAST_TICK > 0 and fr - LAST_TICK > 6000 then
        stop(1, string.format("[ERR] keysRead 停摆 f=%d idx=%d/%d", fr, IDX, #STEPS))
    end
end)
