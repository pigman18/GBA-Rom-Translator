/* ============================================================================
 * tile_alloc.c — v8 顺序 tile 分配器（运行时读 tilemap → 避让带 → 顺序绕开）
 *
 * 取代 v6 静态行带表 + v7 动态行基址表，回到用户最初认知的「顺序放入 + 避让带」。
 * 一个字的 tile 号只有一个来源：本顺序分配器。16px / 12px / 8px 统一走同一条路径，
 * 不再有「静态表命中走 A、未命中走 B」的分裂。
 *
 * 三步法（用户定义）：
 *   ① 屏蔽输出 —— 已在 PrintNextChar_Hook + ADDR_V6_BYPASS 开关完成；
 *   ② 读避让带 —— 本文件：扫 tilemap 活引用，收集官方已占 tile 号；
 *   ③ 顺序绕开 —— 本文件：确定性遍历空闲带，跳过占用，领连续 glyph_len 个 tile。
 *
 * 三条铁律（缺一不可）：
 *   ① 确定性：固定起点遍历跳过占用，同输入 → 同输出（防 v4 随机取址/重绘漂移坑）。
 *   ② 权威性：避让带来自 tilemap 活引用，不靠猜（漏一个就砸官方字）。
 *   ③ 隔离性：charBase 物理分块天然隔离 OBJ 精灵区，上界用 REG_DISPCNT 截断。
 *
 * 关键输入（AXVJ 实证）：
 *   tilemap 指针 = tpl[TPL_TILEMAP]=+0x10；charBase = tpl[TPL_CHARBASE]=+0x01
 *   （charBlock 号 0~3）；tilemap 表项 tile 号 = entry&0x3FF（低 10 bit，
 *   高 4 bit 是 palette）；OBJ 起始 charBlock = (REG_DISPCNT>>4)&3。
 *
 * 状态最小化 + 生命周期（用户反复强调「别来回切换出 BUG」）：
 *   - 占用位图（128B）、分配游标（2B）、12px 相位（px 2B + last_tile 2B）三者
 *     都在 v8_alloc_begin（InitTextPrinter 会话边界）重建/复位。
 *   - 相位不再是全局 8 槽 + 行指纹 key 的跨窗口状态表，而是会话内单调增量，
 *     窗口切换自然从头累计，不存在残留。
 * ==========================================================================*/
#include "tile_alloc.h"

/* 占用位图：128 字节 = 1024 bit = tile 相对号 0~1023。
 * bit 布局：位图[0] bit0 = tile 0，位图[0] bit7 = tile 7，位图[1] bit0 = tile 8 … */
#define V8_BITMAP_WORDS  128u   /* 1024 bit / 8 */

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

/* 读 GBA 寄存器（volatile 映射） */
static uint16_t v8_reg_dispcnt(void)
{
    return *(volatile uint16_t *)0x04000000u;
}

/* OBJ 起始 charBlock：DISPCNT bits[5:4]（DISPCNT_OBJ_CHAR_BASE_MASK=0x0030）。 */
static uint8_t v8_obj_charblock(void)
{
    return (uint8_t)((v8_reg_dispcnt() >> 4) & 3u);
}

/* 分配上界（charBase 相对号）：避免落入 OBJ 精灵 charBlock。
 * 若 OBJ charBlock > 当前 charBase，则相对号 t 落 OBJ 当且仅当 charBase+t/512 == obj_cb
 * ⇒ 上界 hi = (obj_cb - charBase)*512；否则 hi = 1024（4 个 charBlock 全覆盖）。 */
static uint16_t v8_alloc_hi(uint8_t char_base)
{
    uint8_t obj_cb = v8_obj_charblock();
    if (obj_cb > char_base)
        return (uint16_t)((unsigned)(obj_cb - char_base) * 512u);
    return 1024u;
}

/* ============================================================================
 * v8_alloc_begin：打印会话开始时快照占用位图 + 复位游标与相位。
 * 扫当前窗口 tilemap（BG screenBase 32×32 = 1024 表项）的活引用，每个非零
 * 表项的低 10 bit = 官方已占 tile 相对号，标位。
 * 之后本轮所有中文查这张快照——不看自己刚写入的表项 ⇒ 防自画污染。
 * 游标与相位同步复位（三者同生命周期）。
 * ==========================================================================*/
