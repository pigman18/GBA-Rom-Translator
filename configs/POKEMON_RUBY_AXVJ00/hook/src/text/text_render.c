/* =====================================================================================
 * text_render.c — v5 渲染件（混合写入架构步骤 2，docs/REWRITE_DESIGN_混合写入架构.md）
 *
 * 职责：PrintGlyph（F9 汉字）/ DrawGlyph（PCS 单字节）的渲染实现。
 *
 * mode0（线性滚动光栅，对话/战斗台词/详情页）—— 官方模型逐列复刻：
 *   官方 tm0 处理器@0x08003568：blit@tileData[(TILE_BASE+TILE_OFFSET)*32]
 *   （8px 列对 upper/lower）→ UpdateTilemap（写 tilemap 列 cursorX+cursorTileX，
 *   不推进游标）→ TILE_OFFSET+=2、cursorTileX+=1。
 *   v5 汉字 = 16px 整格（2 列 × 4 tile）：字库容器 [TL@0][BL@32][TR@64][BR@96]
 *   解压 → 官方 CopyGlyph2bppTo4bpp 颜色重映射（15→C/14→E/0→D）直写 VRAM →
 *   每列 UpdateTilemap_Origin + cursorTileX++ → 收尾 TILE_OFFSET+=4。
 *   官方游标语义零改动、零自研状态（无 pitch 槽/行键/last_off，v4 全废）。
 *
 * tm1/tm2/tm3：步骤 2 为「消费 + 推进」（像素路径步骤 3 逐窗收敛）：
 *   tm1/tm3：cursorTileX += cols（官方 tm1 每字 +1 的 16px 推广）；
 *   tm2：缓冲指针 win[0x20] += cols*0x40（官方每列 +0x40，血条 OBJ 刷走）。
 *
 * DrawGlyph（中文替换流里的 PCS 字节）：
 *   SYM 标点带（0x36-0x3E，编码即 JP PCS 同码）→ mode0 自绘一列 8px；
 *     非 mode0 尾调原生处理器（JP 半角形回退，视觉可接受）。
 *   ≥0xF7 不可印位直接消费（引擎零回落）；
 *   其余按 textMode 尾调原生处理器（FontFunc_NativeDispatch 直调 Origin
 *   地址，**严禁经 FontFuncTable**——表项已指向我方 thunk，经表分发会无限递归）。
 * ===================================================================================== */
#include "text.h"

#define CHS_GLYPH_HALF_BIT   0x8000u
#define CHS_GLYPH_IDX_MASK   0x7FFFu

/* 字形解压（v4 同款）：128B 容器原样拷出，保持
 * [TL@+0][BL@+32][TR@+64][BR@+96] 布局；bit15=半字右半（+64 起）。 */
static void decompress_chs_glyph(uint8_t out[CHS_CELL_BYTES],
                                 uint16_t gidx, uint8_t font_id)
{
    const uint8_t *base;
    const uint8_t *g;

    if (gidx >= CHS_FONT_GLYPH_MAX)
        gidx = 0;

    base = (font_id == 4u) ? (const uint8_t *)ADDR_FONT_CHS_SMALL
                           : (const uint8_t *)ADDR_FONT_CHS_NORMAL;
    g = base + ((uint32_t)(gidx & CHS_GLYPH_IDX_MASK) << 7);
    if (gidx & CHS_GLYPH_HALF_BIT)
        g += 64u;

    copy_tile32(out + 0x00, g + 0u);   /* TL */
    copy_tile32(out + 0x20, g + 32u);  /* BL */
    copy_tile32(out + 0x40, g + 64u);  /* TR */
    copy_tile32(out + 0x60, g + 96u);  /* BR */
}

/* mode0 单列绘制（官方 tm0 一列的逐语义复刻）：
 * src_u/src_l = 32B 4bpp 字库 tile（索引 15/14/0）；
 * 落点 tileData[(TILE_BASE+TILE_OFFSET)*32]，颜色重映射后直写 VRAM
 * （官方 FontFunc → CopyGlyph2bpp 链路本就直写 VRAM dst）；
 * UpdateTilemap 写表项列，cursorTileX/TILE_OFFSET 各推一格。 */
