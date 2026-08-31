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
 *   解压 → blend_glyph_4bpp 混合写入 VRAM（colors[16] 值→色号 LUT 直通，
 *   0→底色/14→阴影/15→前景；tile 无所有权、跨度外像素保留）→
 *   每列 UpdateTilemap_Origin + cursorTileX++ → 收尾 TILE_OFFSET+=4。
 *   官方游标语义零改动、零自研状态（无 pitch 槽/行键/last_off，v4 全废）。
 *
 * tm1/tm2/tm3（步骤 3 逐窗收敛，2026-08-31）：
 *   tm3：已实现像素路径——落点 2D 布局公式（反汇编 @0x08003500 实证）
 *     tile = (cursorX+cursorTileX)+2+TILE_BASE+(cursorY+cursorTileY)*30，
 *     复用 blit_column_at_tile（blend_glyph_4bpp），每列 [0x1B]+=1。
 *   tm1：暂消费 + 推进（cursorTileX += cols）——官方 tm1 只写 tilemap
 *     （预渲染 tile 号，字形已在 ROM 预渲染库），无动态 tileData 游标；
 *     中文像素路径需先定「动态 tile 号分配」方案。
 *   tm2：缓冲指针 win[0x20] += cols*0x40（官方每列 +0x40，血条 OBJ 刷走；
 *     8px 槽，中文 16px 塞不下，血条窗口本不该有中文）。
 *
 * DrawGlyph（中文替换流里的 PCS 字节）：
 *   SYM 标点带（0x36-0x3E，编码即 JP PCS 同码）→ mode0 自绘一列 8px；
 *     非 mode0 尾调原生处理器（JP 半角形回退，视觉可接受）。
 *   ≥0xF7 不可印位直接消费（引擎零回落）；
 *   其余按 textMode 尾调原生处理器（FontFunc_NativeDispatch 直调 Origin
 *   地址，**严禁经 FontFuncTable**——表项已指向我方 thunk，经表分发会无限递归）。
 * ===================================================================================== */
#include "text.h"
#include "blend_glyph.h"

#define CHS_GLYPH_HALF_BIT   0x8000u
#define CHS_GLYPH_IDX_MASK   0x7FFFu

/* 下半 tile 相对上半 tile 的偏移（**随 textMode 而变，不可统一**）：
 *   tm0 = 1  ——官方 tm0_core@0x08003520：upper=base+off, lower=upper+1。
 *   tm3 = 30 ——官方 tm3@0x080034A8：upper=X+Y*30, lower=X+(Y+1)*30。
 *     tm3 的 VRAM 网格行宽是 30（省空间），tilemap 行宽仍是 32（硬件），
 *     两者本就不同；误用 tm0 的 +1 会让下一列的上半覆盖本列的下半，
 *     并让 tilemap 下一行指到被覆盖的 tile ⇒ 文字上下错位（2026-08-31 实证）。 */
#define TM0_LOWER_DELTA      1u
#define TM3_LOWER_DELTA      30u

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

/* 按 tile 号写一列（upper@tile / lower@tile+lower_delta，8px 单列；tm0/tm3 共用）。
 * src_u/src_l = 32B 4bpp 字库 tile（索引 15=前景/14=阴影/0=底色）；
 * 经 blend_glyph_4bpp 混合写入（colors[16] 值→色号 LUT 直通，方案 A；
 * tile 无所有权、跨度外保留）；UpdateTilemap 写表项列，cursorTileX 推一格。
 * 16px 整格 startPixel=0/width=8 无溢出（spillTile=0），blend 退化为整 tile
 * 重写但与 CopyGlyph 覆盖等价；blend 统一原语为后续 12px 相位/溢出留路。
 * tile 号与物理地址：tile → tile_data + (tile<<5)；
 * lower_delta 见上方宏（tm0=1 / tm3=30），**不可写成常量 1**。 */
