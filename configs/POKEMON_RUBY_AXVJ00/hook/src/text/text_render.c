/* =====================================================================================
 * text_render.c — 汉字直绘层（2026-11-10 重写版）
 * -------------------------------------------------------------------------------------
 * 设计只有一条：**完全沿用官方引擎的坐标系**，自己只做「把 12px 字按掩码切开写进
 * 两列 tile」这一件官方做不到的事。凡是能从窗口结构读出来的量，一律现场读，不留状态。
 *
 * 一、tile 号（官方坐标系，纯函数）
 *     文本行 row = (CURSOR_Y + CURSOR_TILE_Y) >> 1        // 换行固定 CTY += 2
 *     列     col =  CURSOR_X + CURSOR_TILE_X              // 进 1 列 = 8px
 *     tile  = TILE_BASE + (row & 7) * 64 + col * 2 + {0 上半, 1 下半}
 *
 *   容量闭合的根据（实测 + 反汇编）：
 *     · 窗口模板 +0x0C 的 tileData 是 0x06008000，下一个窗口是 0x0600C000
 *       —— 每个窗口独占 0x4000 字节 = 512 个 tile。
 *     · 一条 tilemap 行最多 32 列，每列 2 个 tile（上/下）= 64 tile。
 *     · 512 / 64 = 8 个文本行，正好是普通文本窗口的行数上限。
 *   所以 `(row & 7) * 64 + col * 2` 不会越界，也不需要扩容 charBase。
 *
 * 二、像素（官方掩码语义，等价于美版 sGlyphMasks + DrawGlyphTiles）
 *     一个字占 [rx, rx + advance) 共 advance 像素，落在若干列上：
 *       本列起点 sp = (rx + gx) & 7，源起点 sx = gx & 7，长度 w 取三者最小
 *     只写 [sp, sp + w)，区间对相邻两字严格互补：
 *       rx=0 时  字A: col[0,8) + col+1[0,4)   字B 从 col+1[4,8) 起
 *       rx=4 时  字A: col[4,8) + col+1[0,8)   字B 从 col+2 起
 *     因此结构上不可能产生残影，**不需要任何「整行清零」的事后补丁**。
 *     字模值域 {0, 14, 其它} → {背景色, 阴影色, 前景色}，与官方
 *     CopyGlyph1bppTo4bpp(upper, dst, colorD, colorC) 的语义一致（0 像素写背景色，
 *     不是留透明 —— 写 0 会让底色非 0 的窗口整片偏色）。
 *
 * 三、唯一的状态：行内相位 rx ∈ {0, 4}（advance 12 的余数）
 *     长度是窗口列表，每次绘制现场比对：**行号变了、或有人动过列游标**，
 *     相位就归零。这样既不需要「行首清零」，也不会被重印/滚动带偏。
 *
 * 历史教训（都在这份重写里被结构性消除）：
 *   · blit_run 没把 sx 当源偏移 → 相位 4 时右半个字取错，字看着「断成两半」
 *   · 每次 CTX==0 就清整行 64 tile → 同一行第二段（×N）把第一段（物品名）擦掉
 *   · 用 arena 累加器记 tile 起点 → 两个窗口共用批 tile、几轮后回绕撞字
 *   · 相位表放 0x0203FF88 → 被游戏周期性清零，行内 4px 随机错位
 * ===================================================================================== */
#include "text_render.h"
#include "text_scene.h"

/* 文本行在 tile 池里的排布：一行 62 tile（31 列 × 上/下），8 行 = 496，
 * 尾部 496..511 留给固定图标（▶ 菜单光标 0x1F0/0x1F1）。
 * ★ 不能占满 512：光标 tile 是硬编码进 tilemap 的绝对号，占满就会和文本撞。
 *   背包第 7 行「小」的下半截曾被 0x1E0 的 ▶ 覆盖 —— 就是这条。 */
#define CHS_ROW_TILES   62u
#define CHS_ROWS         8u