static void blit_column_mode0(TextPrinter *win,
                              const uint8_t *src_u, const uint8_t *src_l)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    uint8_t fg_ov = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    uint8_t color_c = fg_ov ? fg_ov : win_u8(win, WIN_COLOR_C);
    uint8_t color_d = win_u8(win, WIN_COLOR_D);
    uint8_t color_e = win_u8(win, WIN_COLOR_E);
    uint16_t base = win_u16(win, WIN_TILE_BASE);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    uint16_t t;
    uint8_t *dst_u;

    if (!tile_data)
        return;

    t = (uint16_t)(base + off);
    dst_u = tile_data + ((uint32_t)t << 5);

    CopyGlyph2bppTo4bpp_Origin(src_u, dst_u, color_c, color_e, color_d);
    CopyGlyph2bppTo4bpp_Origin(src_l, dst_u + 0x20, color_c, color_e, color_d);
    UpdateTilemap_Origin(win, t, (uint16_t)(t + 1u));
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
    win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
}

/* mode0 汉字整格：cols=2（16px 主字体）/ 1（font4 小字，8px 单列）。 */
static void print_glyph_mode0(TextPrinter *win, uint16_t gidx,
                              uint8_t font_id, unsigned cols)
{
    uint8_t buf[CHS_CELL_BYTES];
    unsigned col;

    decompress_chs_glyph(buf, gidx, font_id);

    for (col = 0; col < cols; col++) {
        const uint8_t *src_u = buf + (col ? 0x40u : 0x00u);
        const uint8_t *src_l = buf + (col ? 0x60u : 0x20u);

        blit_column_mode0(win, src_u, src_l);
    }
}

/* mode0 SYM 标点：64B 容器 [U@+0][L@+32]，一列 8px（同官方半角节奏）。 */
static void draw_sym_mode0(TextPrinter *win, uint32_t sym_idx)
{
    const uint8_t *sym =
        (const uint8_t *)ADDR_FONT_CHS_SYM + sym_idx * 64u;

    blit_column_mode0(win, sym, sym + 32u);
}

/* F9 汉字渲染入口（text_translater.c 消费）。
 * glyphWidth 形参仅为兼容既有签名——v5 步进由渲染模型决定：
 * 16px 整格（主字体 2 列）/ font4 小字 8px（1 列）。 */
void PrintGlyph(TextPrinter *win, uint32_t gidx, unsigned glyphWidth)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
    uint8_t fn = win_u8(win, WIN_FONTNUM_REAL);
    unsigned cols;

    (void)glyphWidth;

    if (fn > 6u)
        fn = 3u;
    if (tm == 2u)
        fn = 4u;         /* tm2 缓冲为原生 8px 槽（v4 实证） */

    cols = (fn == 4u) ? 1u : 2u;

    switch (tm) {
    case 0:
        print_glyph_mode0(win, (uint16_t)(gidx & 0xFFFFu), fn, cols);
        break;
    case 1:
    case 3:
        /* 步骤 2：消费 + 推进（像素路径步骤 3 逐窗收敛） */
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + cols));
        break;
    case 2: {
        uint32_t dst = win_u32(win, WIN_TILE_DATA);

        if (dst != 0u)
            win_set_u32(win, WIN_TILE_DATA, dst + cols * 0x40u);
        break;
    }
    default:
        break;
    }
}

/* PCS 单字节渲染入口（text_translater.c 中文替换流内消费）。
 * 返回 1=已消费（引擎零回落：不可印位直接吞掉）。 */
int DrawGlyph(TextPrinter *win, uint32_t cur_char)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;

    if (cur_char >= SYM_GLYPH_BASE
        && cur_char < SYM_GLYPH_BASE + SYM_GLYPH_COUNT) {
        if (tm == 0u) {
            draw_sym_mode0(win, cur_char - SYM_GLYPH_BASE);
            return 1;
        }
        /* 非 mode0：落入下方原生分发，按 JP PCS 同码画半角形
         * （SYM 编码即 JP PCS 标点码，回退视觉可接受）。 */
    }

    if (cur_char >= 0xF7u)
        return 1;

    FontFunc_NativeDispatch(tm, win, cur_char);
    return 1;
}
