/* ============================================================================
 * tile_alloc.c — v8 动态 tile 分配器（活引用 + VRAM 非空 + ours 段表，零静态表）
 *
 * 2026-09-07 定稿：废弃 kV8AvoidScenes 静态避让带（14 签名/37 段手工表）与
 * 线性落址表（kV8LinearScenes，实测同场景多窗口并发叠印 → 回归 BUG），
 * 全部改为运行时动态获取，任何场景自动适配：
 *
 *   ① 活引用层（权威，防砸屏上正在显示的字）：
 *      v8_alloc_begin 清零重建位图——扫 win 自身 tilemap + DISPCNT 所有启用 BG
 *      中同 charBase 的 screenblock（BGxCNT.size 位定扫描范围，affine/位图 BG 跳过）。
 *      清零重建（非增量）防「旧条目消失后位图泄漏」。
 *   ② VRAM 非空层（补活引用扫不到的官方占用）：
 *      alloc 时对候选 tile 实时校验 32B 全空。覆盖：atlas 字库区（各场景上界
 *      0x208~0x2D1 差异自动适配）、begin 之后才绘制的官方 UI（关闭按钮/状态
 *      图标/窗框）、LZ 解压到硬编码地址的图形——静态带想手工解决但解决不完
 *      的全部场景，动态版一律自动避开。
 *   ③ ours 段表（回收我们自己写过的残留 glyph）：
 *      非空 tile 仅当记录在 ours 段表（EWRAM 0x0203FF80，19 段 + magic 防冷
 *      启动残留）才允许重写；官方数据/atlas 永不在表内 → 永不回收。
 *
 * 确定性不变：固定起点顺序遍历，同输入 → 同输出。
 * OBJ 隔离不变：hi = (4-char_base)*512 clamp 1024。
 * ==========================================================================*/
#include "tile_alloc.h"

/* 占用位图：128 字节 = 1024 bit = tile 相对号 0~1023。 */
#define V8_BITMAP_WORDS  128u   /* 1024 bit / 8 */

/* ours 段表容量：80B = magic(2B) + pad(2B) + 19 段 × 4B */
#define V8_OURS_SEG_N    19u
#define V8_OURS_MAGIC    0xA5C3u

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

/* 单 tile 可用性：位图未标（无活引用）且（VRAM 全空 或 属 ours 可回收）。 */
static int v8_tile_usable(volatile uint8_t *bm, const void *vram, uint16_t t)
{
    const volatile uint32_t *p;
    if (v8_bit_get(bm, t))
        return 0;
    p = (const volatile uint32_t *)((const volatile uint8_t *)vram
                                    + (unsigned)t * 32u);
    if (p[0] | p[1] | p[2] | p[3] | p[4] | p[5] | p[6] | p[7])
        return v8_in_ours(t);
    return 1;
}

/* ============================================================================
 * v8_alloc_begin：打印会话边界——复位游标/相位 + 权威重建活引用位图。
 * ① win 自身 tilemap（防御 tilemap 不在 screenblock 的缓冲直绘变体）；
 * ② DISPCNT 启用的每个 text BG：BGxCNT.charBase == 本窗 charBase 时，
 *    按其 size 位扫整个 screenblock（32×32/64×32/32×64/64×64 表项）。
 *    affine（mode1/2 的 BG2、mode2 的 BG3）与位图模式 BG 的表项语义不同，跳过。
 * ==========================================================================*/
void v8_alloc_begin(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    volatile uint8_t *bm = v8_bitmap();
    uint8_t cb;
    unsigned bg, i;

    *(volatile uint16_t *)ADDR_V8_CURSOR = 0u;
    *(volatile uint16_t *)ADDR_V8_PHASE = 0u;
    *(volatile uint16_t *)ADDR_V8_PHASE_ROW = 0u;
    *(volatile uint16_t *)ADDR_V8_LAST_TILE = 0u;
    *(volatile uint16_t *)ADDR_V8_NL_MARK = 0xFFFFu; /* 无上次坐标 */

    if (!tpl)
        return;
    cb = tpl[TPL_CHARBASE];
    v8_ours_init_once();
    v8_bit_clear_all(bm);

    /* ① win 自身 tilemap */
    {
        const uint16_t *tilemap = (const uint16_t *)(uintptr_t)win_u32(tpl, TPL_TILEMAP);
        if (tilemap) {
            for (i = 0; i < 1024u; i++) {
                uint16_t t = tilemap[i] & 0x3FFu;
                if (t != 0u)
                    v8_bit_set(bm, t);
            }
        }
    }

    /* ② 全 BG 同 charBase 的 screenblock 活引用 */
    {
        uint16_t dis = REG_V8_DISPCNT;
        uint8_t mode = (uint8_t)(dis & 7u);
        for (bg = 0; bg < 4u; bg++) {
            uint16_t cnt;
            const uint16_t *sb;
            unsigned size, n;

            if (!(dis & (uint16_t)(0x100u << bg)))
                continue;
            /* mode≠0 时 BG2/BG3 可能是 affine 或位图层：表项不是 10bit tile 号 */
            if (bg >= 2u && mode != 0u)
                continue;
            cnt = REG_V8_BGxCNT(bg);
            if (((cnt >> 2) & 3u) != cb)
                continue;
            sb = (const uint16_t *)(uintptr_t)
                 (0x06000000u + (unsigned)((cnt >> 8) & 0x1Fu) * 0x800u);
            size = (unsigned)(cnt >> 14) & 3u;
            n = (size == 0u) ? 1024u : (size == 3u) ? 4096u : 2048u;
            for (i = 0; i < n; i++) {
                uint16_t t = sb[i] & 0x3FFu;
                if (t != 0u)
                    v8_bit_set(bm, t);
            }
        }
    }
}

