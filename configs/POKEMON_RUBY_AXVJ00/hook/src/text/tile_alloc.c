/* ============================================================================
 * tile_alloc.c — v8 动态 tile 分配器 + v9 队列记账层（2026-09-09）
 *
 * ── 分配算法：v8 原样保留，一个字节都不改 ────────────────────────────────
 *   ① 活引用层（权威，防砸屏上正在显示的字）：
 *      v8_alloc_begin 清零重建位图——扫 win 自身 tilemap + DISPCNT 所有启用 BG
 *      中同 charBase 的 screenblock（BGxCNT.size 位定扫描范围，affine/位图 BG 跳过）。
 *   ② VRAM 非空层（补活引用扫不到的官方占用）：alloc 时对候选 tile 实时校验
 *      32B 全空。覆盖 atlas 字库区、begin 之后才绘制的官方 UI、LZ 解压图形。
 *   ③ ours 段表（回收我们自己写过的残留 glyph）：非空 tile 仅当记录在 ours
 *      段表才允许重写；官方数据/atlas 永不在表内 → 永不回收。
 *   ④ screenblock 内存保留：tilemap 区本身（含零槽位）整段标占。
 *   起址 lo = 0x100（256），上界 hi = (4-char_base)*512 clamp 1024（OBJ 隔离）。
 *
 * ── 队列记账层（v9 新增，**不改分配算法**）────────────────────────────────
 *   队列 = 本窗「自本次开窗以来已发出的号」的记录，游标 = 分配扫描起点。
 *     · 切换（**win + 模板双键**）→ 游标置首（回到 lo，重新从队首开始记）
 *       双键原因：日版复用同一个 TextPrinter 挂不同模板（日志实证
 *       win=0x0202E658 同时挂过 tpl=0x081BB49C 与 0x081BB7E4），
 *       只比 win 会漏判 → 游标不复位 → 一路吃到上界 → 整窗不画（全白）。
 *     · 两个消费者共用同一游标、同一账本：
 *         ① 主动文本分配 v8_alloc_tile
 *         ② UI 分配      v8_ui_alloc
 *       谁先谁后由调用顺序决定，UI 先领则文本排在 UI 之后。
 *   记账落 ours 段表（相邻自动合并），即「本窗这轮占了哪些 tile」的账本。
 *
 * ⚠ 2026-09-09 事故：曾把「移除扫描逻辑」理解成「拆掉分配器的占用校验」，
 *   起址从 0x100 挪到 win[0x16](=1) → 落进官方图集区 → 设置页撞 UI（用户实机）。
 *   **分配算法（起址 lo / 位图 / VRAM 非空校验 / ours）禁止再动**；
 *   要改只能改记账层。「移除扫描」指的是避让带勘探，不是分配器的占用校验。
 * ==========================================================================*/
#include "tile_alloc.h"

/* 占用位图：128 字节 = 1024 bit = tile 相对号 0~1023。 */
#define V8_BITMAP_WORDS  128u   /* 1024 bit / 8 */

/* ours 段表容量：80B = magic(2B) + pad(2B) + 19 段 × 4B */
#define V8_OURS_SEG_N    19u
#define V8_OURS_MAGIC    0xA5C3u

/* 队列归属键 magic（与 ours 表分开，独立校验冷启动） */
#define V8Q_MAGIC          0x5A3Cu

#define REG_V8_DISPCNT     (*(volatile uint16_t *)0x04000000u)
#define REG_V8_BGxCNT(bg)  (*(volatile uint16_t *)(0x04000008u + (bg) * 2u))

static volatile uint8_t *v8_bitmap(void)
{
    return (volatile uint8_t *)ADDR_V7_ALLOC_STATE;
}

static void v8_bit_set(volatile uint8_t *bm, uint16_t tile)
{
    bm[tile >> 3] |= (uint8_t)(1u << (tile & 7u));
}

