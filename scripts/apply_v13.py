# -*- coding: utf-8 -*-
"""v13 一次性改动：UI/文字统一分配 + 真回收回路。

按项目约定：读时归一 \r\n -> \n，写时还原；每处替换用 count 断言。
任何一处对不上就整体中止（不写盘）。
"""
import pathlib
import sys

ROOT = pathlib.Path(r"C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\hook")

EDITS = []


def edit(rel, old, new, tag, count=1):
    EDITS.append((rel, old, new, tag, count))


def load(p):
    b = p.read_bytes()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n")
    return b.decode("utf-8").replace("\r\n", "\n"), ("\r\n" if crlf > (lf - crlf) else "\n")


def save(p, text, eol):
    p.write_bytes((text.replace("\n", eol) if eol == "\r\n" else text).encode("utf-8"))


# =============================================================================
# 1. include/tile_alloc.h —— UI 出口改成 tpl 版
# =============================================================================
edit("include/tile_alloc.h",
     """ *   队列 = 本窗可分配的连续 tile 区间 [head, end)
 *          head = win[0x16] TILE_BASE（0 号槽官方空白，跳过）
 *          end  = 本窗 charBlock 上界（仅 OBJ 物理隔离）
 *   游标 = 队列内下一个可分配位置；切换窗 → 置首
 *   消费 = ① 主动文本分配 v8_alloc_tile  ② UI 分配 v8_ui_alloc
 *          两者共用同一游标，领到即占用，单调前进
 *
 * 铁律：
 *   ① 确定性：纯游标推进，同调用序列 → 同 tile 号（无随机、无环境依赖）。
 *   ② 零扫描：不读 tilemap、不读 screenblock、不做 VRAM 非空校验。
 *   ③ 宁缺不砸：队列耗尽返回 0，调用方放弃绘制。""",
     """ *   v13（2026-09-11）现状：UI 与文本**走同一个函数** `v8_alloc_core`。
 *   分配出口 = ① 主动文本 `v8_alloc_tile(win, ...)`（模板取自 TextPrinter）
 *             ② UI 框号   `v8_alloc_ui(tpl, n)`（模板来自 0x03000328，
 *                          ⑤ 被接管时手上只有模板、没有 TextPrinter）
 *   两者共用同一游标、同一 ours 账本、同一套三层占用校验
 *   （活引用位图 / VRAM 非空 / ours），领到即占用。
 *
 * 分层（自下而上，v13）：
 *   占用判定  v8_tile_usable        位图 + VRAM 非空 + ours
 *   回收      v8_rebuild_live       重建活引用位图（失败时重试一次 = 真回收）
 *   扫描      v8_alloc_scan         两遍（游标起 + 回卷）
 *
 * 铁律：
 *   ① 确定性：同调用序列 → 同 tile 号（无随机、无环境依赖）。
 *   ② 宁缺不砸：池子给不出连续 n 个砖 ⇒ 返回 0，调用方放弃绘制。
 *   ③ 文本与 UI 无区别：两者都从本出口领号，满了都返回 0。""",
     "tile_alloc.h 头注释")

edit("include/tile_alloc.h",
     """/* ② UI 分配：图集 / 窗框等 UI 占位领 n 个 tile。
 * 与文本分配共用同一队列游标 —— UI 先领则文字排在 UI 之后。 */
uint16_t v8_ui_alloc(TextPrinter *win, uint16_t n);""",
     """/* ② UI 分配：窗框等 UI 占位领 n 个 tile ——**与文本走同一个 v8_alloc_core**。
 *
 *   🔴 形参是 **tpl（窗口模板）而不是 TextPrinter**：⑤ `TextWindow_SetBaseTileNum`
 *      被接管时手上只有模板指针（0x03000328，① 写入），没有 TextPrinter。
 *   🔴 v12 之前 UI 不走这里（走的是一条叫 `v10_frame_alloc` 的纯计数器：不查位图、
 *      不读 VRAM、只判「游标+23 有没有越过上界」）⇒ 池子满了框照样画得出来
 *      = 用户实测「文字空、UI 不空」。v13 删掉那条路，UI 与文本同权。 */
uint16_t v8_alloc_ui(uint8_t *tpl, uint16_t n);""",
     "tile_alloc.h v8_alloc_ui 声明")


# =============================================================================
# 2. src/text/tile_alloc.c —— 头注释 + v8_rebuild_live 抽取 + v13 分配核心
# =============================================================================
edit("src/text/tile_alloc.c",
     """ *   ④ screenblock 内存保留：tilemap 区本身（含零槽位）整段标占。
 *   起址 lo = `v10_pool_lo()`（win_alloc.c 发放：池底 V12_POOL_LO=1，
 *   或本窗口 UI 框之后），上界 hi = (4-char_base)*512 clamp 1024（OBJ 隔离）。""",
     """ *   ④ screenblock 内存保留：tilemap 区本身（含零槽位）整段标占。
 *   ⑤ 真回收（v13）：两遍扫描都满 ⇒ `v8_rebuild_live()` 重跑一遍活引用重建
 *      （= 把已无 tilemap 引用的旧 bm 位一次性放掉）再试一次；仍无 ⇒ 返回 0。
 *   起址 lo = `v10_pool_lo()`（win_alloc.c 发放：池底 V12_POOL_LO=1，
 *   或本窗口 UI 框之后），上界 hi = (4-char_base)*512 clamp 1024（OBJ 隔离）。""",
     "tile_alloc.c 头注释 ④/⑤")

edit("src/text/tile_alloc.c",
     """ *     · 两个消费者共用同一游标、同一账本：
 *         ① 主动文本分配 v8_alloc_tile
 *         ② UI 分配      v8_ui_alloc
 *       谁先谁后由调用顺序决定，UI 先领则文本排在 UI 之后。""",
     """ *     · 两个消费者走**同一个函数**（v13 起）：
 *         ① 主动文本分配 v8_alloc_tile
 *         ② UI 框号       v8_alloc_ui（由 win_alloc.c 的 ⑤ 接管调用）
 *       v12 之前 ② 是 win_alloc.c 里的纯计数器（不查位图 / 不读 VRAM）⇒
 *       池子满了框照样画得出来 = 用户实测「文字空、UI 不空」。v13 删掉它。""",
     "tile_alloc.c 头注释 两个消费者")