/* 字形索引的位域：低 15 位是序号，bit15 表示取右半（同一个字的第二片） */
#define CHS_GLYPH_HALF_BIT  0x8000u
#define CHS_GLYPH_IDX_MASK  0x7FFFu

/* 相位表：8 个槽 × 8B。必须落 RAM（game.ld 只有 ROM 段，全局会被链接进 ROM，
 * 写入被硬件丢弃）。0x0203E000 实测在所有帧恒零，且不与游戏堆冲突。 */
#define CHS_STATE_ADDR  0x0203E000u

struct ChsRowState {
    uint32_t win;   /* 窗口指针 */
    uint8_t  row;   /* 文本行 (CURSOR_Y + CURSOR_TILE_Y) >> 1 */
    uint8_t  rx;    /* 行内像素相位 0..7 */
    uint8_t  ctx;   /* 上次绘制后留下的 CURSOR_TILE_X */
    uint8_t  used;
};

static struct ChsRowState *st_tab(void)
{
    return (struct ChsRowState *)(uintptr_t)CHS_STATE_ADDR;
}

/* 取本窗口的状态槽。按窗口指针定位；满了就按指针散列挑一个固定槽，
 * 让两个窗口不会共用同一个槽（共用会让相位互相污染）。 */
static struct ChsRowState *st_slot(TextPrinter *win)
{
    struct ChsRowState *tab = st_tab();
    unsigned i;
    unsigned free_slot = CHS_ROWS;

    for (i = 0; i < CHS_ROWS; i++) {
        if (tab[i].used && tab[i].win == (uint32_t)(uintptr_t)win)
            return &tab[i];
        if (!tab[i].used && free_slot == CHS_ROWS)
            free_slot = i;
    }
    if (free_slot == CHS_ROWS)
        free_slot = (unsigned)(((uintptr_t)win >> 4) & (CHS_ROWS - 1u));
    tab[free_slot].win = (uint32_t)(uintptr_t)win;
    tab[free_slot].row = 0xFFu;         /* 强制下一次绘制归零相位 */
    tab[free_slot].rx = 0u;
    tab[free_slot].ctx = 0xFFu;
    tab[free_slot].used = 1u;
    return &tab[free_slot];
}

/* ---- 临时探针：按 textMode 统计绘制次数（0x0203F800，实测恒零区） ---- */
#define CHS_PROBE 0
#define CHS_PROBE_ADDR 0x0203F800u

static void probe_hit(unsigned mode, unsigned font)
{
#if CHS_PROBE
    volatile uint8_t *p = (volatile uint8_t *)(uintptr_t)CHS_PROBE_ADDR;

    p[mode & 7u] = (uint8_t)(p[mode & 7u] + 1u);
    p[8] = (uint8_t)font;
#else
    (void)mode; (void)font;
#endif
}

/* tm2：把正在打印的文本流前 16 字节抓出来（判断字节编码对不对） */
static void probe_text(TextPrinter *win)
{
#if CHS_PROBE
    volatile uint8_t *p = (volatile uint8_t *)(uintptr_t)CHS_PROBE_ADDR;
    uint32_t tp;
    uint16_t ti;
    unsigned i;

    if (p[0x20] != 0u)
        return;
    /* 只抓「战斗名字」：tm2 + font4（8px 小字） */
    if ((win_u8(win, WIN_TEXTMODE) & 7u) != 2u
        || win_u8(win, WIN_FONTNUM_REAL) != 4u)
        return;
    tp = win_u32(win, WIN_TEXT_PTR);
    ti = win_u16(win, WIN_TEXT_INDEX);
    if (!((tp >= 0x08000000u && tp < 0x0A000000u)
          || (tp >= 0x02000000u && tp < 0x02040000u)))
        return;
    for (i = 0; i < 16u; i++)
        p[0x20 + i] = *(volatile uint8_t *)(uintptr_t)(tp + ti + i);
    p[0x30] = (uint8_t)((tp >> 24) & 0xFFu);
    p[0x31] = (uint8_t)((tp >> 16) & 0xFFu);
    p[0x32] = (uint8_t)((tp >> 8) & 0xFFu);
    p[0x33] = (uint8_t)(tp & 0xFFu);
    p[0x34] = (uint8_t)(ti & 0xFFu);
    p[0x35] = (uint8_t)((ti >> 8) & 0xFFu);
    p[0x20] = 0xFFu;              /* 标记已抓 */
#endif
}

