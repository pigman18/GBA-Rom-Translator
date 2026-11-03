-- ============================================================================
-- bot.lua — GBA 场景回放引擎（mGBA dev-build + Lua）
--
-- 由 bot/scenes/{gameId}/main.lua 经 dofile 载入（main.lua 只是衔接层）。
--
-- ── 契约（用户口径，逐条对应）──────────────────────────────────────────────
--   1) 场景存 bot/scenes/{gameId}/{scene}.lua，经 main.lua 执行
--   2) 截图落 bot/shoots/{gameId}/{scene}/{时间}/{origin|translated}/{number}.png
--   3) 两侧用**同一份 .sav**、非即时存档（savestate 基于内存，hook 改动不加载）
--   4) 对比截图判：已汉化 + 无撞 UI + 无乱码
--   5) 像素级判据由 verify.py 完成（本文件负责采集）
--
-- ════════════════════════════════════════════════════════════════════════════
-- 【2026-10-17 时序模型重写 —— 本文件的核心变更】
--
-- 旧模型（已废弃）：用**固定帧数**赌时序
--     api.wait(420) → A 长按 20 帧 → wait(500) → A 长按 20 帧 → wait(900)
--   这些数字是某台机器某份 ROM 上测出来的，换环境立刻漂。
--
--   实测反证（bot/shoots/POKEMON_RUBY_AXVJ00/options/20261016T015912_697134/）：
--     origin/005.png 与 translated/005.png 的 SHA-256 **完全相同**
--     （f9d0a71a00ae68ec0b39bf6bbbadff975e66a6ec4cc2a0cfed580a5777a69086），
--     画面是**博士开场**而非「设置」菜单 ⇒ 两侧根本没到目标场景，
--     而 run.py 照样把这 21 帧记成了一对一对的合法对照。
--   同时 005(opt_open) f=2243 与 006(opt_open_b) f=2244 是**相邻帧**，
--   画面根本没稳定就拍了。
--
-- 新模型 = **状态驱动 + 稳定优先**：
--   ★ 每一步结束后都进入 SETTLE（等画面连续 K 帧不变）才推进下一步。
--     于是两侧的「第 N 个 shot」必然对应**同一个界面状态**，与机器速度无关。
--     关键词：**等稳定，不等帧数**。
--   ★ 主循环放在 `frame` 回调而不是 `keysRead`：
--     keysRead 只在游戏**主动读输入**时触发，过场/淡入时可能长时间不触发，
--     步骤会停滞且超时也检测不到；frame 每帧必触发。
--     （旧注释担心的「双倍步进」只在**两边都推进**时发生，现在只有一边推进。）
--   ★ 两处硬证明：
--     ① prove：读档后于 EWRAM 搜索 .sav 里的玩家名字节 —— 命中即证明
--        「这份存档真的被加载进游戏了」，而不只是「文件哈希相同」。
--        顺带解出运行时 pos/location，与 .sav 里的位置比对。
--     ② 每张截图记录 `stable`（截图前连续稳定的帧数）+ `settled` 标志，
--        落进 index.csv / scene.log，供 run.py 判定「这确实是个静止界面」。
--
-- ── 环境变量（由 run.py 提供）───────────────────────────────────────────────
--   BOT_ROOT      bot/ 的绝对路径
--   BOT_GAME_ID   如 POKEMON_RUBY_AXVJ00
--   BOT_SCENE     场景名
--   BOT_SIDE      "origin" | "translated"
--   BOT_OUTPUT    本侧输出目录（绝对路径，落盘一律用它，不依赖 CWD）
--   BOT_SAV_PROOF 玩家名等「存档身份」字节的 hex（可选，用于读档证明）
--   BOT_SAV_POS   "MapName:x:y"（可选，用于位置比对）
--   可选调参：BOT_SETTLE_NEED(默认6) BOT_SETTLE_TIMEOUT(默认900)
--
-- ── 每张截图产出（四件套 + 索引）────────────────────────────────────────────
--   NNN.png         整幅 240×160（纯序号，两侧同号为一对）
--   NNN.vram.bin    0x06000000..0x06018000（96KB：tile + tilemap + OBJ）
--   NNN.pal.bin     0x05000000..0x05000400（1KB）
--   NNN.ram.bin     EWRAM 0x02000000+0x40000 | IWRAM 0x03000000+0x8000（共 288KB）
--                   布局以 manifest.dumps.ram 为准（schema 3 起；schema 2 是
--                   EWRAM 0x02020000+0x20000 | IWRAM+0x800，共 130KB）
--   scene.log       每帧/每步的可读快照（DISPCNT/BGxCNT/窗结构/settle 结果）
--   index.csv       机器可读索引（末列 stable，见上）
--
-- 结束必须写 `done f=<帧号> idx=<n>/<总>`（run.py 靠这行判断完成）
-- ============================================================================

local ROOT     = assert(os.getenv("BOT_ROOT"),     "BOT_ROOT missing")
local game     = assert(os.getenv("BOT_GAME_ID"),  "BOT_GAME_ID missing")
local scene    = assert(os.getenv("BOT_SCENE"),    "BOT_SCENE missing")
local side     = assert(os.getenv("BOT_SIDE"),     "BOT_SIDE missing")
local SHOTDIR  = assert(os.getenv("BOT_OUTPUT"),   "BOT_OUTPUT missing")

local SAV_PROOF = os.getenv("BOT_SAV_PROOF") or ""   -- hex 字节串
local SAV_POS   = os.getenv("BOT_SAV_POS")   or ""   -- "MapName:x:y"

-- settle 调参：连续多少帧画面不变算稳定 / 一次 settle 最多等多少帧
local SETTLE_NEED    = tonumber(os.getenv("BOT_SETTLE_NEED")) or 6
local SETTLE_TIMEOUT = tonumber(os.getenv("BOT_SETTLE_TIMEOUT")) or 900

-- ★ 严格/宽松双阶段（2026-10-17，修野外永不稳定的问题）
-- 野外地图自带持续动画（水面波纹、草丛摆动、云影），VRAM 的 tile 数据
-- 每帧都在变 ⇒ 「VRAM 逐字节全等」这种严格判据在野外**永远不成立**，
-- 实测 3 张截图全部 settled=NO、stable=0/1，还白等 12 次 900 帧超时。
-- 但这类动画**不改调色板、也不改 DISPCNT/BGxCNT**，所以：
--   前 SOFT_AFTER 帧：严格（VRAM+PAL+IO 全等）—— 静态界面（菜单/对话框）走这条，精确
--   之后自动降级：宽松（只比 PAL+IO，忽略 VRAM 内容）—— 动画场景走这条
-- 降级会记进日志与 index.csv（soft 列），验收时可据此区别对待。
local SOFT_AFTER = tonumber(os.getenv("BOT_SETTLE_SOFT_AFTER")) or 60

-- 只允许安全标识符，防路径穿越
local function safe_id(s)
    return type(s) == "string" and s:match("^[A-Za-z0-9_%-]+$") ~= nil
end
assert(safe_id(game) and safe_id(scene), "unsafe game/scene identifier")
assert(side == "origin" or side == "translated", "invalid ROM side")