# --- v8_alloc_begin -> v8_rebuild_live + 瘦身后的 v8_alloc_begin ---
edit("src/text/tile_alloc.c",
     """void v8_alloc_begin(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    volatile uint8_t *bm = v8_bitmap();
    uint8_t cb;
    unsigned bg;
    int switched;

    v8q_init_once();
    switched = v8q_is_switch(win);
    if (switched)
        v8q_own(win);

    /* v9.1：场景签名变化 ⇒ 官方极可能重新装载了 VRAM 图形 ⇒ ours 位图整体作废。
     * 同时兜住冷启动：EWRAM 垃圾不保证为 0，首次签名必与当前值不等 ⇒ 走一次清零。 */
    if (v8_scene_sig_changed())
        v8_ours_clear_all();

    *(volatile uint16_t *)ADDR_V8_PHASE     = 0u;
    *(volatile uint16_t *)ADDR_V8_PHASE_ROW = 0u;
    *(volatile uint16_t *)ADDR_V8_LAST_TILE = 0u;
    if (switched)
        *(volatile uint16_t *)ADDR_V8_CURSOR = 0u;   /* ← 切换：游标置首 */

    if (!tpl)
        return;
    cb = tpl[TPL_CHARBASE];

    v8_bit_clear_all(bm);

    /* ① win 自身 tilemap */""",
     """/* ============================================================================
 * v8_rebuild_live：**权威重建活引用位图**（v13 从 v8_alloc_begin 抽出来）。
 * 抽出来的唯一理由：分配失败时的「真回收」要重跑同一段扫描 ——
 * 重建一次 = 把「已无任何 tilemap 引用的旧 bm 位（含负缓存）」全部放掉。
 * 这是「每开一窗把游标打回池底」的正确替代：只还死掉的砖，不丢整个池子。
 *
 * ① win 自身 tilemap（防御 tilemap 不在 screenblock 的缓冲直绘变体）；
 * ② DISPCNT 启用的每个 text BG：BGxCNT.charBase == 本窗 charBase 时，
 *    按其 size 位扫整个 screenblock；
 * ③ screenblock 内存保留：各启用 BG 的 tilemap 内存区（含零槽位）整段标占。
 *
 * ⚠ begin 节流（同帧同签名跳过重建）已于 2026-09-07 实测证伪删除，本函数
 *   每次调用都全量重建，无跳过路径（理由见下方 v8_alloc_begin 的教训注释）。
 * ⚠ 调用方负责「本窗自己的号段」补标（见 v8_mark_frame）。
 * ==========================================================================*/
static void v8_rebuild_live(uint8_t *tpl)
{
    volatile uint8_t *bm = v8_bitmap();
    uint8_t cb = tpl[TPL_CHARBASE];
    unsigned bg;

    v8_bit_clear_all(bm);

    /* ① win 自身 tilemap */""",
     "tile_alloc.c 抽出 v8_rebuild_live")

edit("src/text/tile_alloc.c",
     """        {
            uintptr_t tm_addr = (uintptr_t)win_u32(tpl, TPL_TILEMAP);
            if (tm_addr)
                v8_reserve_mem(bm, tm_addr, tm_addr + 0x800u, cb_base, hi);
        }
    }
}
""",
     """        {
            uintptr_t tm_addr = (uintptr_t)win_u32(tpl, TPL_TILEMAP);
            if (tm_addr)
                v8_reserve_mem(bm, tm_addr, tm_addr + 0x800u, cb_base, hi);
        }
    }
}

/* ============================================================================
 * v8_alloc_begin：打印会话边界——复位行相位 + 权威重建活引用位图。
 * v9 叠加：归属 (win,模板) 变化 → 队列换主，游标置首。
 * 同一队列的连续文本块不重置游标，接着往后排。
 * ==========================================================================*/
void v8_alloc_begin(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    int switched;

    v8q_init_once();
    switched = v8q_is_switch(win);
    if (switched)
        v8q_own(win);

    /* v9.1：场景签名变化 ⇒ 官方极可能重新装载了 VRAM 图形 ⇒ ours 位图整体作废。
     * 同时兜住冷启动：EWRAM 垃圾不保证为 0，首次签名必与当前值不等 ⇒ 走一次清零。 */
    if (v8_scene_sig_changed())
        v8_ours_clear_all();

    *(volatile uint16_t *)ADDR_V8_PHASE     = 0u;
    *(volatile uint16_t *)ADDR_V8_PHASE_ROW = 0u;
    *(volatile uint16_t *)ADDR_V8_LAST_TILE = 0u;
    if (switched)
        *(volatile uint16_t *)ADDR_V8_CURSOR = 0u;   /* ← 切换：游标置首 */

    if (!tpl)
        return;

    /* 活引用重建 = 一次真回收：未被任何 tilemap 引用的旧 bm 位就此放出 */
    v8_rebuild_live(tpl);
}
""",
     "tile_alloc.c 瘦身 v8_alloc_begin")