static int v8_bit_get(const volatile uint8_t *bm, uint16_t tile)
{
    return (bm[tile >> 3] >> (tile & 7u)) & 1u;
}

static void v8_bit_clear_all(volatile uint8_t *bm)
{
    unsigned i;
    for (i = 0; i < V8_BITMAP_WORDS; i++)
        bm[i] = 0u;
}

/* ---- ours 段表（EWRAM 0x0203FF80）--------------------------------------
 * raw[0]=magic；seg[i] = {raw[2+i*2]=start, raw[3+i*2]=len}。
 * GBA 冷启动 EWRAM 内容不保证零（game.bin 无 .bss 加载器），magic 一次校验：
 * 非 magic → 整表清零并落 magic（垃圾恰好等于 magic 且段又合法的概率可忽略；
 * 即便误判，后果只是某个 tile 被多一次回收机会，不是直接砸字）。 */
static volatile uint16_t *v8_ours_raw(void)
{
    return (volatile uint16_t *)ADDR_V8_OURS_SEGS;
}

static void v8_ours_init_once(void)
{
    volatile uint16_t *raw = v8_ours_raw();
    unsigned i;
    if (raw[0] == V8_OURS_MAGIC)
        return;
    raw[0] = V8_OURS_MAGIC;
    for (i = 1; i < 2u + V8_OURS_SEG_N * 2u; i++)
        raw[i] = 0u;
}

static uint16_t v8_seg_start(unsigned i)
{
    return v8_ours_raw()[2u + i * 2u];
}

static uint16_t v8_seg_len(unsigned i)
{
    return v8_ours_raw()[3u + i * 2u];
}

static void v8_seg_set(unsigned i, uint16_t start, uint16_t len)
{
    v8_ours_raw()[2u + i * 2u] = start;
    v8_ours_raw()[3u + i * 2u] = len;
}

static int v8_in_ours(uint16_t t)
{
    unsigned i;
    for (i = 0; i < V8_OURS_SEG_N; i++) {
        uint16_t st = v8_seg_start(i);
        uint16_t ln = v8_seg_len(i);
        if (ln != 0u && (uint16_t)(t - st) < ln)
            return 1;
    }
    return 0;
}

static void v8_ours_add(uint16_t t, uint16_t len)
{
    unsigned i;
    /* 并入相邻段 / 重复段去重 */
    for (i = 0; i < V8_OURS_SEG_N; i++) {
        uint16_t st = v8_seg_start(i);
        uint16_t ln = v8_seg_len(i);
        if (ln == 0u)
            continue;
        if ((uint16_t)(st + ln) == t) {                 /* 后接 */
            v8_seg_set(i, st, (uint16_t)(ln + len));
            return;
        }
        if ((uint16_t)(t + len) == st) {                /* 前接 */
            v8_seg_set(i, t, (uint16_t)(ln + len));
            return;
        }
        if ((uint16_t)(t - st) < ln)                    /* 已包含 */
            return;
    }
    /* 无相邻：淘汰最旧（seg[0]），整体前移，新段入尾 */
    for (i = 0; i + 1u < V8_OURS_SEG_N; i++)
        v8_seg_set(i, v8_seg_start(i + 1u), v8_seg_len(i + 1u));
    v8_seg_set(V8_OURS_SEG_N - 1u, t, len);
}

/* 分配上界（charBase 相对号）：避免落入 OBJ 精灵 charBlock（cb4/5 物理隔离）。
 * char_base=0/1/2 -> 1024；char_base=3 -> 512（相对 512+ = 物理 cb4 = OBJ 区）。 */
static uint16_t v8_alloc_hi(uint8_t char_base)
{
    unsigned hi = (char_base < 4u) ? (unsigned)(4u - char_base) * 512u : 0u;
    if (hi > 1024u)
        hi = 1024u;
    return (uint16_t)hi;
}