local function slash(s) return (s:gsub("\\", "/"):gsub("/+$", "")) .. "/" end
ROOT, SHOTDIR = slash(ROOT), slash(SHOTDIR)

-- ---- 落盘文件 --------------------------------------------------------------
local lf  = assert(io.open(SHOTDIR .. "scene.log", "w"), "cannot open scene.log")
local csv = assert(io.open(SHOTDIR .. "index.csv", "w"), "cannot open index.csv")
local function log(s) lf:write(s .. "\n"); lf:flush() end
local function stop(code, message)
    log(message)
    lf:close(); csv:close()
    os.exit(code)
end

-- ---- 载入场景步骤 ----------------------------------------------------------
local scene_path = ROOT .. "scenes/" .. game .. "/" .. scene .. ".lua"
local ok, STEPS = pcall(dofile, scene_path)
if not ok or type(STEPS) ~= "table" then
    stop(1, "[ERR] scene load failed: " .. tostring(STEPS))
end

local KEYBIT = { A=0, B=1, SELECT=2, START=3, RIGHT=4, LEFT=5, UP=6, DOWN=7, R=8, L=9 }
local MAX_FRAMES = 20000000

-- ★ SaveBlock1 相对 SaveBlock2 的偏移（权威符号表实证）：
--     02024ea4 g 00000890 gSaveBlock2
--     02025734 g 00003ac0 gSaveBlock1
--   ⚠ 必须声明在**文件顶部**：settle_step 里的 await_pos 分支要用它，
--     而 Lua 的 local 作用域从声明处才生效 —— 原先它声明在 settle_step
--     **之后**，导致 settle_step 里看到的是 nil 全局，直接报
--     "attempt to perform arithmetic on a nil value (global 'SB1_DELTA')"，
--     整个模拟器卡死到超时。
local SB1_DELTA = 0x890

-- prove 命中后记下 SaveBlock2 的运行时地址，供 walk/await_pos 读坐标使用
SB2_RUNTIME = nil

-- ---- 步骤表校验 ------------------------------------------------------------
local total_frames, shots = 0, 0
local names = {}
for i, st in ipairs(STEPS) do
    if type(st) ~= "table" or type(st.act) ~= "string" then
        stop(1, string.format("[ERR] invalid step %d", i))
    end
    if st.act == "shot" then
        if st.n ~= nil and st.n ~= 0 then
            stop(1, string.format("[ERR] shot step %d n must be zero", i))
        end
        local nm = st.name or "shot"
        if not safe_id(nm) then
            stop(1, string.format("[ERR] invalid shot name at step %d", i))
        end
        if names[nm] then stop(1, "[ERR] duplicate shot name: " .. nm) end
        names[nm] = true
        shots = shots + 1
    elseif st.act == "talk" then
        -- ★ 对话闸门：按 A，然后等**已验证的真实文本窗口**出现。
        --   n = 等待窗口的超时帧数；press = A 按住帧数；soft = 超时后继续。
        --   为什么需要它：旧版 dialogue 场景根本没触发对话（原地按 A 打空），
        --   但截图照样被记成合法对照 —— 场景「静默无效」是采集里最贵的错。
        if st.n ~= nil and (type(st.n) ~= "number" or st.n < 1) then
            stop(1, string.format("[ERR] talk step %d bad n", i))
        end
        total_frames = total_frames + (st.n or 300)
    elseif st.act == "wait" or KEYBIT[st.act] ~= nil then
        if type(st.n) ~= "number" or st.n ~= math.floor(st.n) or st.n < 1 then
            stop(1, string.format("[ERR] invalid frame count at step %d", i))
        end
        total_frames = total_frames + st.n
    elseif st.act == "prove" then
        -- 瞬时步骤，无帧数
    elseif st.act == "await" then
        -- 状态驱动等待：等「画面稳定 **且** 内存条件满足」。
        -- n = 超时帧数；addr/value（+可选 addr2/value2）= 目标界面特征。
        if type(st.n) ~= "number" or st.n < 1 then
            stop(1, string.format("[ERR] await step %d needs n=timeout", i))
        end
        if type(st.addr) ~= "number" or type(st.value) ~= "number" then
            stop(1, string.format("[ERR] await step %d needs addr/value", i))
        end
        total_frames = total_frames + st.n
    elseif st.act == "walk" then
        -- ★ 走一格并等坐标对齐：等待期间持续按住 dir。
        -- n = 超时帧数；dir = 方向；x/y = 目标格；soft = 超时后是否降级继续。
        if type(st.dir) ~= "string" or KEYBIT[st.dir] == nil then
            stop(1, string.format("[ERR] walk step %d bad dir", i))
        end
        if type(st.x) ~= "number" or type(st.y) ~= "number" then
            stop(1, string.format("[ERR] walk step %d needs x/y", i))
        end
        total_frames = total_frames + (st.n or 600)
    elseif st.act == "await_pos" then
        -- ★ 等游戏内坐标到达目标格（移动场景对齐用）。
        -- n = 超时帧数；x/y = 目标格坐标；soft = 超时后是否降级继续。
        if type(st.n) ~= "number" or st.n < 1 then
            stop(1, string.format("[ERR] await_pos step %d needs n=timeout", i))
        end
        if type(st.x) ~= "number" or type(st.y) ~= "number" then
            stop(1, string.format("[ERR] await_pos step %d needs x/y", i))
        end
        total_frames = total_frames + st.n
    else
        stop(1, string.format("[ERR] unknown act at step %d: %s", i, st.act))
    end
end
if shots == 0 then stop(1, "[ERR] scene has no shots") end
if total_frames * 3 > MAX_FRAMES then
    stop(1, string.format("[ERR] scene exceeds frame limit (%d)", total_frames * 3))
end

-- ---- 字节读取工具 ----------------------------------------------------------
local function u8(s, o)  return s:byte(o + 1) end
local function u16(s, o) return s:byte(o + 1) | (s:byte(o + 2) << 8) end
local function u32(s, o)
    return s:byte(o + 1) | (s:byte(o + 2) << 8)
         | (s:byte(o + 3) << 16) | (s:byte(o + 4) << 24)