/* tm2 缓冲路径的目标指针探针：dst 是否为空、以及它的高 16 位 */
static void probe_buf(uint32_t dst, unsigned adv, unsigned cx, unsigned cy)
{
#if CHS_PROBE
    volatile uint8_t *p = (volatile uint8_t *)(uintptr_t)CHS_PROBE_ADDR;

    if (dst == 0u) {
        p[9] = (uint8_t)(p[9] + 1u);
        return;
    }
    if (p[10] == 0u && p[11] == 0u) {
        p[10] = (uint8_t)((dst >> 16) & 0xFFu);
        p[11] = (uint8_t)((dst >> 8) & 0xFFu);
        p[12] = (uint8_t)(dst & 0xFFu);
        p[13] = (uint8_t)adv;
        p[14] = (uint8_t)cx;
        p[15] = (uint8_t)cy;
    }
#else
    (void)dst; (void)adv; (void)cx; (void)cy;
#endif
}

/* =====================================================================================
 * 像素写入原语
 * ===================================================================================== */

/* 取 src 里第 s 列一行的调色板值（4bpp，低半字节是左像素）。 */
static uint8_t glyph_px(const uint8_t *src, unsigned y, unsigned s)
{
    return (uint8_t)((src[y * 4u + (s >> 1)] >> ((s & 1u) * 4u)) & 0xFu);
}

/* 把 src 的 [sx, sx+w) 写到 dst 的 [sp, sp+w)，其余像素不动。
 * ★ sx 必须真的作为源偏移 —— 旧版只拿它做长度钳制，相位 4 时右半个字取错。 */
static void blit_run(
    uint8_t *dst, const uint8_t *src, unsigned sx, unsigned sp, unsigned w,
    uint8_t fg, uint8_t bg, uint8_t sh)
{
    unsigned y, i;

    if (!dst || !src || w == 0u || w > 8u || sx + w > 8u || sp + w > 8u)
        return;

    for (y = 0; y < 8u; y++) {
        uint32_t *dp = (uint32_t *)(void *)(dst + y * 4u);
        uint32_t d = *dp;
        uint32_t px = 0;

        for (i = 0; i < w; i++) {
            uint8_t v = glyph_px(src, y, sx + i);
            uint8_t col = (v == 0u) ? bg : ((v == 14u) ? sh : fg);

            px |= (uint32_t)col << (((sp + i) & 7u) * 4u);
        }
        d &= ~(((w >= 8u) ? 0xFFFFFFFFu : ((1u << (w * 4u)) - 1u)) << (sp * 4u));
        *dp = d | px;
    }
}

/* 把 dst 的 [from, to) 填成纯色（用于补齐本字最后一列右侧的遗留像素）。 */
static void fill_run(uint8_t *dst, unsigned from, unsigned to, uint8_t col)
{
    unsigned y, i;

    if (!dst || from >= to || to > 8u)
        return;

    for (y = 0; y < 8u; y++) {
        uint32_t *dp = (uint32_t *)(void *)(dst + y * 4u);
        uint32_t d = *dp;

        for (i = from; i < to; i++) {
            d &= ~(0xFu << (i * 4u));
            d |= (uint32_t)col << (i * 4u);
        }
        *dp = d;
    }
}

/* =====================================================================================
 * 窗口 / 地址
 * ===================================================================================== */

uint8_t *vram_tile(TextPrinter *win, uint16_t tile)
{
    uint8_t *tpl = win_template(win);
    uint8_t *base;

    if (!tpl)
        return 0;
    /* 模板 +0x0C 就是 VRAM 地址（实测 0x06008000 / 0x0600C000），不是偏移量。 */
    base = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!base)
        return 0;
    return base + ((uint32_t)tile << 5);
}