# --- v13 分配核心 ---
edit("src/text/tile_alloc.c",
     """/* ============================================================================
 * v8_alloc_n：领连续 n 个 tile（v8 原算法；文本与 UI 共用的唯一出口）。
 * 确定性顺序遍历 [lo, hi)，逐候选过 v8_tile_usable（位图 + VRAM 非空 + ours）；
 * 无空闲回卷重扫，再无 → 返回 0（调用方放弃，宁缺不砸 UI）。
 * 分配后推进游标并记入 ours 段表（= 队列账本，相邻自动合并）。
 * ==========================================================================*/
static uint16_t v8_alloc_n(TextPrinter *win, uint16_t n)
{
    uint8_t *tpl = win_template(win);
    uint8_t char_base;
    volatile uint8_t *bm = v8_bitmap();
    const void *vram;
    uint16_t hi, lo, t;
    uint16_t start;
    unsigned i;

    if (!tpl || n == 0u)
        return 0u;
    char_base = tpl[TPL_CHARBASE];
    vram = (const void *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!vram)
        return 0u;
    hi = v8_alloc_hi(char_base);
    /* 🔴 v11（2026-09-11）：起址**不再硬编码、也不再是全局水位** ——
     * 号池起点由 win_alloc.c 统一发放：`v11_pool_reset_C()` 在每次「窗口装载」
     * （① TextLoadWindowTemplate）把游标打回池底，`v10_pool_lo()` 返回本窗口的
     * 池底（发过 UI 框 ⇒ 框之后；否则池底本身）。
     *
     * 修掉的两个病：
     *   ① 旧写法 `lo = max(0x100, v10_text_lo())` 里的 `v10_text_lo()` 是
     *      **全局只增不减**的（P_CALLS/P_TEXT 从来没有复位点）⇒ 每开一次窗
     *      下限往上爬，几十次后 lo≥hi ⇒ 本函数返 0 ⇒ 文字整片空白
     *      （实机「训练家页来回进入后文字为空」）。
     *   ② 硬编码 `0x100` 让框与文字各算各的池底，UI 与文本不是一条序列。
     * 现在框与文字共用同一个游标 + 同一个池底 ⇒ 天然不互相覆盖。 */
    lo = v10_pool_lo();
    if (lo >= hi || (unsigned)(hi - lo) < n)
        return 0u;

    v8q_init_once();
    if (v8q_is_switch(win)) {     /* 未走 begin 就分配：先换主并置首 */
        v8q_own(win);
        *(volatile uint16_t *)ADDR_V8_CURSOR = 0u;
    }
    /* 兜底：begin 之后游戏若在本会话内改了 DISPCNT/BGxCNT，这里也要作废 ours */
    if (v8_scene_sig_changed())
        v8_ours_clear_all();

    start = *(volatile uint16_t *)ADDR_V8_CURSOR;
    if (start < lo || start >= hi)
        start = lo;

    /* 第一遍：从上次游标起 */
    for (t = start; (unsigned)t + n <= (unsigned)hi; t++) {
        int ok = 1;
        for (i = 0; i < n; i++)
            if (!v8_tile_usable(bm, vram, (uint16_t)(t + i))) { ok = 0; break; }
        if (ok) {
            /* 领号即标位图：会话内位图只在 begin 重建，不标的话本串已写
             * 的 tile 在「回卷重扫」时位图看不到（VRAM 非空但 ours→可回收）
             * → 后字 blend 叠进前字 tile = 实机粉框「道/路」重叠团。
             * 会话结束下次 begin 会全量重建，此处标占不跨会话泄漏。 */
            for (i = 0; i < n; i++)
                v8_bit_set(bm, (uint16_t)(t + i));
            *(volatile uint16_t *)ADDR_V8_CURSOR = (uint16_t)(t + n);
            v8_ours_add(t, n);
            return t;
        }
    }
    /* 第二遍：回卷到 lo 重扫（位图已含本会话领号，不会回收自己刚写的字） */
    for (t = lo; (unsigned)t + n <= (unsigned)hi; t++) {
        int ok = 1;
        for (i = 0; i < n; i++)
            if (!v8_tile_usable(bm, vram, (uint16_t)(t + i))) { ok = 0; break; }
        if (ok) {
            for (i = 0; i < n; i++)
                v8_bit_set(bm, (uint16_t)(t + i));
            *(volatile uint16_t *)ADDR_V8_CURSOR = (uint16_t)(t + n);
            v8_ours_add(t, n);
            return t;
        }
    }
    return 0u;                    /* 彻底无空闲：放弃，宁缺不砸 UI */
}

/* ① 主动文本分配：中文 glyph 领 glyph_len 个 tile。 */
uint16_t v8_alloc_tile(TextPrinter *win, uint8_t font_px, uint8_t glyph_len)
{
    (void)font_px;   /* 字号当前只影响 glyph_len（调用方已折算），保留形参备将来 GAP 配置 */
    return v8_alloc_n(win, glyph_len);
}

/* ② UI 分配：图集 / 窗框等 UI 占位领 n 个 tile。
 * 与文本分配共用同一游标、同一 ours 账本 —— UI 先领则文本排在 UI 之后。 */
uint16_t v8_ui_alloc(TextPrinter *win, uint16_t n)
{
    return v8_alloc_n(win, n);
}
""",
     """/* ============================================================================
 * v13 分配核心（2026-09-11）：**文本与 UI 唯一的分配出口**。
 *
 * 分层：
 *   v8_alloc_scan  纯扫描（两遍：游标起 → 回卷到 lo）
 *   v8_mark_frame  补标「本窗框号段」（回收重建后防止误放自己的框）
 *   v8_alloc_core  入口：三次尝试 = 扫描 → 真回收 + 扫描 → 放弃
 * ==========================================================================*/

/* 领到 [t, t+n)：标活引用位图 + 推进游标 + 记 ours。 */
static void v8_take(volatile uint8_t *bm, uint16_t t, uint16_t n)
{
    unsigned i;
    /* 领号即标位图：会话内位图只在 begin / 回收时重建，不标的话本串已写
     * 的 tile 在「回卷重扫」时位图看不到（VRAM 非空但 ours → 可回收）
     * → 后字 blend 叠进前字 tile = 实机粉框「道/路」重叠团。 */
    for (i = 0; i < n; i++)
        v8_bit_set(bm, (uint16_t)(t + i));
    *(volatile uint16_t *)ADDR_V8_CURSOR = (uint16_t)(t + n);
    v8_ours_add(t, n);
}

/* 确定性顺序遍历 [lo, hi)，逐候选过 v8_tile_usable；
 * 第一遍从上次游标起，第二遍回卷到 lo 重扫。找不到 → 0。 */
static uint16_t v8_alloc_scan(uint16_t n, uint16_t lo, uint16_t hi,
                              volatile uint8_t *bm, const void *vram)
{
    uint16_t start = *(volatile uint16_t *)ADDR_V8_CURSOR;
    uint16_t t;
    unsigned i;

    if (start < lo || start >= hi)
        start = lo;

    for (t = start; (unsigned)t + n <= (unsigned)hi; t++) {
        int ok = 1;
        for (i = 0; i < n; i++)
            if (!v8_tile_usable(bm, vram, (uint16_t)(t + i))) { ok = 0; break; }
        if (ok) { v8_take(bm, t, n); return t; }
    }
    for (t = lo; (unsigned)t + n <= (unsigned)hi; t++) {
        int ok = 1;
        for (i = 0; i < n; i++)
            if (!v8_tile_usable(bm, vram, (uint16_t)(t + i))) { ok = 0; break; }
        if (ok) { v8_take(bm, t, n); return t; }
    }
    return 0u;
}

/* 本窗口的框号段补标回位图。
 * 为什么需要：回收走的是「扫 tilemap」重建，而框的 tilemap 由 ⑨b 写，
 * 时序上可能晚于我们的分配；漏标会让回收把自己刚发的框误判成死砖。
 * 读的是**官方自己的字段** 0x03000514（⑤ 写），不另建表。 */
static void v8_mark_frame(void)
{
    volatile uint8_t *bm = v8_bitmap();
    uint16_t base = *(volatile uint16_t *)0x03000514u;
    unsigned i;

    if (base == 0u)
        return;
    for (i = 0; i < V10_FRAME_SPAN; i++)
        v8_bit_set(bm, (uint16_t)(base + i));
}

static uint16_t v8_alloc_core(uint8_t *tpl, uint16_t n)
{
    volatile uint8_t *bm = v8_bitmap();
    const void *vram;
    uint16_t hi, lo, r;

    if (!tpl || n == 0u)
        return 0u;
    vram = (const void *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!vram)
        return 0u;
    hi = v8_alloc_hi(tpl[TPL_CHARBASE]);

    /* 起址下限 = win_alloc.c 发放的本窗口池底（池底 V12_POOL_LO=1，
     * 或本窗口 ⑤ 发过框 ⇒ 框之后）。框与文字因此共享同一条序列。 */
    lo = v10_pool_lo();
    if (lo >= hi || (unsigned)(hi - lo) < n)
        return 0u;

    /* 兜底：begin 之后游戏若在本会话内改了 DISPCNT/BGxCNT，这里也要作废 ours */
    if (v8_scene_sig_changed())
        v8_ours_clear_all();

    r = v8_alloc_scan(n, lo, hi, bm, vram);
    if (r != 0u)
        return r;

    /* ---- v13 真回收（S6）----
     * 两遍都满 ⇒ 重建活引用位图：把「已无任何 tilemap 引用的旧 bm 位
     *（含 negative cache：非空且非 ours 而被永久拉黑的那批）」一次性放掉，
     * 再试一次。这是 `v11_pool_reset_C` 里 `P_V8CUR = 池底` 的正确替代 ——
     * 后者是**假回收**：把整个池子丢掉，别的窗口还活着的号也被抹平，
     * 池子于是永远填不满（用户判据「满池 ⇒ 文字与 UI 一起空白」因此不可达）。
     * 补偿：重建后把本窗框号段补标回去（见 v8_mark_frame）。 */
    v8_rebuild_live(tpl);
    v8_mark_frame();
    return v8_alloc_scan(n, lo, hi, bm, vram);
}

/* ② UI 分配：与文本完全同一条路径（同一个 v8_alloc_core）。 */
uint16_t v8_alloc_ui(uint8_t *tpl, uint16_t n)
{
    return v8_alloc_core(tpl, n);
}

/* 文本分配的包装：补上 v9 的「队列换主」语义（UI 不需要 —— 它不是文本队列）。 */
static uint16_t v8_alloc_n(TextPrinter *win, uint16_t n)
{
    uint8_t *tpl = win_template(win);

    if (!tpl || n == 0u)
        return 0u;
    v8q_init_once();
    if (v8q_is_switch(win)) {     /* 未走 begin 就分配：先换主并置首 */
        v8q_own(win);
        *(volatile uint16_t *)ADDR_V8_CURSOR = 0u;
    }
    return v8_alloc_core(tpl, n);
}

/* ① 主动文本分配：中文 glyph 领 glyph_len 个 tile。 */
uint16_t v8_alloc_tile(TextPrinter *win, uint8_t font_px, uint8_t glyph_len)
{
    (void)font_px;   /* 字号当前只影响 glyph_len（调用方已折算），保留形参备将来 GAP 配置 */
    return v8_alloc_n(win, glyph_len);
}
""",
     "tile_alloc.c v13 分配核心")