/* ============================================================================
 * v8_alloc_tile：领连续 glyph_len 个 tile。
 * 确定性顺序遍历 [lo, hi)，逐候选过 v8_tile_usable（位图 + VRAM 非空 + ours）；
 * 无空闲回卷重扫，再无 → 返回 0（调用方放弃，宁缺不砸 UI）。
 * 分配后推进游标并记入 ours 段表（相邻自动合并）。
 * ==========================================================================*/
uint16_t v8_alloc_tile(TextPrinter *win, uint8_t font_px, uint8_t glyph_len)
{
    uint8_t *tpl = win_template(win);
    uint8_t char_base;
    volatile uint8_t *bm = v8_bitmap();
    const void *vram;
    uint16_t hi, lo, t;
    uint16_t start;
    unsigned i;

    (void)font_px;   /* 字号当前只影响 glyph_len（调用方已折算），保留形参备将来 GAP 配置 */

    if (!tpl || glyph_len == 0u)
        return 0u;
    char_base = tpl[TPL_CHARBASE];
    vram = (const void *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!vram)
        return 0u;
    hi = v8_alloc_hi(char_base);
    lo = 0x100u;                  /* 起点避开官方 atlas 主体；越界部分由 VRAM 校验兜底 */
    if (lo >= hi || (unsigned)(hi - lo) < glyph_len)
        return 0u;

    start = *(volatile uint16_t *)ADDR_V8_CURSOR;
    if (start < lo || start >= hi)
        start = lo;

    /* 第一遍：从上次游标起 */
    for (t = start; (unsigned)t + glyph_len <= (unsigned)hi; t++) {
        int ok = 1;
        for (i = 0; i < glyph_len; i++)
            if (!v8_tile_usable(bm, vram, (uint16_t)(t + i))) { ok = 0; break; }
        if (ok) {
            *(volatile uint16_t *)ADDR_V8_CURSOR = (uint16_t)(t + glyph_len);
            v8_ours_add(t, glyph_len);
            return t;
        }
    }
    /* 第二遍：回卷到 lo 重扫 */
    for (t = lo; (unsigned)t + glyph_len <= (unsigned)hi; t++) {
        int ok = 1;
        for (i = 0; i < glyph_len; i++)
            if (!v8_tile_usable(bm, vram, (uint16_t)(t + i))) { ok = 0; break; }
        if (ok) {
            *(volatile uint16_t *)ADDR_V8_CURSOR = (uint16_t)(t + glyph_len);
            v8_ours_add(t, glyph_len);
            return t;
        }
    }
    return 0u;                    /* 彻底无空闲：放弃，宁缺不砸 UI */
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

void v8_phase_before_glyph(TextPrinter *win)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
    uint8_t tx = win_u8(win, WIN_CURSOR_TILE_X);
    uint8_t ty = win_u8(win, WIN_CURSOR_TILE_Y);
    uint16_t prev = *(volatile uint16_t *)ADDR_V8_NL_MARK;

    if (prev == 0xFFFFu)
        return;

    {
        uint8_t prev_tx = (uint8_t)(prev & 0xFFu);
        uint8_t prev_ty = (uint8_t)(prev >> 8);

        /* TY 变 或 同行 TX 回落 = 官方已换行（FE/FB 尾调用后的下一字） */
        if (ty != prev_ty || tx < prev_tx) {
            *(volatile uint16_t *)ADDR_V8_PHASE = 0u;
            *(volatile uint16_t *)ADDR_V8_LAST_TILE = 0u;
            *(volatile uint16_t *)ADDR_V8_PHASE_ROW = 0xFFFFu;
            /* tm0/1 恒 TILE_OFFSET+=2（文档铁律，奇数位行末必做） */
            if (tm == 0u || tm == 1u)
                win_set_u16(win, WIN_TILE_OFFSET,
                            (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + 2u));
        }
    }
}

void v8_phase_after_glyph(TextPrinter *win)
{
    uint8_t tx = win_u8(win, WIN_CURSOR_TILE_X);
    uint8_t ty = win_u8(win, WIN_CURSOR_TILE_Y);

    *(volatile uint16_t *)ADDR_V8_NL_MARK =
        (uint16_t)(((uint16_t)ty << 8) | tx);
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