/* 单 tile 可用性：位图未标（无活引用）且（VRAM 全空 或 属 ours 可回收）。
 * 负缓存：判定「非空且非 ours」后立即标进位图——同一 tile 在本会话内
 * 最多做一次 32B VRAM 读，回卷重扫时全走位图（2026-09-07 性能优化）。
 * 方向保守：标了占用只会让我们不写它，官方清空后我们暂不回收该 tile，
 * 宁可浪费不可错写。 */
static int v8_tile_usable(volatile uint8_t *bm, const void *vram, uint16_t t)
{
    const volatile uint32_t *p;
    if (v8_bit_get(bm, t))
        return 0;
    p = (const volatile uint32_t *)((const volatile uint8_t *)vram
                                    + (unsigned)t * 32u);
    if (p[0] | p[1] | p[2] | p[3] | p[4] | p[5] | p[6] | p[7]) {
        if (!v8_in_ours(t)) {
            v8_bit_set(bm, t);
            return 0;
        }
        return 1;
    }
    return 1;
}

/* ⚠ begin 节流（同帧同签名跳过重建）已于 2026-09-07 实测证伪删除：
 * 继续菜单一帧内关旧窗开新窗，DISPCNT/BGxCNT 不变、VCOUNT 未回绕 →
 * 位图过期，新窗 tile 引用不在位图且图形未写入（先 tilemap 后图形，
 * 非空层拦不住）→ 中文压上新窗 = 疯狂撞（用户实机截图）。
 * 教训：活引用重建是权威层，任何「跳过」都是在赌官方时序，不赌。 */

/* 表项扫描（活引用收集）：优先 u32 读（VRAM 32-bit 总线，一次取 2 表项，
 * 成本减半）；n 为表项数。地址非 4 对齐时退回 u16 逐项。 */
static void v8_scan_entries(const uint16_t *sb, unsigned n, volatile uint8_t *bm)
{
    unsigned i;

    if ((((uintptr_t)sb) & 3u) == 0u) {
        const volatile uint32_t *p = (const volatile uint32_t *)(const void *)sb;
        for (i = 0; i + 1u < n; i += 2u) {
            uint32_t w = p[i >> 1];
            uint16_t t0 = (uint16_t)(w & 0x3FFu);
            uint16_t t1 = (uint16_t)((w >> 16) & 0x3FFu);
            if (t0 != 0u)
                v8_bit_set(bm, t0);
            if (t1 != 0u)
                v8_bit_set(bm, t1);
        }
        if (i < n) {              /* n 为奇数时的收尾（实际 n 恒偶） */
            uint16_t t = sb[i] & 0x3FFu;
            if (t != 0u)
                v8_bit_set(bm, t);
        }
    } else {
        for (i = 0; i < n; i++) {
            uint16_t t = sb[i] & 0x3FFu;
            if (t != 0u)
                v8_bit_set(bm, t);
        }
    }
}

/* ============================================================================
 * 队列记账层（v9）：身份键 = (win, 模板)。
 * 只记录「当前队列归属谁」，用于切换时把分配游标置首；
 * 「本窗占了哪些 tile」的账本就是 ours 段表（v8_ours_add 已在记）。
 * ==========================================================================*/
#define V8Q_P_WIN          (*(volatile uint32_t *)ADDR_V8Q_WIN)
#define V8Q_P_TPL          (*(volatile uint32_t *)ADDR_V8Q_TPL)

static void v8q_init_once(void)
{
    if (*(volatile uint16_t *)ADDR_V8Q_MAGIC == V8Q_MAGIC)
        return;
    *(volatile uint16_t *)ADDR_V8Q_MAGIC = V8Q_MAGIC;
    V8Q_P_WIN = 0u;
    V8Q_P_TPL = 0u;
}

/* 归属判定：win 或模板任一变化即视为切换。 */
static int v8q_is_switch(TextPrinter *win)
{
    return (V8Q_P_WIN != (uint32_t)(uintptr_t)win)
        || (V8Q_P_TPL != (uint32_t)(uintptr_t)win_template(win));
}