void copy_tile32(void *dst, const void *src)
{
    const uint32_t *s = (const uint32_t *)src;
    uint32_t *d = (uint32_t *)dst;

    d[0] = s[0]; d[1] = s[1]; d[2] = s[2]; d[3] = s[3];
    d[4] = s[4]; d[5] = s[5]; d[6] = s[6]; d[7] = s[7];
}

/* 三色直取窗口字段：C=前景 D=背景 E=阴影（与官方 ApplyColors 的入参同序）。 */
static void chs_colors(TextPrinter *win, uint8_t *fg, uint8_t *bg, uint8_t *sh)
{
    *fg = win_u8(win, WIN_COLOR_C);
    *bg = win_u8(win, WIN_COLOR_D);
    *sh = win_u8(win, WIN_COLOR_E);
}

/* =====================================================================================
 * 绘制
 * ===================================================================================== */

/* 写 tilemap 表项。索引与官方 GetCursorTilemapPointer 同式：
 *   idx = (CURSOR_Y + CURSOR_TILE_Y + rowtile) * 32 + (CURSOR_X + CURSOR_TILE_X + col) */
static void put_entry(TextPrinter *win, unsigned col, unsigned rowtile, uint16_t tile)
{
    uint8_t *tpl = win_template(win);
    uint16_t *tm;

    if (!tpl)
        return;
    tm = (uint16_t *)(uintptr_t)win_u32(tpl, TPL_TILEMAP);
    if (!tm)
        return;
    tm[((unsigned)win_u8(win, WIN_CURSOR_Y)
        + (unsigned)win_u8(win, WIN_CURSOR_TILE_Y) + rowtile) * 32u
       + (unsigned)win_u8(win, WIN_CURSOR_X)
       + (unsigned)win_u8(win, WIN_CURSOR_TILE_X) + col]
        = (uint16_t)(tile | ((uint16_t)win_u8(win, WIN_PALETTE) << 12));
}

/* textMode 0/1/3：写 tilemap + tile 数据 */
static void draw_glyph_tilemap(
    TextPrinter *win, const struct ChsGlyphTiles *t, unsigned advance)
{
    struct ChsRowState *st = st_slot(win);
    unsigned row = ((unsigned)win_u8(win, WIN_CURSOR_Y)
                    + (unsigned)win_u8(win, WIN_CURSOR_TILE_Y)) >> 1;
    unsigned col = (unsigned)win_u8(win, WIN_CURSOR_X)
                 + (unsigned)win_u8(win, WIN_CURSOR_TILE_X);
    unsigned ctx = (unsigned)win_u8(win, WIN_CURSOR_TILE_X);
    uint16_t base = (uint16_t)(win_u16(win, WIN_TILE_BASE)
                               + (uint16_t)((row & (CHS_ROWS - 1u)) * CHS_ROW_TILES));
    unsigned rx, gx;
    uint8_t fg, bg, sh;

    /* 相位：行号变了或列游标被外力移动过 → 归零 */
    if (st->row != (uint8_t)row || st->ctx != (uint8_t)ctx)
        st->rx = 0u;
    st->row = (uint8_t)row;
    st->ctx = (uint8_t)ctx;
    rx = (unsigned)st->rx;

    chs_colors(win, &fg, &bg, &sh);

    gx = 0;
    while (gx < advance) {
        unsigned off = rx + gx;
        unsigned sp = off & 7u;
        unsigned c = off >> 3u;
        unsigned sx = gx & 7u;
        unsigned w = 8u - sp;
        uint16_t tu = (uint16_t)(base + (uint16_t)((col + c) * 2u));
        const uint8_t *sup = (gx < 8u) ? t->tl : t->tr;
        const uint8_t *slo = (gx < 8u) ? t->bl : t->br;

        if (w > 8u - sx)
            w = 8u - sx;
        if (w > advance - gx)
            w = advance - gx;

        blit_run(vram_tile(win, tu),       sup, sx, sp, w, fg, bg, sh);
        blit_run(vram_tile(win, (uint16_t)(tu + 1u)), slo, sx, sp, w, fg, bg, sh);
        put_entry(win, c, 0u, tu);
        put_entry(win, c, 1u, (uint16_t)(tu + 1u));

        gx += w;
    }

    /* 本字最后一列右侧若还空着（advance 不是 8 的整数倍），补背景色。
     * 那一段不属于本字，也不属于下一个字（下一个字从列边界重新起算），
     * 不清就会露出池子里的旧内容 —— 这是唯一需要补的地方。 */
    {
        unsigned end = rx + advance;
        unsigned rem = end & 7u;

        if (rem != 0u) {
            unsigned last = (end - 1u) >> 3u;
            uint16_t tu = (uint16_t)(base + (uint16_t)((col + last) * 2u));

            fill_run(vram_tile(win, tu), rem, 8u, bg);
            fill_run(vram_tile(win, (uint16_t)(tu + 1u)), rem, 8u, bg);
        }
    }

    st->rx = (uint8_t)((rx + advance) & 7u);
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(ctx + ((rx + advance) >> 3u)));
    st->ctx = win_u8(win, WIN_CURSOR_TILE_X);
}