# =============================================================================
# 3. include/win_alloc.h —— 删魔数 / 删纯计数器声明
# =============================================================================
edit("include/win_alloc.h",
     """ * v10/v11.1 改法：**只在官方 base 落在我们池子的辖区（≥ 池底）时才改号**，
 *     池外的官方 base（2/18/20/34 这类固定小槽）**原样透传**。见 win_alloc.c
 *     里 `v10_set_frame_base_C` 的 14 个调用点分类表（全盘反汇编实证）。
 *     ⑤ 拿到 C ⇒ ⑦ 把标准框图形装到 tile C；⑤ 返回 C+9 ⇒ ⑥ 记下并返回 C+23
 *     ⇒ ⑧ 把对话框框图形装到 tile C+9。**⑤⑥⑦⑧ 一行汇编都不改**，全自动跟随。""",
     """ * v13 改法（2026-09-11）：⑤ 也走**统一分配器** `v8_alloc_ui` —— 与汉字同一个
 *     `v8_alloc_core`、同一套三层占用校验（活引用位图 / VRAM 非空 / ours）、
 *     同一个游标、同一个 ours 账本。池子给不出连续 23 个砖 ⇒ 返 0 ⇒ 框也不画。
 *     （v11.1 的「官方 base < 池底就原样透传」= 变相不可用区，v12 已删。）
 *     ⑤ 拿到 C ⇒ ⑦ 把标准框图形装到 tile C；⑤ 返回 C+9 ⇒ ⑥ 记下并返回 C+23
 *     ⇒ ⑧ 把对话框框图形装到 tile C+9。**⑤⑥⑦⑧ 一行汇编都不改**，全自动跟随。""",
     "win_alloc.h 头注释 v13")

edit("include/win_alloc.h",
     """ * 取 1 不取 0：`v8_alloc_n` / `v10_frame_alloc` 用 **0 表示「没领到号」**，
 * 0 必须保留为哨兵（砖 0 也从不分配，永远空白）。 */
#define V12_POOL_LO      1u""",
     """ * 取 1 不取 0：`v8_alloc_core` 用 **0 表示「没领到号」**，
 * 0 必须保留为哨兵（砖 0 从不分配；tilemap 里 0 号是「空槽」标记）。 */
#define V12_POOL_LO      1u""",
     "win_alloc.h 池底注释")

edit("include/win_alloc.h",
     """/* 框装载门控 magic（u16 @ ADDR_V12_FRAME_OK）：
 *   V12_OK_MAGIC   = 0x0000 ⇒ ⑦⑧ 正常装载
 *   V12_FAIL_MAGIC = 0xA55A ⇒ 池子满 ⇒ ⑦⑧ 入口直接返回、不装载
 * 🔴 为什么不用「0/0xA5 一个字节」：EWRAM 冷启动是垃圾（mGBA 下多为全 0），
 *    「0 = 失败」会让任何「没跑过 ⑤ 就画框」的窗口把边框整条丢掉。
 *    16 位 magic + **只认精确等于 FAIL** ⇒ 未初始化 / 其他值一律走「装载」。 */
#define V12_OK_MAGIC     0x0000u
#define V12_FAIL_MAGIC   0xA55Au

/* 发一段框号：返回起点 C，游标推进 V10_FRAME_SPAN。⑤ 的 hook 调用。 */
uint16_t v10_frame_alloc(void);

/* 本窗口文字起址下限 = 号池起点：
 *   本窗口还没发过框 ⇒ V11_POOL_LO（池底）；
 *   发过框          ⇒ 框之后（框与文字同一条序列，不会互相压）。
 * ⚠ 该值**按窗口**生效：`v11_pool_reset_C()` 在每次「窗口装载」（①）时清零。 */
uint16_t v10_pool_lo(void);""",
     """/* 本窗口文字起址下限 = 号池起点：
 *   本窗口还没发过框 ⇒ V11_POOL_LO（池底）；
 *   发过框          ⇒ 框之后（框与文字同一条序列，不会互相压）。
 * ⚠ 该值**按窗口**生效：`v11_pool_reset_C()` 在每次「窗口装载」（①）时清零 P_CALLS。
 * 🔴 池子**游标不随窗口复位**（v13）：游标是池子本身的状态，复位它 = 丢掉整个池子。 */
uint16_t v10_pool_lo(void);""",
     "win_alloc.h 删 magic + v10_frame_alloc 声明")