end
local function s8v(b) return b > 127 and (b - 256) or b end
local function hexs(s, n)
    local t = {}
    for i = 1, n do t[#t + 1] = string.format("%02X", s:byte(i)) end
    return table.concat(t, " ")
end
local function wr(path, data)
    local f = assert(io.open(path, "wb"))
    assert(f:write(data))
    assert(f:close())
end

-- ---- 窗结构扫描（AXVJ TextPrinter 布局）------------------------------------
-- +0 tpl(u32) +4 state(u16) +A textMode +B fontNum +10 text(u32) +14 index(u16)
-- +16 TILE_BASE +18 TILE_OFF +1A curX +1B curTX +1C curY +1D curTY
-- 扫描范围含 IWRAM（文本可能指向 IWRAM 工作区，历史踩坑：只扫 EWRAM 会漏窗）
--
-- ★★ 2026-10-18：加**真实性校验**（见 win_is_real）。
--   裸扫 struct 的假阳性率高得离谱：实测 bag_open 一帧扫出 7 个「窗口」，
--   只有 1 个是真的（其余 tpl 指向随机 ROM 数据，charBase=79/100/186 这种
--   明显越界的值也照样通过旧判据）。
--   这条校验同时也是 `talk` 步骤能成立的唯一基础 —— 没有它，
--   「文本窗口出现」这个信号全是噪声，talk 会 100% 假命中。
local function bg_layers()
    -- 只取**已开启**的 BG 图层；DISPCNT bit8+b 是 BGb enable
    local dis = emu:read16(0x04000000)
    local t = {}
    for b = 0, 3 do
        if ((dis >> (8 + b)) & 1) == 1 then
            local v = emu:read16(0x04000008 + b * 2)
            t[#t + 1] = {
                b = b,
                cb = (v >> 2) & 3,
                sb = (v >> 8) & 0x1F,
                bpp8 = ((v >> 7) & 1) == 1,
            }
        end
    end
    return t, dis
end

-- 窗口 tpl 页里记录的 (charBase, tileData, tilemap) 是否**真的**对得上
-- 某个已开启 BG 图层的寄存器配置。对得上 ⇒ 这个窗口确实在往屏幕上写字。
--
-- 实测样本（bag_open，唯一真窗口）：tpl=0x081BB544 charBase=2
--   tileData=0x06008000 tilemap=0x0600F800
--   BG0CNT=1F08 ⇒ charBase=2、screenBase=31
--   ⇒ 0x06000000 + 2*0x4000 = 0x06008000 ✓
--   ⇒ 0x06000000 + 31*0x800 = 0x0600F800 ✓
local function win_is_real(w)
    local page = emu:readRange(w.tpl, 0x14)
    if not page or #page < 0x14 then return false end
    local cb  = u8(page, 1)
    local td  = u32(page, 0x0C)
    local tm  = u32(page, 0x10)
    local layers = bg_layers()
    for _, L in ipairs(layers) do
        local want_td = 0x06000000 + cb * (L.bpp8 and 0x8000 or 0x4000)
        local want_tm = 0x06000000 + L.sb * 0x800
        if cb == L.cb and td == want_td and tm == want_tm then
            return true, L.b
        end
    end
    return false
end

-- real_only=true ⇒ 只要通过 win_is_real 的（默认用它）
local function scan_wins(real_only)
    if real_only == nil then real_only = true end
    local found = {}
    local ranges = {
        { 0x02020000, 0x18000 },
        { 0x03000000, 0x8000 },
    }
    for _, r in ipairs(ranges) do
        local blob = emu:readRange(r[1], r[2])
        if blob and #blob >= r[2] then
            local o = 0
            while o + 0x1E <= r[2] do
                local tpl = u32(blob, o)
                if tpl >= 0x08000000 and tpl < 0x0A000000 then
                    local txt = u32(blob, o + 0x10)
                    local okp = (txt >= 0x08000000 and txt < 0x0A000000)
                             or (txt >= 0x02000000 and txt < 0x02040000)
                             or (txt >= 0x03000000 and txt < 0x03008000)
                    local tm  = u8(blob, o + 0x0A)
                    local fn  = u8(blob, o + 0x0B)
                    local st  = u16(blob, o + 0x04)
                    local idx = u16(blob, o + 0x14)
                    local tb  = u16(blob, o + 0x16)
                    if okp and tm <= 7 and fn <= 7 and st < 0x10
                       and idx < 0x400 and tb < 0x400 then
                        local w = {
                            addr = r[1] + o, tpl = tpl, txt = txt,
                            tm = tm, fn = fn, st = st, idx = idx, tb = tb,
                            tof = u16(blob, o + 0x18),
                            cx  = u8(blob, o + 0x1A), ctx = u8(blob, o + 0x1B),
                            cy  = u8(blob, o + 0x1C), cty = u8(blob, o + 0x1D),
                        }
                        if real_only then
                            w.real, w.bg = win_is_real(w)
                        end
                        if (not real_only) or w.real then
                            found[#found + 1] = w
                        end
                    end
                end
                o = o + 4
            end
        end
    end
    return found
end

local function dump_win(w)
    local lines = {}
    lines[#lines + 1] = string.format(
        "[win] 0x%08X state=%d textMode=%d fontNum=%d%s"
        .. " TILE_BASE=0x%04X TILE_OFF=0x%04X"
        .. " curX=%d curTX=%d curY=%d curTY=%d index=%d",
        w.addr, w.st, w.tm, w.fn,
        w.real and string.format(" BG%d", w.bg or -1) or " (未校验)",
        w.tb, w.tof, w.cx, w.ctx, w.cy, w.cty, w.idx)
    local raw = emu:readRange(w.addr, 0x28)
    if raw and #raw >= 0x28 then
        lines[#lines + 1] = string.format("  raw win: %s", hexs(raw, 0x28))
        -- 钩子把「最近一次绘字的真实地址」写在 0x0203FFC0（见 text_render.c）。
        -- 直接读它，就不用再猜 BGxCNT / charblock。
        local dbg = emu:readRange(0x0203FFC0, 48)
        if dbg and #dbg >= 48 then
            lines[#lines + 1] = string.format(
                "  chsdbg: charb=0x%08X tmb=0x%08X base_tile=%d col=%d row=%d cx=%d ctx0=%d tb=%d gidx=%d font=%d glyphptr=0x%08X phase=%d",
                u32(dbg, 0), u32(dbg, 4), u32(dbg, 8), u32(dbg, 12),
                u32(dbg, 16), u32(dbg, 20), u32(dbg, 24), u32(dbg, 28),
                u32(dbg, 32), u32(dbg, 36), u32(dbg, 40), u32(dbg, 44))
        end
        -- 把当前文本指针处的前 12 字节读出来：用来判断这个窗口到底在打印
        -- 原始日文（JP 字节）还是我们的 F9 编码（F9 80 hi lo / F9 00 lead trail）。
        local tp = u32(raw, 0x10)
        if tp and tp > 0x08000000 and tp < 0x0A000000 then
            local tb = emu:readRange(tp, 12)
            if tb and #tb >= 12 then
                lines[#lines + 1] = string.format("  text@0x%08X: %s", tp, hexs(tb, 12))
            end
        end
    end
    local t = emu:readRange(w.tpl, 0x14)
    if t and #t >= 0x14 then
        lines[#lines + 1] = string.format(
            "  tpl@0x%08X: charBase=%d tileData=0x%08X tilemap=0x%08X",
            w.tpl, u8(t, 1), u32(t, 0x0C), u32(t, 0x10))
    end
    if w.txt then
        local b = emu:readRange(w.txt + (w.idx > 8 and w.idx - 8 or 0), 24)
        if b and #b >= 24 then
            lines[#lines + 1] = string.format("  text@0x%08X index=%d: %s",
                                              w.txt, w.idx, hexs(b, 24))
        end
    end
    return table.concat(lines, "\n")
end

-- ============================================================================
-- ★ 画面稳定检测（新模型的核心）
-- ----------------------------------------------------------------------------
-- 读三段状态做**逐字节比较**（Lua 的字符串 == 是 C 层 memcmp，很快）：
--   VRAM 96KB（tile + tilemap + OBJ tile）—— 文字/图形重绘都在这里
--   PAL   1KB                            —— 调色板/淡入淡出
--   IO  0x60B                            —— DISPCNT/BGxCNT/卷动/窗口
-- 注意 **不含 OAM(0x07000000)**：NPC 走路、角色转身只改 OAM，
-- 不应被判成「画面还在变」，否则野外场景永远 settle 不了。
-- ============================================================================
local VRAM_ADDR, VRAM_LEN = 0x06000000, 0x18000
local PAL_ADDR,  PAL_LEN  = 0x05000000, 0x400
local IO_ADDR,   IO_LEN   = 0x04000000, 0x60

-- ★ 显示相关 IO 寄存器**白名单**（2026-10-17，修 settled 永远为 0 的问题）
-- ⚠ 绝不能整块读 0x04000000..0x60：那块里混着
--     VCOUNT(0x04000006)  —— 每帧递增
--     DISPSTAT / 声音寄存器 —— 每帧变化
--   只要它们在指纹里，「逐字节全等」就永远不成立。
--   实测症状：stable 恒为 0，连宽松判据都判成「PAL/IO 仍在变」，
--   于是每张截图都白等 900 帧超时、settled 永远是 NO。
--   这里只读**画面构成真正依赖**的寄存器。
local IO_REGS = {
    0x04000000,                                     -- DISPCNT
    0x04000008, 0x0400000A, 0x0400000C, 0x0400000E, -- BG0CNT..BG3CNT
    0x04000010, 0x04000012, 0x04000014, 0x04000016, -- BG0/BG1 HOFS,VOFS
    0x04000018, 0x0400001A, 0x0400001C, 0x0400001E, -- BG2/BG3 HOFS,VOFS
    0x04000040, 0x04000042, 0x04000044, 0x04000046, -- WIN0H/V, WIN1H/V
    0x04000048, 0x0400004A,                         -- WININ, WINOUT
    0x04000050, 0x04000052, 0x04000054,             -- BLDCNT, BLDALPHA, BLDY
}

local function read_io()
    local t = {}
    for i = 1, #IO_REGS do
        local v = emu:read16(IO_REGS[i])
        t[i] = string.char(v & 0xFF, (v >> 8) & 0xFF)
    end
    return table.concat(t)
end

local function blit()
    return emu:readRange(VRAM_ADDR, VRAM_LEN),
           emu:readRange(PAL_ADDR,  PAL_LEN),
           read_io()
end

-- settle 状态机
local S = {
    active   = false,   -- 是否正在等稳定
    stable   = 0,       -- 已连续稳定的帧数
    start_fr = 0,       -- 进入 settle 的帧号
    last_v = nil, last_p = nil, last_i = nil,
    timed_out = false,  -- 本次 settle 是否超时
    soft = false,       -- 本次 settle 是否走了宽松判据（忽略 VRAM 动画）
    why = "",           -- 进入 settle 的原因（写日志用）
    -- await 附加条件：稳定之后还要满足它才算到位（见 settle_step）
    await_addr = nil, await_val = nil, await_addr2 = nil, await_val2 = nil,
    await_to = 0,
    -- await_pos：等游戏内坐标到达目标格（移动场景对齐用）
    pos_sb2 = nil, pos_x = 0, pos_y = 0,
    -- walk：等待坐标期间持续按住的方向键掩码（nil = 不按键）
    walk_mask = nil,
    -- walk 的按键持续帧数：按满后自动松手，再等坐标停稳
    walk_frames = 0,
    -- 坐标比较轴："y" / "x" / nil（nil = 两轴都必须精确相等）
    pos_axis = nil,
    -- 上一帧读到的坐标（判「停稳」用）
    last_px = nil, last_py = nil,
}

-- 请求进入 settle（下一步是该步骤的动作）。
-- await_addr/await_val（可选）：稳定之后必须再满足该内存条件，否则继续等。
-- pos_sb2/pos_x/pos_y（可选）：等 SaveBlock1 的 pos 到达目标格。
-- walk_mask（可选）：等待期间按住该方向键；walk_frames 帧后自动松手。
local function settle_begin(reason, fr, await_addr, await_val, await_to,
                            await_addr2, await_val2,
                            pos_sb2, pos_x, pos_y, walk_mask, walk_frames,
                            pos_axis)
    S.active, S.stable, S.start_fr = true, 0, fr
    S.last_v, S.last_p, S.last_i = nil, nil, nil
    S.timed_out, S.soft, S.why = false, false, reason or ""
    S.await_addr, S.await_val = await_addr, await_val
    S.await_addr2, S.await_val2 = await_addr2, await_val2
    S.await_to = await_to or SETTLE_TIMEOUT
    S.pos_sb2, S.pos_x, S.pos_y = pos_sb2, pos_x or 0, pos_y or 0
    S.walk_mask = walk_mask
    S.walk_frames = walk_frames or 0
    S.pos_axis = pos_axis
    S.last_px, S.last_py = nil, nil
    S.last_move_fr = fr
    S.walk_released = false
    -- talk：等「真实文本窗口」出现
    S.talk_to = SETTLE_TIMEOUT
end

-- 推进步骤（在 frame 回调里被调用，见主循环）
local advance      -- 前向声明

-- await：特征需要**连续满足**多少帧才算到位（防抖动，不是防动画）
local AWAIT_NEED = 4

-- 每帧调用：返回 true 表示「还在等，本次不要做别的」
--
-- ★ 两条路径必须分开（实测教训，2026-10-17）：
--   settle 路径：判「画面稳定」—— VRAM/PAL/IO 逐字节不变。
--   await  路径：判「内存特征」—— **绝不能要求画面稳定**。
--     标题画面自带 logo 闪光/闪烁的 PUSH START，VRAM 每帧都在变，
--     上一次实现把 await 条件挂在「稳定之后」检查，结果
--     stable 永远是 0、条件根本没机会被查，一路等到超时。
--     目标界面有动画是常态，所以 await 只看特征连续满足。
local function settle_step(fr)
    if not S.active then return false end

    -- ── await_pos 路径：等「游戏内坐标」到达目标格 ───────────────────────
    -- ★★ 这是移动场景（走路/进草丛/遇敌）能对齐的**唯一正确解法**。
    --    实测教训：从同一存档同一帧出发，两侧盲走 N 步之后画面相似度
    --    会从 1.000 掉到 0.063 —— 因为走路是逐帧累积的过程，按键时序差
    --    一帧，角色就走到不同格。await(dispcnt) 只能判「界面变了」，
    --    判不了「站在哪一格」。
    --    坐标来源：运行时 SaveBlock1 = SaveBlock2 + 0x890（符号表实证），
    --    SaveBlock1+0x00 是 struct Coords16 pos { s16 x; s16 y; }。
    if S.pos_sb2 ~= nil then
        local pos = emu:readRange(S.pos_sb2 + SB1_DELTA, 4)
        if pos and #pos >= 4 then
            local x = u16(pos, 0); if x > 32767 then x = x - 65536 end
            local y = u16(pos, 2); if y > 32767 then y = y - 65536 end

            -- ★★★ 坐标语义（三轮实测才定下来，勿再改）：
            --   `pos` 就是**格子坐标**，不是像素！
            --   证据：起点 prove 报 (68,7)（与存档里的 Route118 位置一致），
            --   按住 DOWN 之后读到 (68,14) —— x 保持 68，y 单调增。
            --   我先前误判成像素坐标（拿 68*16+8=1096 去比），
            --   于是永远不相等，卡死两轮。
            --
            -- ★★★ walk 的按键策略（2026-10-18 重写）：**持续按住 + 到位即松手**
            --
            --   旧策略 = 「按住固定 walk_frames 帧 → 松手 → 等停稳」，它把
            --   「按键时长」和「走几格」硬绑在一起，于是同一段脚本换个方向
            --   或换个起点就得重新调参；调大了冲过头，调小了走不到。
            --
            --   新策略每帧读坐标再决定按键：
            --     · 没到位 ⇒ 一直按住方向（Gen3 按住即连续走，一格约 16 帧）
            --     · 一到位 ⇒ **当帧松手**（这是关键，才不会冲过目标格）
            --     · 松手后坐标连续 AWAIT_NEED 帧不变 ⇒ 真停稳
            --     · 按住却 40 帧坐标都没变 ⇒ 被 NPC/墙挡住（blocked）
            local arrived
            if S.pos_axis == "y" then
                arrived = (x == S.pos_x) and (y >= S.pos_y)
            elseif S.pos_axis == "x" then
                arrived = (y == S.pos_y) and (x >= S.pos_x)
            else
                arrived = (x == S.pos_x and y == S.pos_y)
            end

            if x ~= S.last_px or y ~= S.last_py then
                S.last_move_fr = fr          -- 这一步真的移动了
            end

            if S.walk_mask ~= nil and not S.walk_released then
                if arrived then
                    emu:setKeys(0)
                    S.walk_released = true
                else
                    emu:setKeys(S.walk_mask)
                end
            end

            -- 等「坐标连续 AWAIT_NEED 帧不变」= 真的停稳了
            if S.last_px == x and S.last_py == y then
                S.stable = S.stable + 1
            else
                S.stable = 0
            end
            S.last_px, S.last_py = x, y

            -- 必须：已松手 + 停稳 + 到位
            if S.walk_released and S.stable >= AWAIT_NEED and arrived then
                S.active = false
                log(string.format(
                    "[AWAIT_POS] hit f=%d grid=(%d,%d) want=(%d,%d) span=%d%s",
                    fr, x, y, S.pos_x, S.pos_y, fr - S.start_fr,
                    S.walk_mask ~= nil and " (walk)" or ""))
                return false
            end

            -- 被挡住：还按着键，但 40 帧没挪过位置（走一格约 16 帧）
            local stuck = (S.walk_mask ~= nil) and (not arrived)
                          and (fr - (S.last_move_fr or fr) > 40)
            if stuck then
                S.active, S.timed_out = false, true
                emu:setKeys(0)
                log(string.format(
                    "[AWAIT_POS] BLOCKED f=%d want=(%d,%d) got=(%d,%d) span=%d"
                    .. "  ⇒ 被挡住/撞墙，40 帧没挪过格",
                    fr, S.pos_x, S.pos_y, x, y, fr - S.start_fr))
                return false
            end

            if fr - S.start_fr > S.await_to then
                S.active, S.timed_out = false, true
                if S.walk_mask ~= nil then emu:setKeys(0) end
                log(string.format(
                    "[AWAIT_POS] TIMEOUT f=%d want=(%d,%d) got=(%d,%d) span=%d"
                    .. " stable=%d  ⇒ 没走到目标格",
                    fr, S.pos_x, S.pos_y, x, y, fr - S.start_fr, S.stable))
                return false
            end
            return true
        end
    end

    -- ── await 路径 ──────────────────────────────────────────────────────
    if S.await_addr ~= nil then
        local cur = emu:read16(S.await_addr)
        local cur2 = S.await_addr2 and emu:read16(S.await_addr2) or nil
        local hit = (cur == S.await_val)
                and (S.await_addr2 == nil or cur2 == S.await_val2)
        if hit then
            S.stable = S.stable + 1
            if S.stable >= AWAIT_NEED then
                S.active = false
                log(string.format("[AWAIT] hit f=%d reason=%s span=%d",
                                  fr, S.why, fr - S.start_fr))
                return false
            end
        else
            if S.stable > 0 then
                log(string.format("[AWAIT] lost f=%d want=0x%04X@%08X got=0x%04X",
                                  fr, S.await_val, S.await_addr, cur))
            end
            S.stable = 0
        end

        if fr - S.start_fr > S.await_to then
            S.active, S.timed_out = false, true
            log(string.format(
                "[AWAIT] TIMEOUT f=%d reason=%s want=0x%04X@%08X"
                .. (S.await_addr2 and " want2=0x%04X@%08X" or "")
                .. " got=0x%04X span=%d  ⇒ 没到达目标界面",
                fr, S.why, S.await_val, S.await_addr,
                (S.await_val2 or 0), (S.await_addr2 or 0),
                cur, fr - S.start_fr))
            return false
        end
        return true
    end

    -- ── settle 路径 ─────────────────────────────────────────────────────
    local v, p, i = blit()
    local span = fr - S.start_fr
    local strict = span < SOFT_AFTER
    local same
    if v == nil or p == nil or i == nil or S.last_v == nil then
        same = false
    elseif strict then
        same = (S.last_v == v and S.last_p == p and S.last_i == i)
    else
        -- 宽松阶段：忽略 VRAM 的内容动画，只看调色板与显示寄存器
        same = (S.last_p == p and S.last_i == i)
    end
    if same then S.stable = S.stable + 1 else S.stable = 0 end
    S.last_v, S.last_p, S.last_i = v, p, i

    if S.stable >= SETTLE_NEED then
        S.active, S.soft = false, (not strict)
        log(string.format("[SETTLE] ok f=%d reason=%s stable=%d span=%d mode=%s",
                          fr, S.why, S.stable, span,
                          strict and "strict" or "soft(忽略VRAM动画)"))
        return false
    end

    if span > SETTLE_TIMEOUT then
        S.active, S.timed_out = false, true
        log(string.format(
            "[SETTLE] TIMEOUT f=%d reason=%s stable=%d span=%d"
            .. "  ⇒ 连宽松判据都不稳（PAL/IO 仍在变），按超时继续",
            fr, S.why, S.stable, span))
        return false
    end

    return true
end

-- ============================================================================
-- ★ 读档证明（prove）
-- ----------------------------------------------------------------------------
-- 只比 .sav 的 SHA-256 只能证明「两侧用的是同一份文件」，
-- **不能证明这份存档真的被游戏加载了** —— 实测就出现过两侧都冷启动、
-- 停在博士开场却被记成合法对照的情况。
--
-- 做法：run.py 从 .sav 解出「存档身份字节」（SaveBlock2 开头的玩家名等）
-- 传进来，这里在 EWRAM(256KB) + IWRAM(32KB) 里原样搜索它。
--   命中 ⇒ 存档确实进了内存 ⇒ 读档成功。
--   未命中 ⇒ 明确报错，不产生任何对照。
-- 顺带：SaveBlock1 就在 SaveBlock2 之后 0x890 处（权威符号表
--   02024ea4 g 00000890 gSaveBlock2 / 02025734 g 00003ac0 gSaveBlock1），
--   于是可以解出**运行时**的 pos/location，与 .sav 里的位置对比。
-- ============================================================================
local function hex_to_bytes(h)
    local out = {}
    for pair in h:gmatch("%x%x") do out[#out + 1] = string.char(tonumber(pair, 16)) end
    return table.concat(out)
end

local function find_in(addr, len, needle)
    local blob = emu:readRange(addr, len)
    if not blob then return nil end
    local at = string.find(blob, needle, 1, true)     -- plain find
    if at then return addr + at - 1 end
    return nil
end

local function do_prove(fr)
    if SAV_PROOF == "" then
        log("[PROVE] skip (no BOT_SAV_PROOF)")
        return true
    end
    local needle = hex_to_bytes(SAV_PROOF)
    if #needle < 4 then
        log("[PROVE] skip (needle too short)")
        return true
    end

    local sb2 = find_in(0x02000000, 0x40000, needle)      -- 全 EWRAM 256KB
    if not sb2 then sb2 = find_in(0x03000000, 0x8000, needle) end  -- IWRAM 兜底

    if not sb2 then
        log(string.format(
            "[PROVE] FAIL f=%d needle=%s ⇒ 存档**没有被加载**（内存里找不到"
            .. "存档身份字节）。本场景对照无效，拒绝产出截图。",
            fr, SAV_PROOF))
        return false
    end

    -- SaveBlock1 = SaveBlock2 + 0x890
    local sb1 = sb2 + SB1_DELTA
    SB2_RUNTIME = sb2                     -- 供 await_pos 读坐标
    local head = emu:readRange(sb1, 16)
    local pos_desc = "?"
    if head and #head >= 8 then
        local x = u16(head, 0) ; if x > 32767 then x = x - 65536 end
        local y = u16(head, 2) ; if y > 32767 then y = y - 65536 end
        local mg = s8v(u8(head, 4))
        local mn = s8v(u8(head, 5))
        pos_desc = string.format("pos=(%d,%d) loc=%d:%d", x, y, mg, mn)
    end

    log(string.format(
        "[PROVE] OK f=%d sb2=0x%08X sb1=0x%08X %s sav_pos=%s"
        .. " ⇒ 存档已加载并可用于两侧对照",
        fr, sb2, sb1, pos_desc, SAV_POS ~= "" and SAV_POS or "-"))
    return true
end

-- ---- 单次快照 --------------------------------------------------------------
local SEQ = 0

-- ok = 截图前是否真的稳定（严格或宽松都算稳定；false = 超时强拍的过渡帧）
local function snapshot(fr, st, stable_n, ok)
    SEQ = SEQ + 1
    local name = st.name or "shot"
    local number = string.format("%03d", SEQ)
    local base = SHOTDIR .. number

    -- ★ 2026-10-21 修正顺序：必须**先读内存再截图**。
    -- 实测证据：font_capture 的 007(menu_top).vram 与 008(closed).vram 相同率 98.7%，
    -- 而 001(overworld) 与 007 相同率 95.5% —— 说明旧顺序（先 screenshot 再 readRange）
    -- 读到的 VRAM 已经是**下一帧/菜单关闭后**的状态，与 PNG 不同步。
    -- 这直接导致 T3 在 VRAM 里找不到字模。
    local vram = emu:readRange(0x06000000, 0x18000)
    local pal  = emu:readRange(0x05000000, 0x400)
    -- 0x04000000..0x04000060：DISPCNT/DISPSTAT/VCOUNT/BGxCNT/BGxHOFS/BGxVOFS/WIN*/BLDCNT。
    -- 离线合成器（work/compose.py）需要这些寄存器才能知道每层 charBase/screenBase/尺寸，
    -- 否则只能靠猜。
    local io   = emu:readRange(0x04000000, 0x60)
    -- EWRAM **全量** 0x02000000+0x40000，IWRAM **全量** 0x03000000+0x8000。
    -- 2026-10-22 修正：原来 EWRAM 从 0x02020000 起（缺低 128KB）、IWRAM 只 0x800。
    -- 缺口导致两类东西看不见：
    --   ① 低半 EWRAM 里的结构（窗口/打印器的候选位置）；
    --   ② IWRAM 0x03000800 之外的运行时状态。
    -- 布局由 manifest.dumps.ram 声明（schema 3），离线读取方不要再按长度猜。
    local ew   = emu:readRange(0x02000000, 0x40000)
    local iw   = emu:readRange(0x03000000, 0x8000)
    local oam  = emu:readRange(0x07000000, 0x400)

    emu:screenshot(base .. ".png")

    if vram then wr(base .. ".vram.bin", vram) end
    if pal  then wr(base .. ".pal.bin",  pal)  end
    if io   then wr(base .. ".io.bin",   io)   end
    if ew and iw then wr(base .. ".ram.bin", ew .. iw) end
    -- OAM（0x07000000，1024B）：判断文字是否走 OBJ（sprite）渲染。
    -- VRAM 里找不到假名字模时，这是关键判据。
    if oam then wr(base .. ".oam.bin", oam) end

    local dispcnt = emu:read16(0x04000000)
    log(string.format("[SHOT %03d] name=%s f=%d dispcnt=%04X stable=%d settled=%s",
                      SEQ, name, fr, dispcnt, stable_n,
                      ok and (S.soft and "soft" or "yes") or "NO(超时强拍)"))
    local bg = {}
    for b = 0, 3 do
        bg[b] = emu:read16(0x04000008 + b * 2)
        local v = bg[b]
        log(string.format(
            "BG%dCNT=%04X charBase=%d screenBase=%d pri=%d %s",
            b, v, (v >> 2) & 3, (v >> 8) & 0x1F, v & 3,
            ((v >> 7) & 1) == 1 and "8bpp" or "4bpp"))
    end
    for _, w in ipairs(scan_wins()) do
        log(dump_win(w))
    end
    -- BOT_DUMP_ALLWINS=1：把**未通过 BG 真实性校验**的窗口也吐出来。
    -- 用途：战斗血条名/Lv 走 textMode==2 的「指针缓冲」打印器（tpl.tilemap==0），
    -- 它不往 tilemap 写表项，win_is_real 恒假 ⇒ 默认日志里看不到它。
    -- 排查 tm2 槽位问题时必须能看到 win[0x20](tileData 缓冲指针) 与 curTX。
    if os.getenv("BOT_DUMP_ALLWINS") == "1" then
        for _, w in ipairs(scan_wins(false)) do
            if not w.real then
                log("[allwins] " .. dump_win(w))
            end
        end
    end
    -- ★ 角色当前站位（网格坐标）。prove 之后才可用。
    --   写场景时靠它确定「往哪走几格」，跑完回看日志即可校正 ——
    --   不必再靠截图目测数格子。
    if SB2_RUNTIME ~= nil then
        local p = emu:readRange(SB2_RUNTIME + SB1_DELTA, 4)
        if p and #p >= 4 then
            local px = u16(p, 0); if px > 32767 then px = px - 65536 end
            local py = u16(p, 2); if py > 32767 then py = py - 65536 end
            log(string.format("[POS] shot=%s grid=(%d,%d)", name, px, py))
        end
    end
    log(string.format("  dumps: %s.{png,vram.bin,pal.bin,ram.bin}", number))

    -- 末列 stable：截图前连续稳定的帧数。
    -- settled 列：1=严格稳定（VRAM 全等） 2=宽松稳定（忽略 VRAM 动画） 0=超时强拍
    local settled_code = (not ok) and 0 or (S.soft and 2 or 1)
    csv:write(string.format("%d,%d,%s,%s.png,%04X,%04X,%04X,%04X,%04X,%d,%d\n",
             SEQ, fr, name, number, dispcnt,
             bg[0], bg[1], bg[2], bg[3], stable_n, settled_code))
    csv:flush()
end

-- ============================================================================
-- 主循环（frame 回调，每帧必触发）
-- ----------------------------------------------------------------------------
-- 步骤语义（新）：
--   {act="A".."L", n=H}  按住 H 帧 → 松开 → settle
--   {act="wait",  n=N}   纯等 N 帧   → settle
--   {act="shot",  name=X} settle → 截图 → settle
--   {act="prove"}        settle → 读档证明 → settle
--
-- ⚠ 物理按键展开：hold H 帧 + release H 帧（H<4 时补到 4）。
--   Gen3 的标题/菜单需要**新的按下沿**，一直按住会被当成一次长按而忽略；
--   松开太少又可能被当成抖动。两条都遵守才有稳定的按键响应。
-- ============================================================================
log("scene=" .. scene .. " side=" .. side .. " steps=" .. #STEPS)
log("scene.lua=" .. scene_path)
log(string.format("settle: need=%d timeout=%d", SETTLE_NEED, SETTLE_TIMEOUT))
local title = emu:readRange(0x080000A0, 12)
if title then log("rom_title=" .. title:gsub("[^%w]", ".")) end
log("output=" .. SHOTDIR)

local IDX = 1                        -- 当前步骤
local ELEFT = 0                      -- 当前步骤（持续性）剩余帧数
local mask = 0                       -- 当前按键掩码
local PHASE = "step"                 -- "step" | "hold" | "release"
local HOLD = 0                       -- 本步按住帧数
local REL = 0                        -- 本步松开帧数
local FRAME_BASE = nil
local LAST_HB = 0

-- ── talk 步骤的运行态（见 settle/step 注释）──────────────────────────────────
local TALK_TO     = 300    -- 等文本窗口出现的超时帧数
local TALK_T0     = 0      -- 进入 talk_wait 的帧号
local TALK_NEXT   = 0      -- 下次扫描窗口的帧号
local TALK_SOFT   = false  -- 超时未出现窗口时是否继续
local TALK_BASE   = nil    -- 按键前的窗口指纹 {addr -> {idx, txt}}
-- 窗口扫描要读 96KB+32KB 再逐 4 字节过一遍，每帧做太重（会拖慢模拟速度）。
-- 每 4 帧扫一次：600fps 下相当于 6ms 一次，足够跟上对话开框的速度。
local TALK_SCAN_EVERY = 4

-- 执行「瞬时步骤」；返回 false 表示应当终止
local function exec_instant(fr, st, timeout_flag)
    if st.act == "shot" then
        -- ok = 是否真的稳定。宽松稳定（soft）**也算稳定** —— 只是判据
        -- 放宽到忽略 VRAM 内容动画，绝不是「超时强拍」。
        snapshot(fr, st, S.stable, not timeout_flag)
    elseif st.act == "prove" then
        if not do_prove(fr) then
            return false
        end
    end
    return true
end

-- 进入下一步：只负责「切到下一步 + 请求 settle」。
-- ⚠ 瞬时步骤（shot/prove）**不在这里执行** —— 统一由主循环在 settle 结束后的
--   同一个分支里执行一次。否则 advance 执行一次、主循环又执行一次 = 双份截图。
advance = function(fr)
    IDX = IDX + 1
    if IDX > #STEPS then
        emu:setKeys(0)
        stop(0, string.format("done f=%d idx=%d/%d shots=%d",
                              fr, IDX - 1, #STEPS, SEQ))
        return
    end
    PHASE = "step"
    ELEFT = 0
    local st = STEPS[IDX]
    if st.act == "await" then
        settle_begin(string.format("await:0x%04X@%08X", st.value, st.addr), fr,
                     st.addr, st.value, st.n, st.addr2, st.value2)
    elseif st.act == "walk" or st.act == "await_pos" then
        -- 需要 prove 先找到 SaveBlock2 的运行时地址
        local wm = (st.act == "walk") and (1 << KEYBIT[st.dir]) or nil
        if SB2_RUNTIME == nil then
            log(string.format(
                "[ERR] %s 需要 SB2 地址但 prove 还没跑过 ⇒ 本步将超时",
                st.act))
        end
        settle_begin(string.format("%s:(%d,%d)", st.act, st.x, st.y), fr,
                     nil, nil, st.n, nil, nil, SB2_RUNTIME, st.x, st.y, wm,
                     st.hold or 20, st.axis)
    else
        settle_begin(st.act .. (st.name and (":" .. st.name) or ""), fr)
    end
end

-- 开局：为**第 1 步**请求 settle。
-- ⚠⚠ 不能让第 1 步是 await 时先用「无条件 settle」跑一遍（实测踩坑）：
--   那样 settle 会在版权画面就通过，随后主循环把该 await 当成「条件已满足」
--   直接 advance，于是 await 形同虚设 —— 整个 run 停在标题画面，
--   后面每一次 A 都按在版权/logo 上，全部按空（日志里连 [AWAIT] hit 都没有）。
do
    local st1 = STEPS[1]
    if st1.act == "await" then
        settle_begin(string.format("await:0x%04X@%08X", st1.value, st1.addr), 0,
                     st1.addr, st1.value, st1.n, st1.addr2, st1.value2)
    else
        settle_begin("boot", 0)
    end
end

-- ⚠⚠ 回调选择（2026-10-17 实测，勿再改）：
--   主循环 + 按键必须在 **keysRead**，不能在 frame。
--   frame 回调里调 `emu:setKeys` **不生效** —— 实测两轮 A 长按 20 帧之后
--   DISPCNT 依然停在 0x1741（标题），游戏完全没收到按键。
--   换回 keysRead 后同一份序列立刻能推动界面。
--   frame 只保留「兜底退出」，避免 keysRead 万一停摆时静默挂死。
local LAST_TICK = 0

callbacks:add("keysRead", function()
    local fr = emu:currentFrame()
    LAST_TICK = fr

    if FRAME_BASE == nil then
        FRAME_BASE = fr
        log(string.format("[BASE] frame origin = %d", fr))
    end

    if fr - LAST_HB >= 300 then
        LAST_HB = fr
        log(string.format("[HB] f=%d(+%d) step=%d/%d phase=%s mask=%04X shots=%d",
                          fr, fr - FRAME_BASE, IDX, #STEPS, PHASE, mask, SEQ))
        lf:flush()
    end

    if fr > MAX_FRAMES then
        stop(1, string.format("[ERR] frame cap reached f=%d idx=%d/%d", fr, IDX, #STEPS))
        return
    end

    -- ① 稳定检测优先：不稳定就不推进任何东西
    if settle_step(fr) then return end

    local timeout_flag = S.timed_out

    -- ② settle 刚结束（含开局首次）：执行当前步骤
    if PHASE == "step" then
        local st = STEPS[IDX]
        if st.act == "await" then
            -- 条件已在 settle_step 里满足（否则不会走到这里）；
            -- 超时未满足 = 没到达目标界面 ⇒ 硬失败，绝不产生假对照。
            if timeout_flag then
                emu:setKeys(0)
                stop(1, string.format(
                    "[ERR] await 未满足：等 0x%04X@0x%08X，超时 %d 帧未到达"
                    .. "（f=%d step=%d）。场景未到达目标界面，拒绝产出对照。",
                    st.value, st.addr, st.n, fr, IDX))
                return
            end
            advance(fr)
            return
        elseif st.act == "walk" or st.act == "await_pos" then
            -- ★ 坐标对齐：超时说明没走到目标格。
            --   soft=true 时降级为警告并继续（用于「可能已遇敌、坐标被战斗
            --   系统接管」这类合法场景）；否则硬失败，该帧不可用于对照。
            if timeout_flag then
                if st.soft then
                    log(string.format(
                        "[AWAIT_POS] soft-timeout step=%d want=(%d,%d) f=%d"
                        .. " ⇒ 判定为已进入战斗/被接管，继续", IDX, st.x, st.y, fr))
                else
                    emu:setKeys(0)
                    stop(1, string.format(
                        "[ERR] %s 未满足：等坐标 (%d,%d)，超时 %d 帧未到达"
                        .. "（f=%d step=%d）。两侧未站到同一格，拒绝产出对照。",
                        st.act, st.x, st.y, st.n, fr, IDX))
                    return
                end
            end
            advance(fr)
            return
        elseif st.act == "shot" or st.act == "prove" then
            if not exec_instant(fr, st, timeout_flag) then
                emu:setKeys(0)
                stop(1, string.format("[ERR] prove failed at step %d (f=%d)", IDX, fr))
                return
            end
            advance(fr)
            return
        elseif st.act == "talk" then
            -- ★ 对话闸门（详见 step 校验处的注释）：
            --   按住 A → 松手 → 观察「文本是否真的开始推进」。
            HOLD = st.press or 4
            ELEFT = HOLD
            mask = (1 << KEYBIT["A"])
            PHASE = "talk_press"
            TALK_TO = st.n or 300
            TALK_T0 = fr
            TALK_NEXT = 0
            TALK_SOFT = st.soft or false
            TALK_BASE = nil
        elseif st.act == "wait" then
            ELEFT = st.n
            PHASE = "waiting"
            -- 落到下面继续按帧递减
        else
            -- 按键步骤：进入 hold
            HOLD = st.n
            REL = HOLD < 4 and 4 or HOLD
            ELEFT = HOLD
            PHASE = "hold"
            mask = (1 << KEYBIT[st.act])
        end
    end

    -- ③ 持续动作按帧递减
    if PHASE == "waiting" then
        ELEFT = ELEFT - 1
        if ELEFT <= 0 then advance(fr) end
        return
    end

    if PHASE == "talk_press" then
        emu:setKeys(mask)
        ELEFT = ELEFT - 1
        if ELEFT <= 0 then
            emu:setKeys(0)
            mask = 0
            PHASE = "talk_wait"
            TALK_T0, TALK_NEXT = fr, 0
        end
        return
    end

    if PHASE == "talk_wait" then
        if fr >= TALK_NEXT then
            TALK_NEXT = fr + TALK_SCAN_EVERY
            local wins = scan_wins()
            if TALK_BASE == nil then
                -- 第一次采样 = 基准（按键后 ~4 帧）
                TALK_BASE = {}
                for _, w in ipairs(wins) do
                    TALK_BASE[w.addr] = { idx = w.idx, txt = w.txt }
                end
            else
                -- ★★ 只认「文本真的在推进」这一件事：
                --   ① 出现按键前不存在的窗口
                --   ② 同一窗口换了文本指针（新的一句）
                --   ③ 同一窗口的打印下标 index 变了（逐字打印中）
                --
                --   为什么不能只认「存在一个合法窗口」（2026-10-18 实测踩坑）：
                --   AXVJ 里那个 tpl=0x081BB46C / BG0 的窗口**野外也一直在**
                --   （index=11、text 指针固定），于是「有窗口」恒为真，
                --   踩进草丛触发的**战斗转场**也被判成「对话开框」，
                --   整段场景照样跑完、产出的却是战斗画面。
                for _, w in ipairs(wins) do
                    local b = TALK_BASE[w.addr]
                    local why
                    if b == nil then
                        why = "新窗口"
                    elseif b.txt ~= w.txt then
                        why = string.format("文本指针 %08X→%08X", b.txt, w.txt)
                    elseif b.idx ~= w.idx then
                        why = string.format("打印推进 index %d→%d", b.idx, w.idx)
                    end
                    if why then
                        log(string.format(
                            "[TALK] hit f=%d step=%d span=%d win=0x%08X %s",
                            fr, IDX, fr - TALK_T0, w.addr, why))
                        advance(fr)
                        return
                    end
                end
                -- ④ 窗口**消失**也算文本推进：一句说完后按 A 会把对话框关掉，
                --    这时不会出现新窗口，只会少一个 —— 漏掉这条会把
                --    「关掉最后一句」误判成「A 打空」。
                local now = {}
                for _, w in ipairs(wins) do now[w.addr] = true end
                for addr in pairs(TALK_BASE) do
                    if not now[addr] then
                        log(string.format(
                            "[TALK] hit f=%d step=%d span=%d win=0x%08X 窗口关闭"
                            .. " ⇒ 这一下 A 把最后一句关掉了",
                            fr, IDX, fr - TALK_T0, addr))
                        advance(fr)
                        return
                    end
                end
                for _, w in ipairs(wins) do
                    TALK_BASE[w.addr] = { idx = w.idx, txt = w.txt }
                end
            end
        end
        if fr - TALK_T0 > TALK_TO then
            local msg = string.format(
                "[TALK] TIMEOUT f=%d step=%d 等了 %d 帧文本没有推进"
                .. " ⇒ 这一下 A 没打到对话（NPC 不在面前/站在草丛里被转场吃掉）",
                fr, IDX, fr - TALK_T0)
            if TALK_SOFT then
                log(msg .. " (soft，继续)")
                advance(fr)
            else
                emu:setKeys(0)
                stop(1, "[ERR] " .. msg)
            end
            return
        end
        return
    end

    if PHASE == "hold" then
        emu:setKeys(mask)
        ELEFT = ELEFT - 1
        if ELEFT <= 0 then
            PHASE = "release"
            ELEFT = REL
            mask = 0
            emu:setKeys(0)
        end
        return
    end

    if PHASE == "release" then
        emu:setKeys(0)
        ELEFT = ELEFT - 1
        if ELEFT <= 0 then advance(fr) end
        return
    end
end)

-- 兜底：keysRead 万一长时间不触发（游戏卡在不读输入的循环里），
-- 也要报错退出而不是静默挂起。
callbacks:add("frame", function()
    local fr = emu:currentFrame()
    if LAST_TICK > 0 and fr - LAST_TICK > 3000 then
        stop(1, string.format(
            "[ERR] 输入回调停摆 fr=%d last_tick=%d idx=%d/%d phase=%s",
            fr, LAST_TICK, IDX, #STEPS, PHASE))
    end
end)