/* textMode 2：战斗/血条用的线性缓冲（win[0x20] 递增，不碰 tilemap） */
static void draw_glyph_buffer(
    TextPrinter *win, const struct ChsGlyphTiles *t, unsigned advance)
{
    uint8_t *dst = (uint8_t *)(uintptr_t)win_u32(win, WIN_TILE_DATA);
    unsigned gx = 0;
    uint8_t fg, bg, sh;

    probe_text(win);
    probe_buf(win_u32(win, WIN_TILE_DATA), advance,
              win_u8(win, WIN_CURSOR_X), win_u8(win, WIN_CURSOR_Y));
    if (!dst)
        return;
    chs_colors(win, &fg, &bg, &sh);

    while (gx < advance) {
        unsigned sx = gx & 7u;
        unsigned w = 8u - sx;
        const uint8_t *sup = (gx < 8u) ? t->tl : t->tr;
        const uint8_t *slo = (gx < 8u) ? t->bl : t->br;

        if (w > advance - gx)
            w = advance - gx;

        blit_run(dst,          sup, sx, 0u, w, fg, bg, sh);
        blit_run(dst + 0x20u,  slo, sx, 0u, w, fg, bg, sh);

        dst += 0x40u;
        gx += w;
    }
    /* 只有 advance 不是 8 的整数倍时才补余量。
     * ★ 曾无条件调用：advance==8 时 from=0，等于把刚画好的整块 tile 填成背景色
     *   —— 战斗名字框整段变空白/残影就是这么来的。 */
    if ((advance & 7u) != 0u)
        fill_run(dst - 0x40u, advance & 7u, 8u, bg);
    win_set_u32(win, WIN_TILE_DATA, (uint32_t)(uintptr_t)dst);
}

void DrawGlyphTiles(
    TextPrinter *win, const struct ChsGlyphTiles *t, unsigned advance)
{
    if (!win || !t || !t->tl || !t->bl || !t->tr || !t->br)
        return;
    if (advance == 0u || advance > 16u)
        advance = CHS_GLYPH_ADVANCE_PX;

    probe_hit((unsigned)(win_u8(win, WIN_TEXTMODE) & 7u),
              (unsigned)win_u8(win, WIN_FONTNUM_REAL));

    if ((win_u8(win, WIN_TEXTMODE) & 7u) == 2u) {
        draw_glyph_buffer(win, t, advance);
        return;
    }
    draw_glyph_tilemap(win, t, advance);
}

/* 行首对齐 ▼ / 光标：把行内相位推到下一个列边界。
 * 官方游标只认整列，留半列相位时后面的图标会压在前一个字上。 */