static void v8q_own(TextPrinter *win)
{
    V8Q_P_WIN = (uint32_t)(uintptr_t)win;
    V8Q_P_TPL = (uint32_t)(uintptr_t)win_template(win);
}

/* ============================================================================
 * v8_alloc_begin：打印会话边界——复位游标/相位 + 权威重建活引用位图。
 * ① win 自身 tilemap（防御 tilemap 不在 screenblock 的缓冲直绘变体）；
 * ② DISPCNT 启用的每个 text BG：BGxCNT.charBase == 本窗 charBase 时，
 *    按其 size 位扫整个 screenblock。
 * ③ screenblock 内存保留：各启用 BG 的 tilemap 内存区（含零槽位）整段标占。
 * 每会话全量重建，无任何跳过路径（节流已实证证伪，见上文教训）。
 *
 * v9 叠加：归属 (win,模板) 变化 → 队列换主，游标置首。
 * 同一队列的连续文本块不重置游标，接着往后排。
 * ==========================================================================*/
/* 绝对地址区间 [start,end) 折算为本窗 charBase 相对 tile 段并整段标占；
 * 超出本窗可分配地址范围 [cb_base, cb_base + hi*32) 的部分自动裁掉。 */
static void v8_reserve_mem(volatile uint8_t *bm, uintptr_t start, uintptr_t end,
                           uintptr_t cb_base, uint16_t hi)
{
    uintptr_t hi_addr = cb_base + (unsigned)hi * 32u;
    uintptr_t s = (start > cb_base) ? start : cb_base;
    uintptr_t e = (end < hi_addr) ? end : hi_addr;
    uint16_t t0, t1;

    if (s >= e)
        return;
    t0 = (uint16_t)((s - cb_base) / 32u);
    t1 = (uint16_t)((e - cb_base + 31u) / 32u);
    for (; t0 < t1; t0++)
        v8_bit_set(bm, t0);
}

void v8_alloc_begin(TextPrinter *win)
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

    *(volatile uint16_t *)ADDR_V8_PHASE     = 0u;
    *(volatile uint16_t *)ADDR_V8_PHASE_ROW = 0u;
    *(volatile uint16_t *)ADDR_V8_LAST_TILE = 0u;
    if (switched)
        *(volatile uint16_t *)ADDR_V8_CURSOR = 0u;   /* ← 切换：游标置首 */

    if (!tpl)
        return;
    cb = tpl[TPL_CHARBASE];
    v8_ours_init_once();

    v8_bit_clear_all(bm);

    /* ① win 自身 tilemap */
    {
        const uint16_t *tilemap = (const uint16_t *)(uintptr_t)win_u32(tpl, TPL_TILEMAP);
        if (tilemap)
            v8_scan_entries(tilemap, 1024u, bm);
    }

    /* ② 全 BG 同 charBase 的 screenblock 活引用 + ③ screenblock 内存保留 */
    {
        uint16_t dis = REG_V8_DISPCNT;
        uint8_t mode = (uint8_t)(dis & 7u);
        uintptr_t cb_base = 0x06000000u + (uintptr_t)cb * 0x4000u;
        uint16_t hi = v8_alloc_hi(cb);

        for (bg = 0; bg < 4u; bg++) {
            uint16_t cnt;
            const uint16_t *sb;
            unsigned size, n;

            if (!(dis & (uint16_t)(0x100u << bg)))
                continue;
            /* mode≠0 时 BG2/BG3 可能是 affine 或位图层：表项不是 10bit tile 号 */
            if (bg >= 2u && mode != 0u)
                continue;
            cnt = REG_V8_BGxCNT((uint8_t)bg);
            if (((cnt >> 2) & 3u) != cb)
                continue;
            sb = (const uint16_t *)(uintptr_t)
                 (0x06000000u + (unsigned)((cnt >> 8) & 0x1Fu) * 0x800u);
            size = (unsigned)(cnt >> 14) & 3u;
            n = (size == 0u) ? 1024u : (size == 3u) ? 4096u : 2048u;
            v8_scan_entries(sb, n, bm);
        }

        /* ③ 各启用 BG 的 tilemap 内存区整段保留（含零槽位、含跨 charBase） */
        for (bg = 0; bg < 4u; bg++) {
            uint16_t cnt;
            uintptr_t sb_addr, sb_end;
            unsigned sz;

            if (!(dis & (uint16_t)(0x100u << bg)))
                continue;
            /* 位图模式 BG2/BG3 是帧缓冲，无 screenblock 可言 */
            if (bg >= 2u && mode >= 3u)
                continue;
            cnt = REG_V8_BGxCNT((uint8_t)bg);
            sb_addr = 0x06000000u + (uintptr_t)((cnt >> 8) & 0x1Fu) * 0x800u;
            sz = ((unsigned)cnt >> 14) & 3u;
            sb_end = sb_addr
                   + ((sz == 0u) ? 0x800u : (sz == 3u) ? 0x2000u : 0x1000u);
            v8_reserve_mem(bm, sb_addr, sb_end, cb_base, hi);
        }

        /* win 自身 tilemap 内存同样保留（BG 未启用时上面的循环覆盖不到它；
         * 模板 [0x10] 与 screenBase 同址、0x800 对齐，按标准 2KB 保留） */
        {
            uintptr_t tm_addr = (uintptr_t)win_u32(tpl, TPL_TILEMAP);
            if (tm_addr)
                v8_reserve_mem(bm, tm_addr, tm_addr + 0x800u, cb_base, hi);
        }
    }
}

