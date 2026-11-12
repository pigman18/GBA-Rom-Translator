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
local burst_prefix = {}     -- burst 的帧名前缀（必须唯一，否则落盘会互相覆盖）
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
        -- any_of = 候选值列表，任一命中即算到位（转场/抖动界面用）。
        if type(st.n) ~= "number" or st.n < 1 then
            stop(1, string.format("[ERR] await step %d needs n=timeout", i))
        end
        if type(st.addr) ~= "number" or type(st.value) ~= "number" then
            stop(1, string.format("[ERR] await step %d needs addr/value", i))
        end
        if st.any_of ~= nil then
            if type(st.any_of) ~= "table" or #st.any_of == 0 then
                stop(1, string.format("[ERR] await step %d bad any_of", i))
            end
            for _, v in ipairs(st.any_of) do
                if type(v) ~= "number" then
                    stop(1, string.format(
                        "[ERR] await step %d any_of 里只能放数字", i))
                end
            end
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
    elseif st.act == "burst" then
        -- ★ 多帧连续采集（2026-11-03 新增）。
        --   为什么需要：单张 shot 只证明「某个定型帧长这样」，
        --   证明不了「过程是连续的、中间帧没错位」。战斗转场、血条递减、
        --   逐字打印、菜单逐项高亮这些都必须看**连续帧**才能判。
        --   n     = 拍几张
        --   every = 每张间隔多少帧（默认 1 = 逐帧）
        --   name  = 帧名前缀，实际落盘为 <prefix>_01、<prefix>_02 …
        --   dumps = 默认 false，只写 PNG。
        --     全量 dump 每帧 ~385KB（vram96K+ram288K+…），连续 30 帧
        --     就是 11MB；而 burst 的用途是看画面演进，不是逐帧做
        --     tile 级分析。需要 dump 的关键帧仍旧单用 shot。
        if type(st.n) ~= "number" or st.n < 1 then
            stop(1, string.format("[ERR] burst step %d needs n>=1", i))
        end
        if st.every ~= nil and (type(st.every) ~= "number" or st.every < 1) then
            stop(1, string.format("[ERR] burst step %d bad every", i))
        end
        if type(st.name) ~= "string" or not safe_id(st.name) then
            stop(1, string.format("[ERR] burst step %d needs a safe name prefix", i))
        end
        if burst_prefix[st.name] then
            stop(1, "[ERR] duplicate burst prefix: " .. st.name)
        end
        burst_prefix[st.name] = true
        total_frames = total_frames + st.n * (st.every or 1)
        shots = shots + st.n
    elseif st.act == "poke" then
        -- ★ 金手指：直接写**实时内存**（2026-11-03 新增）。
        --   用途：把游戏推到指定场景（改坐标、改队伍、改图鉴旗标）。
        --   ⚠ 与 savestate 的本质区别（用户契约第 3 条）：
        --     savestate 是内存快照，会把 ROM 的 hook 改动一起冻住，
        --     验收失真；这里写的是正在跑的实时内存，ROM 是当次加载的。
        --   ⚠ 地址语义：
        --     写 SaveBlock1 里的字段用 `sb1 = <偏移>`（更稳，跟存档走）；
        --     写别处用 `addr = <绝对地址>`。
        --   {act="poke", writes={{sb1=0x00, width=2, value=0x1234}, ...}}
        if type(st.writes) ~= "table" or #st.writes == 0 then
            stop(1, string.format("[ERR] poke step %d needs a non-empty writes list", i))
        end
        for j, wr in ipairs(st.writes) do
            if type(wr) ~= "table" then
                stop(1, string.format("[ERR] poke step %d write %d is not a table", i, j))
            end
            if type(wr.addr) ~= "number" and type(wr.sb1) ~= "number" then
                stop(1, string.format(
                    "[ERR] poke step %d write %d needs addr or sb1", i, j))
            end
            local wd = wr.width or 1
            if wd ~= 1 and wd ~= 2 and wd ~= 4 then
                stop(1, string.format(
                    "[ERR] poke step %d write %d bad width (1/2/4)", i, j))
            end
            if type(wr.value) ~= "number" then
                stop(1, string.format("[ERR] poke step %d write %d needs value", i, j))
            end
        end
    elseif st.act == "call" then
        -- ★ 金手指·调用游戏函数（2026-11-03 新增）。
        --   为什么需要：有些状态没法靠「写某个变量」造出来 ——
        --   比如**遇敌**，它是函数里一连串判定 + 建队 + 切场景的结果。
        --   改写 gRngValue 只能让随机数确定，不能保证「一定遇敌」。
        --   直接调用游戏的入口函数才是最忠实的做法：走的是**原版自己的逻辑**，
        --   汉化侧与原始侧执行同一条代码路径，对照才成立。
        --   用法：{act="call", addr=0x08128528}    -- SetUpFieldMove_SweetScent
        --   ⚠ 只允许在**野外空闲状态**调用（任务循环在跑、没有开菜单/对话），
        --     否则会把游戏状态机推乱。poke/await 的前置门槛同样适用。
        if type(st.addr) ~= "number" then
            stop(1, string.format("[ERR] call step %d needs addr", i))
        end
    elseif st.act == "hunt" then
        -- ★★ 遇敌搜捕（2026-11-03 新增，用户选定方案）。
        --   为什么需要：「遇敌」本身是随机的，而两侧的帧号/按键时机不可能
        --   完全一致（译文打印更慢），实测同一格走下来遇敌格会差 1。
        --   与其追求「第 N 格必遇敌」，不如改成**一旦遇敌就停**：
        --     每走一格检查 DISPCNT 是否离开野外值(0x7F60)；
        --     一旦离开，立刻停手，后面的采集从**战斗画面**开始 ——
        --     两侧都从同一个界面起采，对照就对齐了。
        --   这样「到底第几格遇敌」不再重要，差值被吸收在这一步内部。
        --   参数：
        --     dir   = 方向（默认 DOWN）
        --     from  = 起始格（x,y 里的固定轴）
        --     steps = 最多走几格（默认 24）
        --     wild  = 野外 DISPCNT 值（默认 0x7F60）
        if KEYBIT[st.dir or "DOWN"] == nil then
            stop(1, string.format("[ERR] hunt step %d bad dir", i))
        end
        if type(st.x) ~= "number" or type(st.y) ~= "number" then
            stop(1, string.format("[ERR] hunt step %d needs x/y start", i))
        end
        if st.steps ~= nil and (type(st.steps) ~= "number" or st.steps < 1) then
            stop(1, string.format("[ERR] hunt step %d bad steps", i))
        end
        total_frames = total_frames + (st.n or 120) * (st.steps or 24)
    elseif st.act == "tap_if" then
        -- ★ 条件按键（2026-11-03 新增）。
        --   为什么需要：读档其实有两条合法路径 ——
        --     ① 标题 → 「继续游戏」菜单(3140) → 按 A → 进野外
        --     ② 标题 → 直接续玩 → 野外(7F60)（跳过菜单）
        --   哪条出现取决于 A 键落在哪一帧，两次运行都可能不同。
        --   旧场景硬等 3140 再无条件按 A，走路径②时会白等超时 + 按空。
        --   本动作：只有当前 DISPCNT == want 时才按 key，否则本步直接跳过。
        if type(st.want) ~= "number" then
            stop(1, string.format("[ERR] tap_if step %d needs want", i))
        end
        if type(st.key) ~= "string" or KEYBIT[st.key] == nil then
            stop(1, string.format("[ERR] tap_if step %d bad key", i))
        end
        if st.addr == nil then
            -- 默认看 DISPCNT
            st.addr = 0x04000000
        end
        if type(st.n) ~= "number" or st.n < 1 then
            stop(1, string.format("[ERR] tap_if step %d bad n", i))
        end
        total_frames = total_frames + st.n
    elseif st.act == "roam" then
        -- ★★ 跨图漫游（2026-11-03 新增，为覆盖道馆/大赛）。
        --   为什么需要：实测「换地图改 .sav」无效，但**走位跨图有效**
        --   （商店 (3,3) 向下走 → map=0:2 城市 (23,17)）。问题在于
        --   **坐标会被换图重置**，按绝对格坐标 walk 会立刻判"已到位/被挡"。
        --   本动作只按**相对方向**推进：每个方向连走 steps 格，
        --   撞墙就换下一个方向，全程不依赖绝对坐标。
        --   参数：seq = 方向序列，如 {"DOWN","LEFT","UP","UP","RIGHT"}；
        --         steps = 每个方向连走几格（默认 8）
        --         collect = true 时每格都截一张（用 name 作前缀）
        if type(st.seq) ~= "table" or #st.seq == 0 then
            stop(1, string.format("[ERR] roam step %d needs seq", i))
        end
        for _, d in ipairs(st.seq) do
            if KEYBIT[d] == nil then
                stop(1, string.format("[ERR] roam step %d bad dir %s", i, tostring(d)))
            end
        end
        if st.steps ~= nil and (type(st.steps) ~= "number" or st.steps < 1) then
            stop(1, string.format("[ERR] roam step %d bad steps", i))
        end
        total_frames = total_frames + (st.n or 100) * (st.steps or 8) * #st.seq
    elseif st.act == "warp" then
        -- ★★★ 精确跳图（2026-11-03 跑通的方案）。
        --
        -- 原理：Gen3 的「传送术」野外效果 = 回到 SaveBlock1.lastHealLocation，
        -- 走 Overworld_ResetStateAfterTeleport → WarpIntoMap 那条路
        -- （这是 WarpIntoMap 全文件仅有的三处调用之一，普通走门不走它）。
        -- 所以先 poke lastHealLocation，再让游戏自己传送，就精确落点。
        --
        -- 实测成功样本：
        --   城市 map=0:2 (23,17) → poke lastHealLocation=0:33 (68,7)
        --   → 菜单里用传送 → 落地 map=0:33 grid=(68,7) 一字不差
        --
        -- ⚠ 前置：存档里必须有会「传送术(moveId=100)」的宝可梦，
        --   由 scripts/warp_tool.py --apply 植入。
        -- 参数：
        --   map = "group:num"   目标地图
        --   x, y                目标格坐标（s16）
        --   mon = 第几只（0-based，默认 1）
        if type(st.map) ~= "string" or not st.map:match("^%-?%d+:%-?%d+$") then
            stop(1, string.format("[ERR] warp step %d needs map=\"g:n\"", i))
        end
        if type(st.x) ~= "number" or type(st.y) ~= "number" then
            stop(1, string.format("[ERR] warp step %d needs x/y", i))
        end
        total_frames = total_frames + 1200
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
        -- 原始日文（JP 字节）还是我们的中文编码（F7 00 hi lo）。
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
    await_any = nil,          -- 候选值列表：任一命中即算到位（转场用）
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
                            pos_axis, await_any)
    S.active, S.stable, S.start_fr = true, 0, fr
    S.last_v, S.last_p, S.last_i = nil, nil, nil
    S.timed_out, S.soft, S.why = false, false, reason or ""
    S.await_addr, S.await_val = await_addr, await_val
    S.await_addr2, S.await_val2 = await_addr2, await_val2
    S.await_any = await_any
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
        -- ★ any_of（2026-11-03）：允许多个候选值任一命中。
        --   为什么必须加：遇敌进战斗时 DISPCNT 会先变成 **0x0000（全黑转场）**
        --   再变成 0xBF40。只等 0xBF40 的话，转场期间每次采样都是 0，
        --   stable 反复清零，很容易整段错过（实测直接超时 900 帧）。
        --   写 any_of 就能把「黑屏」和「已进战斗」都认成「已经离开野外」。
        local hit
        if S.await_any ~= nil then
            hit = false
            for _, v in ipairs(S.await_any) do
                if cur == v then hit = true; break end
            end
            if hit and S.await_addr2 ~= nil then
                hit = (cur2 == S.await_val2)
            end
        else
            hit = (cur == S.await_val)
                  and (S.await_addr2 == nil or cur2 == S.await_val2)
        end
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
            -- any_of 超时补一行候选值，否则日志只显示 value(=候选[1])，
            -- 会让人误以为"只等了一个值"（实测踩过）。
            if S.await_any then
                local t = {}
                for _, v in ipairs(S.await_any) do
                    t[#t + 1] = string.format("0x%04X", v)
                end
                log("[AWAIT] any_of={" .. table.concat(t, ",") .. "} 全部未命中")
            end
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

-- ── burst（多帧连续采集）运行态 ─────────────────────────────────────────────
-- 声明位置必须在 burst_step 之前：Lua 的 local 作用域从声明处生效，
-- 放在后面会变成 nil 全局（本文件顶部 SB1_DELTA 就踩过这个坑）。
local BURST_LEFT  = 0      -- 还剩几张
local BURST_N     = 0      -- 本次总共几张
local BURST_EVERY = 1      -- 每张间隔帧数
local BURST_NEXT  = 0      -- 下一张的帧号
local BURST_NAME  = ""     -- 帧名前缀

-- ok = 截图前是否真的稳定（严格或宽松都算稳定；false = 超时强拍的过渡帧）
-- name_override：burst 用的帧名（<prefix>_01 …）；nil = 用 step 的 name
-- with_dumps：是否落 vram/pal/io/ram/oam 五件套（burst 关掉，见步骤校验注释）
local function snapshot(fr, st, stable_n, ok, name_override, with_dumps)
    SEQ = SEQ + 1
    local name = name_override or st.name or "shot"
    local number = string.format("%03d", SEQ)
    local base = SHOTDIR .. number
    if with_dumps == nil then with_dumps = true end

    -- ★ 2026-10-21 修正顺序：必须**先读内存再截图**。
    -- 实测证据：font_capture 的 007(menu_top).vram 与 008(closed).vram 相同率 98.7%，
    -- 而 001(overworld) 与 007 相同率 95.5% —— 说明旧顺序（先 screenshot 再 readRange）
    -- 读到的 VRAM 已经是**下一帧/菜单关闭后**的状态，与 PNG 不同步。
    -- 这直接导致 T3 在 VRAM 里找不到字模。
    local vram, pal, io, ew, iw, oam
    if with_dumps then
        vram = emu:readRange(0x06000000, 0x18000)
        pal  = emu:readRange(0x05000000, 0x400)
        -- 0x04000000..0x04000060：DISPCNT/DISPSTAT/VCOUNT/BGxCNT/BGxHOFS/BGxVOFS/WIN*/BLDCNT。
        -- 离线合成器（work/compose.py）需要这些寄存器才能知道每层 charBase/screenBase/尺寸，
        -- 否则只能靠猜。
        io   = emu:readRange(0x04000000, 0x60)
        -- EWRAM **全量** 0x02000000+0x40000，IWRAM **全量** 0x03000000+0x8000。
        -- 2026-10-22 修正：原来 EWRAM 从 0x02020000 起（缺低 128KB）、IWRAM 只 0x800。
        -- 缺口导致两类东西看不见：
        --   ① 低半 EWRAM 里的结构（窗口/打印器的候选位置）；
        --   ② IWRAM 0x03000800 之外的运行时状态。
        -- 布局由 manifest.dumps.ram 声明（schema 3），离线读取方不要再按长度猜。
        ew   = emu:readRange(0x02000000, 0x40000)
        iw   = emu:readRange(0x03000000, 0x8000)
        oam  = emu:readRange(0x07000000, 0x400)
    end

    emu:screenshot(base .. ".png")

    if with_dumps then
        if vram then wr(base .. ".vram.bin", vram) end
        if pal  then wr(base .. ".pal.bin",  pal)  end
        if io   then wr(base .. ".io.bin",   io)   end
        if ew and iw then wr(base .. ".ram.bin", ew .. iw) end
        -- OAM（0x07000000，1024B）：判断文字是否走 OBJ（sprite）渲染。
        -- VRAM 里找不到假名字模时，这是关键判据。
        if oam then wr(base .. ".oam.bin", oam) end
    end

    local dispcnt = emu:read16(0x04000000)
    log(string.format("[SHOT %03d] name=%s f=%d dispcnt=%04X stable=%d settled=%s%s",
                      SEQ, name, fr, dispcnt, stable_n,
                      ok and (S.soft and "soft" or "yes") or "NO(超时强拍)",
                      with_dumps and "" or " png-only"))
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
        local p = emu:readRange(SB2_RUNTIME + SB1_DELTA, 6)
        if p and #p >= 6 then
            local px = u16(p, 0); if px > 32767 then px = px - 65536 end
            local py = u16(p, 2); if py > 32767 then py = py - 65536 end
            -- ★ 顺带打地图 ID（2026-11-03）。
            --   为什么必须打：走位跨图（室内走出去 / 换城）是覆盖道馆、大赛的
            --   唯一可行手段，而只看坐标判断不出「现在在哪张图」。
            --   +0x04 = location.mapGroup, +0x05 = mapNum（实测与 .sav 一致）。
            local mg, mn = s8v(u8(p, 4)), s8v(u8(p, 5))
            log(string.format("[POS] shot=%s grid=(%d,%d) map=%d:%d",
                              name, px, py, mg, mn))
        end
    end
    if with_dumps then
        log(string.format("  dumps: %s.{png,vram.bin,pal.bin,ram.bin}", number))
    end

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

-- ── 金手指：把一组写操作打到**实时内存**上 ──────────────────────────────────
-- 返回写入条数；任何一条失败返回 nil + 错误信息。
-- 写之前把原值读出来记进日志：出问题能回滚，也能证明"写之前确实不是这个值"。
local function do_poke(fr, st)
    -- ★★ 硬门槛（2026-11-03，用户口径）：金手指**必须在读档成功之后**才允许执行。
    --   为什么：savestate 那条路已经证明过「内存快照会把 ROM 的 hook 冻住，
    --   验收失真」。金手指虽然写的是实时内存、不冻 ROM，但如果写早了
    --   （还在标题/主菜单、存档尚未载入），改的是**还没被存档初始化**的
    --   EWRAM 区域，游戏读档时会把它整个覆盖掉 —— 表现为「按了没反应」，
    --   更糟的是可能写坏别的结构，让人误判成汉化有问题。
    --   SB2_RUNTIME 只在 do_prove 命中「存档身份字节」后才被赋值，
    --   所以它非 nil 就等价于「这份 .sav 已经真的进了内存」。
    if SB2_RUNTIME == nil then
        return nil, "金手指被拒绝：prove 还没成功（存档未载入），" ..
                    "必须先走完 读档→prove 这一段"
    end

    -- ★ 第二道门槛：DISPCNT 必须已经不是标题/主菜单。
    --   prove 的语义边界是「存档进了内存」，而 Gen3 在**标题画面**就已经
    --   把存档读进来用于画「继续游戏」摘要 —— 光靠 SB2_RUNTIME 拦不住
    --   「还在标题就写内存」。这两个签名是 _lib 里实测的标题/主菜单特征。
    local dis = emu:read16(0x04000000)
    if dis == 0x1741 or dis == 0x3140 then
        return nil, string.format(
            "金手指被拒绝：当前 DISPCNT=0x%04X 仍是标题/继续游戏画面，" ..
            "存档还没真正进入游戏世界", dis)
    end

    local n = 0
    for j, wr in ipairs(st.writes) do
        local addr
        local via
        if wr.sb1 ~= nil then
            if SB2_RUNTIME == nil then
                return nil, string.format(
                    "poke write %d 用 sb1 偏移但 prove 还没跑过（SB2 未知）", j)
            end
            addr = SB2_RUNTIME + SB1_DELTA + wr.sb1
            via = string.format("sb1+0x%X", wr.sb1)
        else
            addr = wr.addr
            via = "abs"
        end

        local wd = wr.width or 1
        -- 读原值（未对齐的宽读会让 mGBA 报错，这里按宽度手工拼）
        local old = 0
        if wd == 1 then old = emu:read8(addr)
        elseif wd == 2 then
            old = emu:read16(addr)
        else
            old = emu:read32(addr)
        end

        local ok, err
        if wd == 1 then ok, err = pcall(function() emu:write8(addr, wr.value) end)
        elseif wd == 2 then ok, err = pcall(function() emu:write16(addr, wr.value) end)
        else ok, err = pcall(function() emu:write32(addr, wr.value) end) end
        if not ok then
            return nil, string.format("poke write %d 失败: %s", j, tostring(err))
        end

        -- 写后复核：这是金手指最容易出错的地方（地址算错会静默改坏别的内存）
        local now
        if wd == 1 then now = emu:read8(addr)
        elseif wd == 2 then now = emu:read16(addr)
        else now = emu:read32(addr) end

        local mask = (wd == 4) and 0xFFFFFFFF or ((1 << (wd * 8)) - 1)
        local want = wr.value & mask
        if now ~= want then
            return nil, string.format(
                "poke write %d 复核失败 @0x%08X: 写入 0x%X 读回 0x%X",
                j, addr, want, now)
        end

        log(string.format(
            "[POKE] f=%d #%d @0x%08X (%s) w%d 0x%X -> 0x%X %s",
            fr, j, addr, via, wd, old & mask, now,
            wr.note and ("; " .. wr.note) or ""))
        n = n + 1
    end
    return n
end

-- ── 金手指·调用游戏函数 ────────────────────────────────────────────────────
-- 真正调用 ROM 里的函数（走原版自己的逻辑），而不是「猜着改某个变量」。
--
-- ⚠ mGBA 的 Lua 绑定**没有** callFunction 之类的接口，所以这里用 GBA 的
--   BIOS 软中断做一次「一次性跳板」：
--     ① 在 EWRAM 末尾（本项目 hook 的调试区之后）写一段 ARM 跳板
--     ② 跳到目标函数（Thumb），返回后跳回一个死循环
--     ③ 用 Halt 让 CPU 停在那
--   实测这条路的风险比「假装能调用」高得多，所以先只做**保守版**：
--   只在明确验证过跳板可用之后才启用；否则如实报错，不静默假装成功。
local function do_call(fr, st)
    if SB2_RUNTIME == nil then
        return nil, "call 被拒绝：prove 还没成功（存档未载入）"
    end
    local dis = emu:read16(0x04000000)
    if dis == 0x1741 or dis == 0x3140 then
        return nil, string.format(
            "call 被拒绝：当前 DISPCNT=0x%04X 仍是标题/菜单画面", dis)
    end
    return nil, string.format(
        "call 暂未启用：mGBA Lua 绑定没有函数调用接口（只有 read/write），" ..
        "跳板方案需要单独验证。目标 0x%08X", st.addr)
end

-- ── 遇敌搜捕（hunt）运行态 ─────────────────────────────────────────────────
-- 逐格走，每帧看 DISPCNT 是否离开野外值；一离开就停手并 advance。
-- 关键：**不在格子层面判等**（那正是两侧差 1 的来源），只判「界面变了」。
local HUNT_ACTIVE = false
local HUNT_DIR    = "DOWN"
local HUNT_TX     = 0
local HUNT_TY     = 0        -- 目标格（每格 +1）
local HUNT_STEPS  = 0        -- 计划最多走几格
local HUNT_DONE   = 0        -- 已走几格
local HUNT_WILD   = 0x7F60
local HUNT_TO     = 120      -- 单格超时帧数
local HUNT_T0     = 0
local HUNT_REL    = 0        -- 松手后的冷却帧数

local function hunt_begin(st, fr)
    HUNT_ACTIVE = true
    HUNT_DIR  = st.dir or "DOWN"
    HUNT_STEPS = st.steps or 24
    HUNT_WILD = st.wild or 0x7F60
    HUNT_TO   = st.n or 120
    HUNT_DONE = 0
    HUNT_T0   = fr
    HUNT_REL  = 0

    -- 起点来自 SaveBlock1（prove 之后可用）；取不到就用场景给的 x/y
    local sx, sy = st.x, st.y
    if SB2_RUNTIME ~= nil then
        local p = emu:readRange(SB2_RUNTIME + SB1_DELTA, 4)
        if p and #p >= 4 then
            local px = u16(p, 0); if px > 32767 then px = px - 65536 end
            local py = u16(p, 2); if py > 32767 then py = py - 65536 end
            sx, sy = px, py
        end
    end
    HUNT_TX, HUNT_TY = sx, sy
    log(string.format("[HUNT] start f=%d from=(%d,%d) dir=%s steps=%d wild=%04X",
                      fr, sx, sy, HUNT_DIR, HUNT_STEPS, HUNT_WILD))
end

-- 返回 true = 本帧已被 hunt 占用
local function hunt_step(fr)
    if not HUNT_ACTIVE then return false end

    -- ① 遇敌判定优先：DISPCNT 一旦不是野外值，立刻停手
    local dis = emu:read16(0x04000000)
    if dis ~= HUNT_WILD then
        emu:setKeys(0)
        HUNT_ACTIVE = false
        -- 顺带打地图 ID：换成室内图（道馆/会场）时也会触发停止，
        -- 这时"不是遇敌"而是"进图了"，日志里必须能分辨。
        local mg, mn = -1, -1
        if SB2_RUNTIME ~= nil then
            local p = emu:readRange(SB2_RUNTIME + SB1_DELTA, 6)
            if p and #p >= 6 then
                mg, mn = s8v(u8(p, 4)), s8v(u8(p, 5))
            end
        end
        log(string.format(
            "[HUNT] hit f=%d after %d steps DISPCNT=%04X map=%d:%d"
            .. " ⇒ 界面已改变，后面的采集从这里开始",
            fr, HUNT_DONE, dis, mg, mn))
        advance(fr)
        return true
    end

    -- ② 全部走完还没遇敌：不算失败，记下来，由后续 await 决定
    if HUNT_DONE >= HUNT_STEPS then
        emu:setKeys(0)
        HUNT_ACTIVE = false
        log(string.format(
            "[HUNT] gave-up f=%d walked %d steps, DISPCNT 仍是 %04X ⇒ 没遇到",
            fr, HUNT_DONE, dis))
        advance(fr)
        return true
    end

    -- ③ 冷却（松手让「按下沿」成立）
    if HUNT_REL > 0 then
        emu:setKeys(0)
        HUNT_REL = HUNT_REL - 1
        if HUNT_REL == 0 then HUNT_DONE = HUNT_DONE + 1; HUNT_T0 = fr end
        return true
    end

    -- ④ 走一格：按住方向，等坐标真的挪过去（或超时）
    --   ★ 往返模式（2026-11-03）：只朝一个方向走会撞出草丛/撞墙
    --     （实测 30 格全程没遇敌，因为走出了草丛）。这里每到边界就掉头，
    --     保证一直在草丛里来回踩，遇敌判定才会持续累计。
    local mask = (1 << KEYBIT[HUNT_DIR])
    emu:setKeys(mask)

    local moved = false
    if SB2_RUNTIME ~= nil then
        local p = emu:readRange(SB2_RUNTIME + SB1_DELTA, 4)
        if p and #p >= 4 then
            local px = u16(p, 0); if px > 32767 then px = px - 65536 end
            local py = u16(p, 2); if py > 32767 then py = py - 65536 end
            moved = (px ~= HUNT_TX) or (py ~= HUNT_TY)
        end
    end

    if moved then
        -- 到位：松手并进入冷却
        emu:setKeys(0)
        local p = emu:readRange(SB2_RUNTIME + SB1_DELTA, 4)
        if p and #p >= 4 then
            local px = u16(p, 0); if px > 32767 then px = px - 65536 end
            local py = u16(p, 2); if py > 32767 then py = py - 65536 end
            HUNT_TX, HUNT_TY = px, py
        end
        HUNT_REL = 6
        return true
    end

    if fr - HUNT_T0 > HUNT_TO then
        -- 这一格走不动（被挡/撞墙），也算走完一格，并**掉头**
        log(string.format("[HUNT] step%d blocked f=%d at=(%d,%d) ⇒ 掉头",
                          HUNT_DONE + 1, fr, HUNT_TX, HUNT_TY))
        emu:setKeys(0)
        HUNT_REL = 6
        HUNT_T0 = fr
        HUNT_DIR = (HUNT_DIR == "DOWN") and "UP" or "DOWN"
    end
    return true
end

-- ── 跨图漫游（roam）运行态 ─────────────────────────────────────────────────
-- 只按方向推进，不用绝对坐标：换图会重置坐标，绝对坐标会立刻判"到位"。
local ROAM_ACTIVE = false
local ROAM_SEQ    = nil
local ROAM_SEQI   = 0        -- 当前方向下标
local ROAM_LEFT   = 0        -- 当前方向还要走几格
local ROAM_STEPS  = 8
local ROAM_PX     = 0
local ROAM_PY     = 0
local ROAM_MAPG   = 0
local ROAM_MAPN   = 0
local ROAM_HOLD   = 0        -- 本次按住已持续帧数
local ROAM_BLOCK  = 0        -- 按住却不动已持续帧数
local ROAM_TO     = 100      -- 单格超时

local function roam_pos()
    if SB2_RUNTIME == nil then return nil end
    local p = emu:readRange(SB2_RUNTIME + SB1_DELTA, 6)
    if not p or #p < 6 then return nil end
    local x = u16(p, 0); if x > 32767 then x = x - 65536 end
    local y = u16(p, 2); if y > 32767 then y = y - 65536 end
    return x, y, s8v(u8(p, 4)), s8v(u8(p, 5))
end

local function roam_begin(st, fr)
    ROAM_ACTIVE = true
    ROAM_SEQ   = st.seq
    ROAM_SEQI  = 1
    ROAM_STEPS = st.steps or 8
    ROAM_LEFT  = ROAM_STEPS
    ROAM_TO    = st.n or 100
    ROAM_HOLD  = 0
    ROAM_BLOCK = 0
    local x, y, g, n = roam_pos()
    ROAM_PX, ROAM_PY, ROAM_MAPG, ROAM_MAPN = x or 0, y or 0, g or 0, n or 0
    log(string.format(
        "[ROAM] start f=%d at=(%d,%d) map=%d:%d seq=%s steps=%d",
        fr, ROAM_PX, ROAM_PY, ROAM_MAPG, ROAM_MAPN,
        table.concat(ROAM_SEQ, ","), ROAM_STEPS))
end

-- 返回 true = 本帧被 roam 占用
local function roam_step(fr)
    if not ROAM_ACTIVE then return false end

    -- 全部方向走完 → 收尾
    if ROAM_SEQI > #ROAM_SEQ then
        emu:setKeys(0)
        ROAM_ACTIVE = false
        local x, y, g, n = roam_pos()
        log(string.format("[ROAM] done f=%d at=(%d,%d) map=%d:%d",
                          fr, x or -1, y or -1, g or -9, n or -9))
        advance(fr)
        return true
    end

    local dir = ROAM_SEQ[ROAM_SEQI]
    local x, y, g, n = roam_pos()
    if x == nil then
        -- 读不到坐标（还没 prove）：直接跳过，避免静默卡死
        emu:setKeys(0)
        ROAM_ACTIVE = false
        log("[ROAM] abort：读不到 SaveBlock1 坐标（prove 未执行？）")
        advance(fr)
        return true
    end

    -- 换图了：坐标已重置，重新定位并继续按序列走（不中止）
    if g ~= ROAM_MAPG or n ~= ROAM_MAPN then
        log(string.format("[ROAM] map %d:%d -> %d:%d at f=%d (坐标重置为 %d,%d)",
                          ROAM_MAPG, ROAM_MAPN, g, n, fr, x, y))
        ROAM_MAPG, ROAM_MAPN = g, n
        ROAM_PX, ROAM_PY = x, y
        ROAM_HOLD, ROAM_BLOCK = 0, 0
        emu:setKeys(0)
        return true
    end

    -- 位置变了 = 走成功了一格
    if x ~= ROAM_PX or y ~= ROAM_PY then
        ROAM_PX, ROAM_PY = x, y
        ROAM_HOLD, ROAM_BLOCK = 0, 0
        ROAM_LEFT = ROAM_LEFT - 1
        emu:setKeys(0)
        if ROAM_LEFT <= 0 then
            log(string.format("[ROAM] dir=%s done f=%d at=(%d,%d) map=%d:%d",
                              dir, fr, x, y, g, n))
            ROAM_SEQI = ROAM_SEQI + 1
            ROAM_LEFT = ROAM_STEPS
        end
        return true
    end

    -- 没动：按住继续推；推太久判撞墙，换下一个方向
    ROAM_HOLD  = ROAM_HOLD + 1
    ROAM_BLOCK = ROAM_BLOCK + 1
    emu:setKeys(1 << KEYBIT[dir])

    if ROAM_BLOCK > 40 or ROAM_HOLD > ROAM_TO then
        emu:setKeys(0)
        log(string.format(
            "[ROAM] dir=%s BLOCKED f=%d at=(%d,%d) map=%d:%d ⇒ 换下一方向",
            dir, fr, x, y, g, n))
        ROAM_SEQI = ROAM_SEQI + 1
        ROAM_LEFT = ROAM_STEPS
        ROAM_HOLD, ROAM_BLOCK = 0, 0
    end
    return true
end

-- ── 精确跳图（warp）运行态 ─────────────────────────────────────────────────
-- 两阶段：
--   WARP_SET：等稳定 → poke lastHealLocation → 进 WARP_KEYS
--   WARP_KEYS：按实测成功的按键序列操作菜单（START→宝可梦→选中→A→A）
--              传送一旦发生，map 会变；检测到 map 变化即收尾
local WARP_ACTIVE = false
local WARP_PHASE = "set"
local WARP_TX, WARP_TY = 0, 0
local WARP_TMAPG, WARP_TMAPN = 0, 0
local WARP_MON = 1
local WARP_SEQ = nil
local WARP_SEQI = 0
local WARP_MAPG0, WARP_MAPN0 = -99, -99
local WARP_T0 = 0
local WARP_TO = 1200

local function warp_pos()
    if SB2_RUNTIME == nil then return nil end
    local p = emu:readRange(SB2_RUNTIME + SB1_DELTA, 6)
    if not p or #p < 6 then return nil end
    local x = u16(p, 0); if x > 32767 then x = x - 65536 end
    local y = u16(p, 2); if y > 32767 then y = y - 65536 end
    return x, y, s8v(u8(p, 4)), s8v(u8(p, 5))
end

-- ⚠ warp_build_seq 定义在 warp_begin 之后，必须先前向声明，
--   否则 warp_begin 里拿到的是 nil 全局（Lua 的 local 作用域从声明处生效）。
local warp_build_seq

local function warp_begin(st, fr)
    -- ⚠ 必须显式关掉 settle：advance 会让上一步进入 settle 状态，
    --   而主循环里 `if settle_step(fr) then return end` 在 warp_step 之前，
    --   settle 一直 active 就永远走不到 warp（实测：只剩 set 阶段日志，
    --   后面的 key 日志一条都不出）。
    S.active = false
    WARP_ACTIVE = true
    WARP_PHASE = "set"
    local g, n = st.map:match("^(%-?%d+):(%-?%d+)$")
    WARP_TMAPG, WARP_TMAPN = tonumber(g), tonumber(n)
    WARP_TX, WARP_TY = st.x, st.y
    WARP_MON = st.mon or 1
    -- ⚠ 不要在这里调用 warp_build_seq：它定义在 warp_begin **之后**，
    --   Lua 的 local 前向声明在赋值前仍是 nil（实测 #WARP_SEQ = -1）。
    --   改为在 keys 阶段首次进入时懒构建。
    WARP_SEQ = nil
    WARP_TO = st.n or 1200
    WARP_T0 = fr
    local x, y, mg, mn = warp_pos()
    WARP_MAPG0, WARP_MAPN0 = mg or -99, mn or -99
    log(string.format(
        "[WARP] start f=%d from=(%d,%d) map=%d:%d → target map=%d:%d (%d,%d) mon=%d",
        fr, x or -1, y or -1, mg or -99, mn or -99,
        WARP_TMAPG, WARP_TMAPN, WARP_TX, WARP_TY, WARP_MON))
    log(string.format("[WARP] baseline set to %d:%d", WARP_MAPG0, WARP_MAPN0))
end

-- 按键序列（实测成功的那条），运行时按 mon 展开成扁平列表：
--   START → UP×8 → DOWN×1 → A →（DOWN × mon）→ A → A
-- ⚠ 这里必须是 `warp_build_seq = function`，不能写 `local function`。
--   因为 1473 行已经 `local warp_build_seq` 前向声明过，
--   再写 `local function` 会新建一个同名 local，前面的那个仍是 nil
--   （实测症状：warp_begin 里调用即抛错，日志连 start 都打不出来）。
warp_build_seq = function(mon)
    local seq = {}
    local function tap(k, n, after)
        seq[#seq + 1] = { key = k, hold = n, wait = after or 0 }
    end
    -- ⚠ 起手先按 B 清场：上一轮 warp 结束后可能还停在某个菜单里，
    --   直接按 START 会变成「在菜单里按 START」（无效），
    --   随后那串 UP 就变成**走路**（实测：角色一路走回商店 map=10:7）。
    --   野外 B 无副作用，室内也只会退出一层，多按几次总能回到可自由行动。
    for _ = 1, 4 do tap("B", 4, 25) end
    tap("START", 4, 60)
    for _ = 1, 8 do tap("UP", 4, 6) end
    tap("DOWN", 4, 12)
    tap("A", 4, 80)
    for _ = 1, mon do tap("DOWN", 4, 22) end
    tap("A", 4, 70)
    tap("A", 4, 40)
    return seq
end

local WARP_SEQ = nil
local WARP_SEQI = 0
local WARP_HOLD = 0
local WARP_WAIT = 0

-- 返回 true = 本帧被 warp 占用
local function warp_step(fr)
    if not WARP_ACTIVE then return false end
    -- 入口探针：若这条不出现，说明主循环没走到 warp_step
    if fr % 60 == 0 then
        log(string.format("[WARP] alive f=%d phase=%s seqi=%d/%d hold=%d wait=%d",
                          fr, WARP_PHASE, WARP_SEQI,
                          WARP_SEQ and #WARP_SEQ or -1, WARP_HOLD, WARP_WAIT))
    end

    local x, y, mg, mn = warp_pos()

    -- 阶段 1：写 lastHealLocation
    if WARP_PHASE == "set" then
        local sb1 = SB2_RUNTIME + SB1_DELTA
        emu:write8(sb1 + 0x1C, WARP_TMAPG & 0xFF)
        emu:write8(sb1 + 0x1D, WARP_TMAPN & 0xFF)
        emu:write8(sb1 + 0x1E, 0xFF)
        emu:write8(sb1 + 0x1F, 0x00)
        emu:write16(sb1 + 0x20, WARP_TX & 0xFFFF)
        emu:write16(sb1 + 0x22, WARP_TY & 0xFFFF)
        log(string.format(
            "[WARP] set lastHealLocation f=%d -> %d:%d (%d,%d)",
            fr, WARP_TMAPG, WARP_TMAPN, WARP_TX, WARP_TY))
        WARP_PHASE = "keys"
        WARP_SEQI = 1
        WARP_HOLD, WARP_WAIT = 0, 0
        WARP_T0 = fr
        return true
    end

    -- 阶段 2 起：每帧先检测是否已换图（这才是成功信号）
    -- 懒构建序列（见 warp_begin 里的注释）
    if WARP_SEQ == nil then
        WARP_SEQ = warp_build_seq(WARP_MON)
        log(string.format("[WARP] seq built: %d keys (mon=%d)",
                          #WARP_SEQ, WARP_MON))
    end

    if x ~= nil and (mg ~= WARP_MAPG0 or mn ~= WARP_MAPN0) then
        emu:setKeys(0)
        WARP_ACTIVE = false
        log(string.format(
            "[WARP] hit f=%d map=%d:%d grid=(%d,%d) target=%d:%d (%d,%d)%s",
            fr, mg, mn, x, y, WARP_TMAPG, WARP_TMAPN, WARP_TX, WARP_TY,
            (mg == WARP_TMAPG and mn == WARP_TMAPN
             and x == WARP_TX and y == WARP_TY) and " OK 完全命中" or " (部分偏差)"))
        advance(fr)
        return true
    end

    if WARP_SEQI > #WARP_SEQ then
        if fr - WARP_T0 > WARP_TO then
            emu:setKeys(0)
            WARP_ACTIVE = false
            log(string.format(
                "[WARP] TIMEOUT f=%d 按完序列仍未换图（map 仍 %d:%d）"
                .. " -> 检查存档里是否真有传送术", fr, mg or -99, mn or -99))
            advance(fr)
            return true
        end
        return true
    end

    local st2 = WARP_SEQ[WARP_SEQI]

    -- 等待段（按键后的间隔）
    if WARP_WAIT > 0 then
        WARP_WAIT = WARP_WAIT - 1
        if WARP_WAIT == 0 then
            -- 等待结束 → 推进到下一个按键。
            -- ⚠ 这里漏过一次：只递减不推进，导致序列永远停在第一个键，
            --   实测空转 150 万帧（[HB] step=13/20 一动不动）。
            WARP_SEQI = WARP_SEQI + 1
            WARP_HOLD = 0
        end
        return true
    end

    -- 按住段
    if WARP_HOLD > 0 then
        emu:setKeys(1 << KEYBIT[st2.key])
        WARP_HOLD = WARP_HOLD - 1
        if WARP_HOLD == 0 then
            emu:setKeys(0)
            if st2.wait > 0 then
                WARP_WAIT = st2.wait
            else
                WARP_SEQI = WARP_SEQI + 1
            end
        end
        return true
    end

    -- 进入这个按键
    WARP_HOLD = st2.hold
    log(string.format("[WARP] key %d/%d = %s (hold=%d wait=%d) f=%d",
                      WARP_SEQI, #WARP_SEQ, st2.key, st2.hold, st2.wait, fr))
    return true
end
-- ── 多帧连续采集 ────────────────────────────────────────────────────────────
-- 已进入 burst 状态（BURST_LEFT>0）时每帧调用；负责计数、间隔、取名、收尾。
-- 返回 true = 本帧已被 burst 占用。
local function burst_step(fr)
    if BURST_LEFT <= 0 then return false end
    if fr < BURST_NEXT then return true end      -- 间隔期：什么都不做，但仍占着本帧

    local i = BURST_N - BURST_LEFT + 1
    snapshot(fr, { name = BURST_NAME }, S.stable, true,
             string.format("%s_%02d", BURST_NAME, i), false)

    BURST_LEFT = BURST_LEFT - 1
    BURST_NEXT = fr + BURST_EVERY
    if BURST_LEFT <= 0 then
        log(string.format("[BURST] done name=%s n=%d every=%d f=%d",
                          BURST_NAME, BURST_N, BURST_EVERY, fr))
        advance(fr)
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
                     st.addr, st.value, st.n, st.addr2, st.value2,
                     nil, nil, nil, nil, 0, nil, st.any_of)
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
    elseif st.act == "poke" then
        -- poke 要在**画面稳定之后**执行：否则可能刚好在转场中途改内存，
        -- 游戏下一帧就会用旧值重算，改了等于没改。settle 后动手成功率高得多。
        settle_begin("poke", fr)
    elseif st.act == "burst" then
        -- burst 之前也要 settle：否则第一张会拍到上一动作的过渡帧。
        settle_begin("burst:" .. tostring(st.name), fr)
    elseif st.act == "hunt" then
        -- hunt 不需要 settle（它自己逐帧判 DISPCNT），直接起
        hunt_begin(st, fr)
    elseif st.act == "tap_if" then
        -- 条件按键也要先等画面稳定，否则可能在上一个界面的过渡帧里判条件
        settle_begin("tap_if", fr)
    elseif st.act == "roam" then
        -- roam 自己逐帧管方向与撞墙，不需要 settle
        roam_begin(st, fr)
    elseif st.act == "warp" then
        -- warp 自己逐帧推进（写 lastHealLocation → 按键序列 → 检测换图）
        warp_begin(st, fr)
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
                     st1.addr, st1.value, st1.n, st1.addr2, st1.value2,
                     nil, nil, nil, nil, 0, nil, st1.any_of)
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

    -- ①' 遇敌搜捕进行中：由它接管本帧（逐帧判 DISPCNT，一遇敌就 advance）
    if hunt_step(fr) then return end

    -- ①'' 跨图漫游进行中：只按方向推进，不依赖绝对坐标
    if roam_step(fr) then return end

    -- ①''' 精确跳图进行中：写 lastHealLocation → 走菜单按键 → 等换图
    if warp_step(fr) then return end

    -- ①'' burst 进行中：由它接管本帧（数帧、拍、到点收尾并 advance）
    if burst_step(fr) then return end

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
        elseif st.act == "tap_if" then
            -- 条件按键：当前值匹配才按，否则静默跳过本步
            local cur = emu:read16(st.addr)
            if cur == st.want then
                log(string.format("[TAP_IF] f=%d match 0x%04X ⇒ 按 %s",
                                  fr, cur, st.key))
                HOLD = st.n or 4
                REL = HOLD < 4 and 4 or HOLD
                ELEFT = HOLD
                PHASE = "hold"
                mask = (1 << KEYBIT[st.key])
            else
                log(string.format("[TAP_IF] f=%d skip（当前 0x%04X ≠ wish 0x%04X）",
                                  fr, cur, st.want))
                advance(fr)
            end
            return
        elseif st.act == "poke" then
            local n, err = do_poke(fr, st)
            if n == nil then
                emu:setKeys(0)
                stop(1, string.format("[ERR] poke 失败 step=%d f=%d: %s",
                                      IDX, fr, tostring(err)))
                return
            end
            log(string.format("[POKE] step=%d 共写入 %d 项", IDX, n))
            advance(fr)
            return
        elseif st.act == "burst" then
            -- 多帧连续采集：本步不按键，按 every 间隔连拍 n 张 PNG
            BURST_LEFT  = st.n
            BURST_N     = st.n
            BURST_EVERY = st.every or 1
            BURST_NEXT  = fr
            BURST_NAME  = st.name
            log(string.format("[BURST] start name=%s n=%d every=%d f=%d",
                              BURST_NAME, BURST_N, BURST_EVERY, fr))
            if not burst_step(fr) then advance(fr) end
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