void arrow_inplace12(TextPrinter *win)
{
    struct ChsRowState *st;

    if (!win)
        return;
    st = st_slot(win);
    if (st->rx == 0u)
        return;
    st->rx = 0u;
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
    st->ctx = win_u8(win, WIN_CURSOR_TILE_X);
}

void ChsBlitTileDirect(TextPrinter *win, const uint8_t *src32, uint16_t tile)
{
    uint8_t fg, bg, sh;

    if (!win || !src32)
        return;
    chs_colors(win, &fg, &bg, &sh);
    blit_run(vram_tile(win, tile), src32, 0u, 0u, 8u, fg, bg, sh);
}

/* =====================================================================================
 * 字形取址
 * ===================================================================================== */

static uint8_t chs_ink_w(uint8_t fontId)
{
    if (fontId == 4u)
        return CHS_INK_SMALL_W;
    if (fontId == 5u)
        return CHS_INK_MIDDLE_W;
    return CHS_INK_NORMAL_W;
}

static uint8_t chs_ink_h(uint8_t fontId)
{
    if (fontId == 4u)
        return CHS_INK_SMALL_H;
    if (fontId == 5u)
        return CHS_INK_MIDDLE_H;
    return CHS_INK_NORMAL_H;
}

static uint8_t chs_pad_top(uint8_t fontId)
{
    if (fontId == 4u)
        return CHS_INK_SMALL_TOP;
    if (fontId == 5u)
        return CHS_INK_MIDDLE_TOP;
    return CHS_INK_NORMAL_TOP;
}

void ChsGlyphMetrics(uint8_t fontId, struct ChsGlyphTiles *t)
{
    if (!t)
        return;
    t->ink_w = chs_ink_w(fontId);
    t->ink_h = chs_ink_h(fontId);
    t->pad_top = chs_pad_top(fontId);
}

/* 128B 字形槽布局：[TL 32B][BL 32B][TR 32B][BR 32B]，4bpp 低半字节是左像素。 */
void DecompressGlyph_Chinese(struct TextGlyph *glyph, uint16_t ChineseChar, uint8_t fontId)
{
    const uint8_t *base;
    const uint8_t *g;

    if (!glyph)
        return;
    if (ChineseChar >= CHS_FONT_GLYPH_MAX)
        ChineseChar = 0;

    if (fontId == 4u)
        base = (const uint8_t *)ADDR_FONT_CHS_SMALL;
    else if (fontId == 5u)
        base = (const uint8_t *)ADDR_FONT_CHS_MIDDLE;
    else
        base = (const uint8_t *)ADDR_FONT_CHS_NORMAL;

    g = base + ((uint32_t)(ChineseChar & CHS_GLYPH_IDX_MASK) << 7);
    if (ChineseChar & CHS_GLYPH_HALF_BIT)
        g += 64u;

    copy_tile32(&glyph->gfxBufferTop[0],    g + 0u);
    copy_tile32(&glyph->gfxBufferTop[8],    g + 64u);
    copy_tile32(&glyph->gfxBufferBottom[0], g + 32u);
    copy_tile32(&glyph->gfxBufferBottom[8], g + 96u);

    glyph->width = GetChineseFontWidthFunc(ChineseChar, fontId);
    glyph->height = chs_ink_h(fontId);
}

uint8_t GetChineseFontWidthFunc(uint16_t ChineseChar, uint8_t fontId)
{
    (void)ChineseChar;
    /* 步进只由 fontNum 决定：常规 12px，小字 8px。绘制侧按 advance 自动分段，
     * 改这里就等于改全局字号。 */
    if (fontId == 4u)
        return CHS_GLYPH_ADVANCE_SMALL;
    return CHS_GLYPH_ADVANCE_PX;
}

/* =====================================================================================
 * 场景门控占位（保持接口；当前一律不生效）
 * ===================================================================================== */

uint8_t chs_pitch_write_op(TextPrinter *win)
{
    (void)win;
    return 0u;
}

void chs_pitch_set_write_op(TextPrinter *win, uint8_t op)
{
    (void)win;
    (void)op;
}