edit("include/win_alloc.h",
     """/* 🆕 v11：**窗口装载 = 号池复位**。由 ① `TextLoadWindowTemplate` @0x08002950
 * 入口钩（entry.s: V11WinInit_Hook）调用。""",
     """/* v11：**窗口装载 = 复位「本窗的文字下限」**。由 ① `TextLoadWindowTemplate`
 * @0x08002950 入口钩（entry.s: V11WinInit_Hook）调用。
 * 🔴 v13 起**不复位池子游标**（旧写法 `P_V8CUR = 池底` = 假回收，见函数内注释）。""",
     "win_alloc.h v11_pool_reset 注释")

edit("include/win_alloc.h",
     """/* ⑤ `TextWindow_SetBaseTileNum` 的替换实现（entry.s 跳板调用）。
 *
 * v12 语义（2026-09-11，用户定义）：
 *   「UI 和文本没有任何区别 —— 一旦分配区分完了，直接就返回空了，
 *     所以到顶 UI 和文字都会空白。」
 *   成功：号来自发号器（`0x03000514 = c`，返回 c+9），ADDR_V12_FRAME_OK = 1；
 *   失败（池子满）：`0x03000514 = 0`、返回 0、**ADDR_V12_FRAME_OK = 0**
 *     ⇒ ⑦⑧ 入口直接返回、不装载框图形 ⇒ 框和字一起空。
 *   ⚠ v11.1 的「官方 base < 池底就原样透传」**已删除**：那是把官方小槽
 *     （2/18/20/34）留成池外私产 = 变相不可用区；v12 起它们同样进分配器。 */
uint16_t v10_set_frame_base_C(uint16_t official_base);

/* v12：把 tile [0, V10_FRAME_SPAN) **清零**（按当前窗口模板的 charBase 基址）。
 * 只在 ⑤ 分配失败时调用一次：框图形不装载 + tilemap 仍指向 0 号小槽
 * ⇒ 必须让那小槽内容为空，否则框位置会露出 0..22 号砖里的旧字。 */
void v12_blank_frame_tiles_C(void);""",
     """/* ⑤ `TextWindow_SetBaseTileNum` 的替换实现（entry.s 跳板调用）。
 *
 * v13 语义（2026-09-11，用户定义）：
 *   「UI 和文本没有任何区别 —— 一旦分配区分完了，直接就返回空了，
 *     所以到顶 UI 和文字都会空白。」
 *   成功：号来自**统一分配器**（`v8_alloc_ui`）→ `0x03000514 = c`，返回 c+9；
 *   失败（池子满）：`0x03000514 = 0`、返回 0 ⇒ ⑦⑧ 的 hook 读到 0 ⇒ 不装载
 *     框图形 ⇒ 框和字一起空。
 *   🔴 不需要任何标志位 / 魔数：`0x03000514` 是官方自己的字段，⑦ 本来就要读它；
 *      `0` = 「没领到号」= 不画，与 `print_glyph` 的 `t0 == 0 ⇒ return` 完全对称。
 *   ⚠ v11.1 的「官方 base < 池底就原样透传」**已删除**：那是把官方小槽
 *     （2/18/20/34）留成池外私产 = 变相不可用区；v12 起它们同样进分配器。 */
uint16_t v10_set_frame_base_C(uint16_t official_base);""",
     "win_alloc.h ⑤ 说明 + 删 blank 声明")


# =============================================================================
# 4. src/text/win_alloc.c
# =============================================================================
edit("src/text/win_alloc.c",
     """#include "win_alloc.h"
#include "game.h\"""",
     """#include "win_alloc.h"
#include "game.h"
#include "tile_alloc.h"   /* v13：⑤ 的框号走统一分配器 v8_alloc_ui */""",
     "win_alloc.c include")

edit("src/text/win_alloc.c",
     """ * v10 改法：**忽略官方传来的 base**，改由本模块从**文字游标**取号。
 *     ⑤ 拿 C ⇒ ⑦ 画在 tile C；⑤ 返回 C+9 ⇒ ⑥ 记下并返回 C+23 ⇒ ⑧ 画在 tile C+9。
 *     ⑤⑥⑦⑧ 一行汇编都不改。""",
     """ * v13 改法：**忽略官方传来的 base**，改由**统一分配器**（v8_alloc_ui）发号。
 *     ⑤ 拿 C ⇒ ⑦ 画在 tile C；⑤ 返回 C+9 ⇒ ⑥ 记下并返回 C+23 ⇒ ⑧ 画在 tile C+9。
 *     ⑤⑥⑦⑧ 一行汇编都不改。""",
     "win_alloc.c 头注释 v13")

edit("src/text/win_alloc.c",
     """ * 🔴 v11（2026-09-11）：号池**按窗口复位**（`v11_pool_reset_C`，① 调用），
 *     池底 = `V11_POOL_LO`。窗口内序列：
 *         本窗: 框 [lo, lo+23) 字 [lo+23, ...)
 *     窗口之间不累积 —— 这才是「来回进入不再越界变空」的根治点。""",
     """ * 🔴 v11/v13（2026-09-11）：① 装载窗口时 `v11_pool_reset_C` 复位**本窗的文字下限**
 *     （P_CALLS / P_TEXT / 行相位），池底 = `V11_POOL_LO`。
 *     ⚠ **不复位池子游标**（v13 改）：v11 曾 `P_V8CUR = 池底`，那等于把整个池子丢掉 ——
 *       别的窗口还活着的号也被抹平，池子于是永远填不满（= 假回收）。
 *       真回收在 tile_alloc.c:v8_alloc_core 的失败路径（重建活引用后重试一次）。""",
     "win_alloc.c 头注释 v11/v13")

edit("src/text/win_alloc.c",
     """/* ============================================================================
 * v11：窗口装载（① `TextLoadWindowTemplate` @0x08002950）＝ 号池复位。
 *
 * 复位「号池」的四件状态，全都在 EWRAM，一个字节的窗口内存都不动：
 *   · 号游标 `ADDR_V8_CURSOR`（框与文字共用） → 池底
 *   · 本窗发框账 P_CALLS / P_TEXT            → 0（文字因此从池底起算）
 *   · 行相位三件（px / 行标识 / 末尾列 tile） → 0
 *
 * 为什么这是「根治」而不是「缓解」：""",
     """/* ============================================================================
 * v11/v13：窗口装载（① `TextLoadWindowTemplate` @0x08002950）＝ 复位**本窗**
 * 的文字下限与行相位，全在 EWRAM，一个字节的窗口内存都不动：
 *   · 本窗发框账 P_CALLS / P_TEXT            → 0（文字因此从池底起算）
 *   · 行相位三件（px / 行标识 / 末尾列 tile） → 0
 *   🔴 v13 起**不再复位号游标** `ADDR_V8_CURSOR`：
 *      v11 的 `P_V8CUR = V11_POOL_LO` 是**假回收** —— 把整个池子丢掉（别的窗口
 *      还活着的号一起被抹平），代价是池子永远填不满，「满池 ⇒ 一起空白」不可达。
 *      真回收 = tile_alloc.c 的失败路径重建活引用位图（只还死掉的砖）。
 *
 * 下面这段保留，记录 v11 修掉的病：""",
     "win_alloc.c v11_pool_reset 注释头")