/* ============================================================================
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
    lo = 0x100u;                  /* 起点避开官方 atlas 主体；越界部分由 VRAM 校验兜底 */
    if (lo >= hi || (unsigned)(hi - lo) < n)
        return 0u;

    v8q_init_once();
    if (v8q_is_switch(win)) {     /* 未走 begin 就分配：先换主并置首 */
        v8q_own(win);
        *(volatile uint16_t *)ADDR_V8_CURSOR = 0u;
    }

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

/* 当前分配游标（= 队列队尾，调试/埋点用）。 */
uint16_t v8_queue_cursor(void)
{
    return *(volatile uint16_t *)ADDR_V8_CURSOR;
}

/* ---- 12px 按行相位（与分配游标同生命周期）---- */
uint16_t v8_phase_get(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    /* 行键必须含 tileY：官方 FE 有时先推 CURSOR_TILE_Y，CURSOR_Y 稍后才变；
     * 只 xor curY 会漏检换行 → 奇数字行末相位 4 延续到下行首字。 */
    uint16_t row = tpl
        ? (uint16_t)((uintptr_t)tpl
                     ^ ((uint16_t)win_u8(win, WIN_CURSOR_Y) << 8)
                     ^ (uint16_t)win_u8(win, WIN_CURSOR_TILE_Y))
        : 0u;

    /* 行标识失配（换行/换窗口）→ 相位与 last_tile 归零 */
    if (*(volatile uint16_t *)ADDR_V8_PHASE_ROW != row) {
        *(volatile uint16_t *)ADDR_V8_PHASE_ROW = row;
        *(volatile uint16_t *)ADDR_V8_PHASE = 0u;
        *(volatile uint16_t *)ADDR_V8_LAST_TILE = 0u;
    }
    return *(volatile uint16_t *)ADDR_V8_PHASE;
}

void v8_phase_advance(uint16_t adv)
{
    *(volatile uint16_t *)ADDR_V8_PHASE =
        (uint16_t)(*(volatile uint16_t *)ADDR_V8_PHASE + adv);
}

uint16_t v8_phase_last_tile(void)
{
    return *(volatile uint16_t *)ADDR_V8_LAST_TILE;
}

void v8_phase_set_last_tile(uint16_t tile)
{
    *(volatile uint16_t *)ADDR_V8_LAST_TILE = tile;
}