static void blit_column_at_tile(TextPrinter *win, uint16_t tile,
                                uint16_t lower_delta,
                                const uint8_t *src_u, const uint8_t *src_l)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    uint8_t fg_ov = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    uint8_t color_c = fg_ov ? fg_ov : win_u8(win, WIN_COLOR_C);
    uint8_t color_d = win_u8(win, WIN_COLOR_D);
    uint8_t color_e = win_u8(win, WIN_COLOR_E);
    uint8_t colors[16];
    uint16_t lower = (uint16_t)(tile + lower_delta);
    uint8_t *dst_u;
    uint8_t *dst_l;
    unsigned i;

    if (!tile_data)
        return;

    /* 4bpp 值→色号 LUT：0→底色、14→阴影、15→前景（其余兜底底色）。 */
    for (i = 0; i < 16u; i++)
        colors[i] = color_d;
    colors[14] = color_e;
    colors[15] = color_c;

    dst_u = tile_data + ((uint32_t)tile << 5);
    dst_l = tile_data + ((uint32_t)lower << 5);

    blend_glyph_4bpp((uint32_t *)(void *)dst_u, 0, src_u, 8u, 0u, colors);
    blend_glyph_4bpp((uint32_t *)(void *)dst_l, 0, src_l, 8u, 0u, colors);
    UpdateTilemap_Origin(win, tile, lower);
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
}

/* mode0 单列：tile = TILE_BASE + TILE_OFFSET（官方 tm0 线性游标），
 * 画完后额外推 TILE_OFFSET += 2（官方 [win+0x18]+=2，一列占上下两 tile）。 */
static void blit_column_mode0(TextPrinter *win,
                              const uint8_t *src_u, const uint8_t *src_l)
{
    uint16_t base = win_u16(win, WIN_TILE_BASE);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    uint16_t tile = (uint16_t)(base + off);

    blit_column_at_tile(win, tile, TM0_LOWER_DELTA, src_u, src_l);
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

/* tm3 单列 tile 号（官方 tm3 2D 布局坐标，反汇编 @0x08003500 实证）：
 *   tile = (cursorX[0x1A] + cursorTileX[0x1B]) + 2 + TILE_BASE[0x16]
 *          + (cursorY[0x1C] + cursorTileY[0x1D]) * 30
 * 官方 tm3 每列只推 [0x1B]（cursorTileX += 1），落点用当前 [0x1B] 现算。
 * 16px 整格 2 列 → 循环 2 次，每列 tile 号 +1（X 方向一格）。 */
static uint16_t tm3_tile_no(TextPrinter *win)
{
    uint16_t x = (uint16_t)(win_u8(win, WIN_CURSOR_X)
                            + win_u8(win, WIN_CURSOR_TILE_X));
    uint8_t  y = (uint8_t)(win_u8(win, WIN_CURSOR_Y)
                           + win_u8(win, WIN_CURSOR_TILE_Y));
    uint16_t base = win_u16(win, WIN_TILE_BASE);

    return (uint16_t)(x + 2u + base + (uint16_t)y * 30u);
}

/* tm3 汉字整格：16px 主字体（2 列）/ font4 小字（8px 1 列），
 * 复用 blit_column_at_tile，落点走 2D 布局公式。 */
static void print_glyph_mode3(TextPrinter *win, uint16_t gidx,
                              uint8_t font_id, unsigned cols)
{
    uint8_t buf[CHS_CELL_BYTES];
    unsigned col;

    decompress_chs_glyph(buf, gidx, font_id);

    for (col = 0; col < cols; col++) {
        const uint8_t *src_u = buf + (col ? 0x40u : 0x00u);
        const uint8_t *src_l = buf + (col ? 0x60u : 0x20u);

        blit_column_at_tile(win, tm3_tile_no(win), TM3_LOWER_DELTA,
                            src_u, src_l);
    }
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
    case 3:
        print_glyph_mode3(win, (uint16_t)(gidx & 0xFFFFu), fn, cols);
        break;
    case 1:
        /* tm1 官方只写 tilemap（预渲染 tile 号），无动态 tileData 区域；
         * 中文像素路径需先定「动态 tile 号分配」方案（步骤 3 后续）。
         * 暂维持消费 + 推进（cursorTileX += cols）。 */
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