edit("src/text/win_alloc.c",
     """void v11_pool_reset_C(void)
{
    P_MAGIC = V10W_MAGIC;
    P_CALLS = 0u;
    P_TEXT  = 0u;
    P_V8CUR = V11_POOL_LO;

    *(volatile uint16_t *)ADDR_V8_PHASE     = 0u;
    *(volatile uint16_t *)ADDR_V8_PHASE_ROW = 0u;
    *(volatile uint16_t *)ADDR_V8_LAST_TILE = 0u;

    /* v12：新窗口默认「框号可发」；⑤ 发不出号时才会清 0。 */
    *(volatile uint16_t *)ADDR_V12_FRAME_OK = V12_OK_MAGIC;
}""",
     """void v11_pool_reset_C(void)
{
    v10w_init_once();

    P_CALLS = 0u;
    P_TEXT  = 0u;
    /* 🔴 v13：不动 P_V8CUR。游标是**池子**的状态，不是窗口的状态；
     * 复位它 = 丢掉整个池子（假回收），池子于是永远填不满。 */

    *(volatile uint16_t *)ADDR_V8_PHASE     = 0u;
    *(volatile uint16_t *)ADDR_V8_PHASE_ROW = 0u;
    *(volatile uint16_t *)ADDR_V8_LAST_TILE = 0u;
}""",
     "win_alloc.c v11_pool_reset_C 函数体")

edit("src/text/win_alloc.c",
     """/* 发一段框号（V10_FRAME_SPAN 个 tile）。返回起点 C。⑤ 的 hook 调用。 */
uint16_t v10_frame_alloc(void)
{
    uint16_t c, hi;

    v10w_init_once();
    hi = v10w_hi();
    P_HI = hi;

    c = P_V8CUR;
    if (c < V11_POOL_LO)
        c = V11_POOL_LO;                         /* 冷启动 / 复位后：从池底起排 */

    /* 🔴 v12（2026-09-11）：**不再回卷**。池子到顶 = 返 0 = 框不发号。
     * 旧写法 `c = V11_POOL_LO`（回卷）⇒ 框永远画得出来 ⇒ 实测「文字空、UI 不空」，
     * 正是用户给出的永久判据「文字耗尽而 UI 不空 ⇒ UI 未接入」。
     * 现在：发不出发号 = 池子有没有空位，UI 与文本同一条判据。 */
    if ((unsigned)c + V10_FRAME_SPAN > (unsigned)hi)
        return 0u;

    P_V8CUR = (uint16_t)(c + V10_FRAME_SPAN);
    P_TEXT  = P_V8CUR;                           /* 本窗口文字从这里开始 */
    P_CALLS++;
    return c;
}

""",
     """""",
     "win_alloc.c 删 v10_frame_alloc")