void v8_alloc_begin(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint16_t *tilemap;
    volatile uint8_t *bm = v8_bitmap();
    unsigned i;

    *(volatile uint16_t *)ADDR_V8_CURSOR = 0u;
    *(volatile uint16_t *)ADDR_V8_PHASE = 0u;
    *(volatile uint16_t *)ADDR_V8_PHASE_ROW = 0u;
    *(volatile uint16_t *)ADDR_V8_LAST_TILE = 0u;

    if (!tpl)
        return;
    tilemap = (uint16_t *)(uintptr_t)win_u32(tpl, TPL_TILEMAP);
    if (!tilemap)
        return;

    v8_bit_clear_all(bm);

    /* 扫整个 tilemap（32×32 = 1024 表项）。tilemap 表项存 charBase 相对号，
     * 高 4 bit 是 palette（官方 UpdateTilemap 写 palette=win[0x0F]<<12），
     * 故 & 0x3FF 取低 10 bit 的 tile 号。 */
    for (i = 0; i < 1024u; i++) {
        uint16_t t = tilemap[i] & 0x3FFu;
        if (t != 0u)
            v8_bit_set(bm, t);
    }
}

/* ============================================================================
 * v8_alloc_tile：领连续 glyph_len 个 tile。
 * 确定性：从游标起遍历 [lo, hi)，跳过占用位图，取首个连续 glyph_len 空闲。
 * 无空闲 → 回卷到 lo 重扫一次，再没有 → 返回 0（调用方放弃，宁缺不砸 UI）。
 * 分配后推进游标到 t + glyph_len（字间紧排，无额外 GAP——用户 2026-09-04 定稿）。
 * ==========================================================================*/
uint16_t v8_alloc_tile(TextPrinter *win, uint8_t font_px, uint8_t glyph_len)
{
    uint8_t *tpl = win_template(win);
    uint8_t char_base;
    volatile uint8_t *bm = v8_bitmap();
    uint16_t hi, lo, t;
    uint16_t start;
    unsigned i;

    (void)font_px;   /* 字号当前只影响 glyph_len（调用方已折算），保留形参备将来 GAP 配置 */

    if (!tpl || glyph_len == 0u)
        return 0u;
    char_base = tpl[TPL_CHARBASE];
    hi = v8_alloc_hi(char_base);
    lo = 0x100u;                  /* 空闲带起点：避开官方 atlas [0,0x100) */
    if (lo >= hi || (unsigned)(hi - lo) < glyph_len)
        return 0u;

    start = *(volatile uint16_t *)ADDR_V8_CURSOR;
    if (start < lo || start >= hi)
        start = lo;

    /* 第一遍：从上次游标起 */
    for (t = start; (unsigned)t + glyph_len <= (unsigned)hi; t++) {
        int ok = 1;
        for (i = 0; i < glyph_len; i++)
            if (v8_bit_get(bm, (uint16_t)(t + i))) { ok = 0; break; }
        if (ok) {
            *(volatile uint16_t *)ADDR_V8_CURSOR = (uint16_t)(t + glyph_len);
            return t;
        }
    }
    /* 第二遍：回卷到 lo 重扫 */
    for (t = lo; (unsigned)t + glyph_len <= (unsigned)hi; t++) {
        int ok = 1;
        for (i = 0; i < glyph_len; i++)
            if (v8_bit_get(bm, (uint16_t)(t + i))) { ok = 0; break; }
        if (ok) {
            *(volatile uint16_t *)ADDR_V8_CURSOR = (uint16_t)(t + glyph_len);
            return t;
        }
    }
    return 0u;                    /* 彻底无空闲：放弃，宁缺不砸 UI */
}

/* ---- 12px 按行相位（与分配游标同生命周期）---- */
uint16_t v8_phase_get(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint16_t row = tpl
        ? (uint16_t)((uintptr_t)tpl ^ ((uint16_t)win_u8(win, WIN_CURSOR_Y) << 8))
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