# =============================================================================
# 5. src/text/win_alloc.c —— ⑤ 实现 + 删 v12_blank_frame_tiles_C
# =============================================================================
edit("src/text/win_alloc.c",
     """/* ============================================================================
 * ⑤ `TextWindow_SetBaseTileNum` @0x08062080 的替换实现（entry.s 跳板调用）。
 *                                                            2026-09-11 v12
 *
 * 官方原语义：{ sTextWindowBaseTileNum = base; return base + 9; }
 *
 * v12 语义 = **UI 与文本完全没有区别**（用户原话：「一旦分配区分完了，
 *   直接就返回空了，所以到顶 UI 和文字都会空白」）：
 *     能领到号 ⇒ 正常装载框图形（⑦⑧，号由⑦⑧从 0x03000514/0x03000516 读）；
 *     领不到号 ⇒ 返回 0 + 清 ADDR_V12_FRAME_OK + 把 0 号小槽清零
 *              ⇒ ⑦⑧ 不装载、⑨b 把框 tilemap 填到空白小槽 ⇒ **框也空白**。
 *
 * 🔴 v11.1 的「官方 base < 池底就原样透传」**已删除**（连同 0x100 池底一起）：
 *   全盘扫 `bl 0x08062080` 的 14 个调用点里，11 处传固定小常量 2/18/20/34。
 *   把它们留成「池外私产」= 变相不可用区（用户明令禁止「设置不可用区」），
 *   而且池子撤到 1 之后，我们的号本来就会分配进那片区域 ⇒ 官方框图形会
 *   反过来盖掉我们的字。v12 起它们同样进分配器：号与 tilemap 同源，不再打架。
 *   （活着的官方层仍有活引用位图 bm 兜底，见 tile_alloc.c:v8_tile_usable。）
 * ==========================================================================*/
/* v12：把 tile [0, V10_FRAME_SPAN) 清零（按当前窗口模板的 charBase 相对基址）。
 * ⑤ 分配失败时调用一次 —— 框图形不装载，但 ⑨b 仍会把框填进 tilemap，
 * 且填的正是 `0x03000514`（此时 = 0）起的 0..22 号砖。不清零的话那里
 * 会露出池子里已分配的旧字。 */
void v12_blank_frame_tiles_C(void)
{
    uint8_t *tpl = *(uint8_t *volatile *)0x03000328u;
    uint32_t base;
    volatile uint32_t *dst;
    unsigned i;

    if (!tpl)
        return;
    base = win_u32(tpl, TPL_TILE_DATA);      /* 0x06000000 + charBase*0x4000 */
    if (!base)
        return;
    dst = (volatile uint32_t *)(uintptr_t)base;
    for (i = 0; i < V10_FRAME_SPAN * 8u; i++)  /* 23 tile × 32B ÷ 4B = 184 word */
        dst[i] = 0u;
}

uint16_t v10_set_frame_base_C(uint16_t official_base)
{
    uint16_t c;

    (void)official_base;   /* v12：官方给的号一律不再采用（UI 与文本同权，无例外） */

    c = v10_frame_alloc();
    if (c == 0u)
    {
        /* —— 池子满：和文字一样「返回空」——
         * ① 标志清 0 ⇒ ⑦⑧ 入口直接返回，框图形不装载；
         * ② `0x03000514` 写 0 ⇒ ⑨b 把框 tilemap 填到 0 号小槽；
         * ③ 0 号小槽清零 ⇒ 那处渲出空白。
         * 三者合起来才是「到顶 UI 也空白」；只做 ① 会露出池里旧字，
         * 只做 ② 会露出官方框图形（= 用户实测「文字空、UI 不空」）。 */
        *(volatile uint16_t *)ADDR_V12_FRAME_OK = V12_FAIL_MAGIC;
        *(volatile uint16_t *)0x03000514u = 0u;   /* sTextWindowBaseTileNum */
        v12_blank_frame_tiles_C();
        return 0u;                                 /* ⑥ 收到 0 ⇒ 0x03000516 = 0 */
    }

    *(volatile uint16_t *)ADDR_V12_FRAME_OK = V12_OK_MAGIC;   /* ⑦⑧ 正常装载 */
    *(volatile uint16_t *)0x03000514u = c;         /* sTextWindowBaseTileNum */
    return (uint16_t)(c + 9u);
}""",
     """/* ============================================================================
 * ⑤ `TextWindow_SetBaseTileNum` @0x08062080 的替换实现（entry.s 跳板调用）。
 *                                                            2026-09-11 v13
 *
 * 官方原语义：{ sTextWindowBaseTileNum = base; return base + 9; }
 *
 * v13 语义 = **UI 与文本完全没有区别**（用户原话：「一旦分配区分完了，
 *   直接就返回空了，所以到顶 UI 和文字都会空白」）：
 *     框号从**统一分配器**领（`v8_alloc_ui` → `v8_alloc_core`，和汉字同一个
 *     函数、同一套占用校验、同一个游标）；
 *     领到 ⇒ `0x03000514 = c`，返回 c+9 ⇒ ⑦⑧ 照常装载；
 *     领不到 ⇒ `0x03000514 = 0`，返回 0 ⇒ ⑦⑧ 读到 0 就不装载 ⇒ 框空白。
 *
 * 🔴 v12 的「ADDR_V12_FRAME_OK 魔数 + 只认 0xA55A + 0 号小槽清零」**已删**：
 *   那是自造侧信道。`0x03000514` 本就是官方字段、⑦ 本来就要读它，
 *   `0` = 没领到号 = 不画 —— 与 `print_glyph` 的 `t0 == 0 ⇒ return` 完全对称。
 *   也不需要清零小槽：⑦⑧ 既然不装载，框就画不出来。
 *
 * 🔴 v11.1 的「官方 base < 池底就原样透传」**已删除**（连同 0x100 池底一起）：
 *   全盘扫 `bl 0x08062080` 的 14 个调用点里，11 处传固定小常量 2/18/20/34。
 *   把它们留成「池外私产」= 变相不可用区（用户明令禁止「设置不可用区」），
 *   而且池子撤到 1 之后，我们的号本来就会分配进那片区域 ⇒ 官方框图形会
 *   反过来盖掉我们的字。v12 起它们同样进分配器：号与 tilemap 同源，不再打架。
 *   （活着的官方层仍有活引用位图 bm 兜底，见 tile_alloc.c:v8_tile_usable。）
 * ==========================================================================*/
uint16_t v10_set_frame_base_C(uint16_t official_base)
{
    uint8_t *tpl = *(uint8_t *volatile *)0x03000328u;   /* ① 写的本窗模板 */
    uint16_t c;

    (void)official_base;   /* v12 起：官方给的号一律不再采用（UI 与文本同权） */

    v10w_init_once();
    P_HI = v10w_hi();

    c = v8_alloc_ui(tpl, V10_FRAME_SPAN);   /* ← 与汉字同一条路径 */
    if (c == 0u)
    {
        /* 池子满：和文字一样「返回空」。⑦⑧ 的 hook 读到 0 ⇒ 不装载框图形。 */
        *(volatile uint16_t *)0x03000514u = 0u;   /* sTextWindowBaseTileNum */
        return 0u;                                /* ⑥ 收到 0 ⇒ 0x03000516 = 0 */
    }

    /* v8_alloc_ui 已把 ADDR_V8_CURSOR 推到 c + V10_FRAME_SPAN，这里只记文字下限 */
    P_TEXT = P_V8CUR;
    P_CALLS++;
    *(volatile uint16_t *)0x03000514u = c;         /* sTextWindowBaseTileNum */
    return (uint16_t)(c + 9u);
}""",
     "win_alloc.c ⑤ 实现")

# v10w_init_once 里删掉 V12 标志
edit("src/text/win_alloc.c",
     """    /* 冷启动把游标按到池底：EWRAM 内容是垃圾，不按会出现任意号 */
    P_V8CUR = V11_POOL_LO;
    /* v12：新窗口默认「框号可发」；只有 ⑤ 真的发不出号才置 0。 */
    *(volatile uint16_t *)ADDR_V12_FRAME_OK = V12_OK_MAGIC;
}""",
     """    /* 冷启动把游标按到池底：EWRAM 内容是垃圾，不按会出现任意号 */
    P_V8CUR = V11_POOL_LO;
}""",
     "win_alloc.c v10w_init_once 删标志")


# =============================================================================
# 6. src/text/entry.s —— ⑦⑧ 门控改读官方字段
# =============================================================================
edit("src/text/entry.s",
     """@ =============================================================================
@ [v12] 图集封堵 + 框装载门控（2026-09-11）
@ 「UI 与文本同权」的收口：分配器满 ⇒ 文字不画（既有）+ 框也不画（本组）。
@ 桩见 hooks_origin.s；ADDR_V12_FRAME_OK = 0x0203FF56（game.h）。
@ =============================================================================""",
     """@ =============================================================================
@ [v12/v13] 图集封堵 + 框装载门控（2026-09-11）
@ v13 起「UI 与文本同权」是一条真路径：⑤ 也调 `v8_alloc_ui`（与汉字同一个
@ `v8_alloc_core`），池子给不出号 ⇒ ⑤ 返 0 + `0x03000514 = 0`
@ ⇒ ⑦⑧ 读到 0 就不装载框图形 ⇒ 框和字一起空。
@ 🔴 v12 的 ADDR_V12_FRAME_OK 魔数门控（0xA55A / 只认精确相等）**已删** ——
@   自造侧信道。门控改读**官方自己的字段** `0x03000514` / `0x03000516`。
@ 桩见 hooks_origin.s。
@ =============================================================================""",
     "entry.s v12/v13 段头")

edit("src/text/entry.s",
     """@ 失败路径（ADDR_V12_FRAME_OK == V12_FAIL_MAGIC 0xA55A，池子满）：
@   pop 掉桩压的两个再返回，**不装载**。
@ ⚠ 门控只认**精确等于** 0xA55A：EWRAM 冷启动是垃圾（mGBA 多为全 0），
@   若写成「0 = 失败」，没跑过 ⑤ 就画框的窗口会把边框整条丢掉。""",
     """@ 失败路径（`0x03000514 == 0`，= 池子没发出号）：pop 掉桩压的两个再返回，**不装载**。
@ 🔴 v13 门控读的是**官方自己的字段** `0x03000514`（⑤ 写、原体本来就要读它）——
@   不再自造魔数 / 侧信道。`0` = 没领到号 = 不画，与 `print_glyph` 的
@   `t0 == 0 ⇒ return` 完全对称（⑤ 成功时该字段必然是 1..1023）。""",
     "entry.s ⑦ 门控注释")

edit("src/text/entry.s",
     """V12StdFrame_Hook:
    ldr     r4, =0x0203FF56            @ ADDR_V12_FRAME_OK
    ldrh    r4, [r4]
    ldr     r3, =0xA55A                @ V12_FAIL_MAGIC
    cmp     r4, r3
    beq     StdFrame_Skip
    ldr     r0, [r0]                   @ 重放 0x08004254（内联）：win → tpl""",
     """V12StdFrame_Hook:
    ldr     r3, =0x03000514            @ 官方框号槽（⑤ 写）
    ldrh    r3, [r3]
    cmp     r3, #0                     @ 0 = 池子没发出号 ⇒ 不装载
    beq     StdFrame_Skip
    ldr     r0, [r0]                   @ 重放 0x08004254（内联）：win → tpl""",
     "entry.s ⑦ 门控码")

edit("src/text/entry.s",
     """V12DlgFrame_Hook:
    ldr     r3, =0x0203FF56            @ ADDR_V12_FRAME_OK
    ldrh    r3, [r3]
    ldr     r2, =0xA55A                @ V12_FAIL_MAGIC（只认精确相等）
    cmp     r3, r2
    beq     DlgFrame_Skip""",
     """V12DlgFrame_Hook:
    ldr     r3, =0x03000516            @ 官方对话框框号槽（⑥ 写）
    ldrh    r3, [r3]
    cmp     r3, #0                     @ 0 = 池子没发出号 ⇒ 不装载
    beq     DlgFrame_Skip""",
     "entry.s ⑧ 门控码")


# =============================================================================
# 7. include/game.h —— 删 ADDR_V12_FRAME_OK
# =============================================================================
edit("include/game.h",
     """/* --- 手工追加（非生成区）：v12 框号分配成败标志（2026-09-11）-----------------
 * ⑤ 分配成功 = V12_OK_MAGIC   (0x0000) ⇒ ⑦ `0x08062094` / ⑧ `0x08062684` 正常装载框图形；
 * ⑤ 分配失败 = V12_FAIL_MAGIC (0xA55A) ⇒ ⑦⑧ 入口直接返回，不装载。
 * 🔴 ⑦⑧ **只认精确等于 0xA55A**：EWRAM 冷启动是垃圾（mGBA 多为全 0），
 *    若写成「0 = 失败」，任何「没跑过 ⑤ 就画框」的窗口都会把边框整条丢掉。
 * 这是「UI 与文本同权」的收口：分配器满 ⇒ 文字不画（既有）+ 框也不画。
 * 落 0x0203FF56：夹在 ADDR_V8Q_END(..0x0203FF55) 与 ADDR_V8Q_TPL(0x0203FF58..) 之间。 */
#define ADDR_V12_FRAME_OK                  0x0203FF56u
""",
     """""",
     "game.h 删 ADDR_V12_FRAME_OK")

# =============================================================================
# 8. game_addrs.asm —— 删 V12FrameOk
# =============================================================================
edit("game_addrs.asm",
     """;   ⇒ ⑤ 发号失败（池子满）时，⑦⑧ 必须**不装载**，否则框图形会盖在 0 号小槽上
;     —— 「文字空、UI 不空」就是漏了这一条。v12 用 ADDR_V12_FRAME_OK 标志门控。""",
     """;   ⇒ ⑤ 发号失败（池子满）时，⑦⑧ 必须**不装载**。v13 门控直接读官方字段
;     `0x03000514`（⑦）/ `0x03000516`（⑧）：0 = 池子没发出号 = 不画。
;     不再有 ADDR_V12_FRAME_OK 魔数（v12 的自造侧信道，已删）。""",
     "game_addrs.asm 注释")

edit("game_addrs.asm",
     """; v12 框号分配成功标志（u16）：⑤ 成功=1（⑦⑧ 正常装载）/ 失败=0（⑦⑧ 直接返回）。
; 落 0x0203FF56——V8Q_END(..0x55) 与 V8Q_TPL(0x58..) 之间的空档，全仓零引用。
V12FrameOk                             equ 0x0203FF56  ; C: ADDR_V12_FRAME_OK
""",
     """""",
     "game_addrs.asm 删 V12FrameOk")

# =============================================================================
# 9. src/text/hooks_origin.s —— ⑦⑧ 注释同步
# =============================================================================
edit("src/text/hooks_origin.s",
     """; [v12] 图集封堵 + 框装载门控（2026-09-11）
; 「UI 与文本同权」的收口：分配器满 ⇒ 文字不画（既有）+ 框也不画（本组）。""",
     """; [v12/v13] 图集封堵 + 框装载门控（2026-09-11）
; v13：「UI 与文本同权」= ⑤ 也走 v8_alloc_ui（同一个 v8_alloc_core）；
;   池子满 ⇒ ⑤ 返 0 + 0x03000514 = 0 ⇒ ⑦⑧ 的 hook 读到 0 就不装载。""",
     "hooks_origin.s 段头")

edit("src/text/hooks_origin.s",
     """; ⑦ TextWindow_LoadStdFrameGraphics @0x08062094 —— 框号分配失败时**不装载**""",
     """; ⑦ TextWindow_LoadStdFrameGraphics @0x08062094 —— 框号 == 0 时**不装载**""",
     "hooks_origin.s ⑦ 小标题")


def main():
    files = {}
    for rel in sorted({e[0] for e in EDITS}):
        p = ROOT / rel
        if not p.exists():
            print("FAIL: 文件不存在 %s" % p)
            return 2
        files[rel] = load(p)

    ok = 0
    for rel, old, new, tag, count in EDITS:
        text, eol = files[rel]
        n = text.count(old)
        if n != count:
            print("FAIL [%s] %s: 期望 %d 处，实际 %d 处" % (rel, tag, count, n))
            return 2
        files[rel] = (text.replace(old, new), eol)
        ok += 1
        print("  ok  %-24s %s" % (rel, tag))

    for rel, (text, eol) in files.items():
        save(ROOT / rel, text, eol)
        print("  write %s (%s)" % (rel, "CRLF" if eol == "\r\n" else "LF"))

    print("\n全部 %d 处替换完成，%d 个文件已写盘。" % (ok, len(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
