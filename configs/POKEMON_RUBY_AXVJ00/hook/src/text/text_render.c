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

/* 列步进：写完一列后"下一列"的 tile 号增量。
 *   tm0 = 2 —— 上下半相邻(+1)，一列占 2 个 tile 号；
 *   tm3 = 1 —— 上下半隔 30，一列只占 1 个 tile 号。 */
#define TM0_COL_STRIDE       2u
#define TM3_COL_STRIDE       1u

/* =====================================================================
 * 行相位（仅 12px 模式需要；16px 整格为零状态，不参与）
 *
 * 官方游标只有"整列"粒度（TILE_OFFSET / cursorTileX），没有像素相位字段。
 * 12px 步进必然产生半列相位 ⇒ 必须自存（game.h struct ChsPhase）。
 * 归零策略：**不检测换行事件**，改用行指纹 key —— 换行/换窗/换流都会让
 *   TILE_BASE / CURSOR_Y / CURSOR_TILE_Y / template 之一变化 ⇒ key 失配
 *   ⇒ px 归零。另加游标失配检测（重印/跳列）兜底，防相位错位写坏 VRAM。
 * ⚠ 表落 EWRAM 绝对地址 0x0203FF90：game.ld 无 .bss/.data，普通可写
 *   static 会被静默塞进 ROM 恒 0 且不报错。
 * ===================================================================== */
#if CHS_ADVANCE_12
static uint16_t chs_phase_key(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint16_t w = tpl ? (uint16_t)(((uintptr_t)tpl >> 2) & 0xFFFFu) : 0;

    /* | 0x8000：保证非 0，兼作"槽已占用"标记 */
    return (uint16_t)((win_u16(win, WIN_TILE_BASE)
                       ^ ((uint16_t)win_u8(win, WIN_CURSOR_Y) << 8)
                       ^ ((uint16_t)win_u8(win, WIN_CURSOR_TILE_Y) << 4)
                       ^ w) | 0x8000u);
}

static volatile struct ChsPhase *chs_phase_slot(TextPrinter *win, uint16_t key)
{
    volatile struct ChsPhase *tab =
        (volatile struct ChsPhase *)ADDR_CHS_PHASE;
    unsigned i;

    for (i = 0; i < CHS_PHASE_COUNT; i++)
        if (tab[i].key == key)
            return &tab[i];

    for (i = 0; i < CHS_PHASE_COUNT; i++) {
        if (tab[i].key == 0u) {
            tab[i].key = key;
            tab[i].px  = 0;
            tab[i].tx0 = win_u8(win, WIN_CURSOR_TILE_X);
            return &tab[i];
        }
    }
    /* 表满：复用 0 号（降级，仅相位归零，不写坏内存） */
    tab[0].key = key;
    tab[0].px  = 0;
    tab[0].tx0 = win_u8(win, WIN_CURSOR_TILE_X);
    return &tab[0];
}

/* 当前行内相位（0..7） */
static unsigned chs_phase_get(TextPrinter *win)
{
    uint16_t key = chs_phase_key(win);
    volatile struct ChsPhase *s = chs_phase_slot(win, key);
    uint8_t tx = win_u8(win, WIN_CURSOR_TILE_X);

    /* 失配检测：期望已走列数 = px>>3；回退/跳列/重印 ⇒ 归零重锚 */
    if (tx < s->tx0 || (unsigned)(tx - s->tx0) != (unsigned)(s->px >> 3)) {
        s->px  = 0;
        s->tx0 = tx;
    }
    return (unsigned)(s->px & 7u);
}

/* 推进 advance 像素（中文=CHS_GLYPH_ADVANCE_PX；半角=CHS_GLYPH_ADVANCE_JP_PX） */
static void chs_phase_advance(TextPrinter *win, unsigned adv_px)
{
    uint16_t key = chs_phase_key(win);
    volatile struct ChsPhase *s = chs_phase_slot(win, key);

    s->px = (uint16_t)(s->px + adv_px);
}
#endif /* CHS_ADVANCE_12 */

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

/* =====================================================================
 * 任意墨宽的两段式渲染（docs/12PX_落地方案.md §3.2，CHS_ADVANCE_12 时启用）
 *
 * 中文 12px（ink=12）/ 半角 8px（ink=8）走同一骨架：advance 不是 8 的倍数
 * 时必然产生半列相位（12 mod 8 = 4 ⇒ phase 只在 0/4 两态）。
 * blend 原语一次最多写 8 像素宽，故一个字拆两段：
 *   第一段：本 tile，startPixel = phase，宽 w0 = min(8-phase, ink)，源列 [0, w0)
 *   第二段：下一列 tile，startPixel = 0，宽 w1 = ink-w0，   源列 [w0, ink)
 * 两段都**恰好落在目标 tile 的可用区间内**（phase+w0 ≤ 8、0+w1 ≤ 8），
 * 因此永不溢出，spillTile 一律传 0。
 *
 * 返回推进列数 = (phase + ink) / 8：
 *   ink=12 → phase0:1 列 / phase4:2 列；ink=8 → phase0:1 列 / phase4:1 列。
 * 不变量 px = 8*col + phase 恒成立（推进 (phase+ink)/8 列 + px 加 ink）。
 * ===================================================================== */
#if CHS_ADVANCE_12
static void chs_fill_bg(TextPrinter *win, uint16_t tile, uint16_t lower_delta,
                        unsigned x0, unsigned x1);   /* 定义在下方 */

static unsigned print_glyph_px(TextPrinter *win, uint16_t tile,
                               uint16_t lower_delta, uint16_t col_stride,
                               const uint8_t *g128, unsigned ink,
                               unsigned phase)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
    uint8_t fg_ov, color_c, color_d, color_e;
    uint8_t colors[16];
    uint32_t w0 = (8u - phase < ink) ? (8u - phase) : ink;
    uint32_t w1 = ink - w0;
    uint16_t t0 = tile;
    uint16_t t1 = (uint16_t)(tile + col_stride);
    uint8_t tx0 = win_u8(win, WIN_CURSOR_TILE_X);
    uint8_t up[32], lo[32];
    unsigned adv = (phase + ink) / 8u;
    unsigned i;

    if (adv < 1u)
        adv = 1u;
    if (!tpl)
        return adv;
    tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!tile_data)
        return adv;

    fg_ov   = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    color_c = fg_ov ? fg_ov : win_u8(win, WIN_COLOR_C);
    color_d = win_u8(win, WIN_COLOR_D);
    color_e = win_u8(win, WIN_COLOR_E);
    for (i = 0; i < 16u; i++)
        colors[i] = color_d;
    colors[14] = color_e;
    colors[15] = color_c;

    /* 第一段：本 tile，起点 phase —— 源列 [0, w0) */
    extract_cols(g128, 0u, w0, up, lo);
    (void)blend_glyph_4bpp(
        (uint32_t *)(void *)(tile_data + ((uint32_t)t0 << 5)),
        0, up, w0, phase, colors);
    (void)blend_glyph_4bpp(
        (uint32_t *)(void *)(tile_data + ((uint32_t)(t0 + lower_delta) << 5)),
        0, lo, w0, phase, colors);

    if (w1 != 0u) {
        /* 第二段：下一列 tile，起点 0 —— 源列 [w0, ink)
         * （phase!=0 时该段横跨 TL/TR 两个源 tile，由 extract_cols 拼好） */
        extract_cols(g128, w0, w1, up, lo);
        (void)blend_glyph_4bpp(
            (uint32_t *)(void *)(tile_data + ((uint32_t)t1 << 5)),
            0, up, w1, 0u, colors);
        (void)blend_glyph_4bpp(
            (uint32_t *)(void *)(tile_data + ((uint32_t)(t1 + lower_delta) << 5)),
            0, lo, w1, 0u, colors);
    }

    /* tilemap：本列必写；第二段存在时下一列也要写 */
    UpdateTilemap_Origin(win, t0, (uint16_t)(t0 + lower_delta));
    if (w1 != 0u) {
        win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(tx0 + 1u));
        UpdateTilemap_Origin(win, t1, (uint16_t)(t1 + lower_delta));
    }
    /* 游标净推进 = adv（不是 2）；下一字的起始 tile 由此决定 */
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(tx0 + adv));

    /* ---------------------------------------------------------------
     * 尾像素补齐（2026-08-31，修「奇数中文字后的透明小格子」）
     *
     * 本字最后一列往往只写了一部分（例：ink=12 / phase=0 时 t1 只写
     * px0-3）。剩余像素若无人负责，就会保留**上一次使用该 tile 的残留**
     * ——行/串到此结束时表现为一块 4px 宽的透明/花屏小格子；
     * 汉字个数为奇数时末尾必然落在半列，偶数时恰好对齐列边界，
     * 故症状只在奇数个字后出现。
     *
     * 补齐为底色是安全的：下一个字若相位非 0，其第一段会完整覆盖这段
     * 区间；若后面没有字了，留下的是干净的 4px 底色而非未初始化 VRAM。
     * --------------------------------------------------------------- */
    if (w1 != 0u)
        chs_fill_bg(win, t1, lower_delta, (unsigned)w1, 8u);
    else
        chs_fill_bg(win, t0, lower_delta, phase + (unsigned)w0, 8u);

    return adv;
}
#endif /* CHS_ADVANCE_12 */

/* =====================================================================
 * 底色填充：把某 tile 的 [x0, x1) 像素区间写成 colors[0]（窗口底色）。
 * 4bpp 源恒 0 ⇒ expand 出全 0 nibble ⇒ colors[0] = color_d（底色）。
 *
 * 两处使用：
 *   ① chs_flush_to_col —— 半角交原生前把相位补齐到列首；
 *   ② print_glyph_px   —— 每个字收尾时补齐最后一列的剩余像素。
 * ===================================================================== */
#if CHS_ADVANCE_12
static void chs_fill_bg(TextPrinter *win, uint16_t tile, uint16_t lower_delta,
                        unsigned x0, unsigned x1)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
    uint8_t fg_ov, color_c, color_d, color_e;
    uint8_t colors[16];
    uint8_t zero[32];
    unsigned i;

    if (x1 <= x0 || x0 > 7u)
        return;
    if (x1 > 8u)
        x1 = 8u;
    if (!tpl)
        return;
    tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!tile_data)
        return;

    fg_ov   = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    color_c = fg_ov ? fg_ov : win_u8(win, WIN_COLOR_C);
    color_d = win_u8(win, WIN_COLOR_D);
    color_e = win_u8(win, WIN_COLOR_E);
    for (i = 0; i < 16u; i++)
        colors[i] = color_d;
    colors[14] = color_e;
    colors[15] = color_c;
    for (i = 0; i < 32u; i++)
        zero[i] = 0u;

    (void)blend_glyph_4bpp(
        (uint32_t *)(void *)(tile_data + ((uint32_t)tile << 5)),
        0, zero, x1 - x0, x0, colors);
    (void)blend_glyph_4bpp(
        (uint32_t *)(void *)(tile_data + ((uint32_t)(tile + lower_delta) << 5)),
        0, zero, x1 - x0, x0, colors);
}
#endif /* CHS_ADVANCE_12 */

/* =====================================================================
 * 相位补齐（2026-08-31，12px 半角混排修复）
 *
 * 官方 tm0/tm3 处理器只会从 startPixel=0 写整列 8px，**不知道像素相位**。
 * 若在 phase=4 时把半角（标点/数字/拉丁）交给原生：
 *   - 它被画到 [8c, 8c+8)，压掉前一个汉字的尾 4px（本该在 [8c, 8c+4)）；
 *   - 它自己应占的 [8c+4, 8c+12) 中，落在下一列 tile px0-3 的那 4px 无人写，
 *     而下一个汉字 phase 仍是 4、只写 px4-7 ⇒ 该 4px 永久空洞（透明小格子）。
 *
 * 补齐策略：调用原生前，先把当前 tile 剩余像素 [phase,8) 用底色填掉，
 * 游标推到列首（px 补成 8 的倍数）。代价是半角前多 4px 空白（视觉上是
 * 标点留白，可接受），换来：前字不被覆盖、无空洞、相位不变量保持。
 * ===================================================================== */
#if CHS_ADVANCE_12
static void chs_flush_to_col(TextPrinter *win, uint16_t lower_delta,
                             uint16_t col_stride, uint16_t tile)
{
    uint8_t tx;
    unsigned phase = chs_phase_get(win);

    if (phase == 0u)
        return;

    /* 填底色：跨度 [phase,8)（startPixel+width = 8，无溢出） */
    chs_fill_bg(win, tile, lower_delta, phase, 8u);

    /* 推到列首：tm0 需同时推 TILE_OFFSET（tile 号来源），tm3 只推 cursorTileX */
    tx = win_u8(win, WIN_CURSOR_TILE_X);
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(tx + 1u));
    if ((win_u8(win, WIN_TEXTMODE) & 7u) == 0u)
        win_set_u16(win, WIN_TILE_OFFSET,
                    (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + col_stride));
    chs_phase_advance(win, 8u - phase);
}
#endif /* CHS_ADVANCE_12 */

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

/* mode0 汉字：12px 两段式（cols=2 主字体）/ 16px 整格回退 / font4 小字 8px 单列。 */
static void print_glyph_mode0(TextPrinter *win, uint16_t gidx,
                              uint8_t font_id, unsigned cols)
{
    uint8_t buf[CHS_CELL_BYTES];
    unsigned col;

#if CHS_ADVANCE_12
    if (cols == 2u) {
        uint16_t base = win_u16(win, WIN_TILE_BASE);
        uint16_t off  = win_u16(win, WIN_TILE_OFFSET);
        unsigned phase = chs_phase_get(win);
        unsigned adv;

        decompress_chs_glyph(buf, gidx, font_id);
        adv = print_glyph_px(win, (uint16_t)(base + off),
                             TM0_LOWER_DELTA, TM0_COL_STRIDE, buf,
                             CHS_GLYPH_ADVANCE_PX, phase);
        /* TILE_OFFSET 单位同列步进（tm0 每列 2 个 tile 号） */
        win_set_u16(win, WIN_TILE_OFFSET,
                    (uint16_t)(off + (uint16_t)(adv * TM0_COL_STRIDE)));
        chs_phase_advance(win, CHS_GLYPH_ADVANCE_PX);
        return;
    }
#endif

    decompress_chs_glyph(buf, gidx, font_id);

    for (col = 0; col < cols; col++) {
        const uint8_t *src_u = buf + (col ? 0x40u : 0x00u);
        const uint8_t *src_l = buf + (col ? 0x60u : 0x20u);

        blit_column_mode0(win, src_u, src_l);
    }
#if CHS_ADVANCE_12
    /* 小字（cols==1）也须推进相位，否则中文混排时相位错乱 */
    chs_phase_advance(win, CHS_GLYPH_ADVANCE_JP_PX);
#endif
}

/* =====================================================================
 * SYM 中文标点（PCS 0x36-0x3E）——**自绘，不回退原生**（2026-08-31 修复）
 *
 * ⚠ 为什么必须自绘：fontfunc thunk 的链路是
 *   TranslateHandleChar（F9 协议 / SLT2 slot 表）‖ FontFunc_NativeDispatch。
 *   标点作为单字节几乎不可能命中 slot 表 ⇒ 直接落到原生处理器 ⇒ 画出
 *   **JP 字体的同码字形**（用户实测「标点符号显示成了奇怪的日文」）。
 *   且原生只从 startPixel=0 写整列 8px，与 12px 相位无关 ⇒ 顺带造成
 *   「奇数字后透明小格子」。故：tm0/tm3 一律走 print_glyph_px 自绘。
 *
 * 字库：ADDR_FONT_CHS_SYM，64B/枚，容器 [U@+0][L@+32]，8 列宽。
 * 为复用 extract_cols（它认 128B/16 列的中文槽），这里把 U/L 填进
 * 128B 暂存槽的 TL/BL，TR/BR 留 0 —— 半角只取列 [0,8)，永远读不到 TR/BR。
 * ===================================================================== */
static uint16_t tm3_tile_no(TextPrinter *win);   /* 定义在下方 */

static int draw_sym_px(TextPrinter *win, uint32_t sym_idx)
{
    const uint8_t *sym =
        (const uint8_t *)ADDR_FONT_CHS_SYM + sym_idx * 64u;
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
    uint8_t buf[CHS_CELL_BYTES];
    uint16_t tile;
    uint16_t lower_delta;
    uint16_t col_stride;
    unsigned phase;
    unsigned adv;
    unsigned i;

    if (tm != 0u && tm != 3u)
        return 0;               /* tm1/tm2 无像素路径：交原生 */

    for (i = 0; i < CHS_CELL_BYTES; i++)
        buf[i] = 0u;
    copy_tile32(buf + 0x00u, sym + 0u);    /* TL ← upper */
    copy_tile32(buf + 0x20u, sym + 32u);   /* BL ← lower */

    if (tm == 0u) {
        tile        = (uint16_t)(win_u16(win, WIN_TILE_BASE)
                                 + win_u16(win, WIN_TILE_OFFSET));
        lower_delta = TM0_LOWER_DELTA;
        col_stride  = TM0_COL_STRIDE;
    } else {
        tile        = tm3_tile_no(win);
        lower_delta = TM3_LOWER_DELTA;
        col_stride  = TM3_COL_STRIDE;
    }

#if CHS_ADVANCE_12
    phase = chs_phase_get(win);
    adv = print_glyph_px(win, tile, lower_delta, col_stride, buf,
                         CHS_GLYPH_ADVANCE_JP_PX, phase);
    if (tm == 0u)
        win_set_u16(win, WIN_TILE_OFFSET,
                    (uint16_t)(win_u16(win, WIN_TILE_OFFSET)
                               + (uint16_t)(adv * TM0_COL_STRIDE)));
    chs_phase_advance(win, CHS_GLYPH_ADVANCE_JP_PX);
#else
    (void)phase;
    (void)adv;
    blit_column_at_tile(win, tile, lower_delta, buf + 0x00u, buf + 0x20u);
    if (tm == 0u)
        win_set_u16(win, WIN_TILE_OFFSET,
                    (uint16_t)(win_u16(win, WIN_TILE_OFFSET)
                               + (uint16_t)TM0_COL_STRIDE));
#endif
    return 1;
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

/* tm3 汉字：12px 两段式（cols=2 主字体）/ 16px 整格回退 / font4 小字 8px 单列，
 * 落点走 tm3 的 2D 布局公式（tm3_tile_no）。 */
static void print_glyph_mode3(TextPrinter *win, uint16_t gidx,
                              uint8_t font_id, unsigned cols)
{
    uint8_t buf[CHS_CELL_BYTES];
    unsigned col;

#if CHS_ADVANCE_12
    if (cols == 2u) {
        unsigned phase = chs_phase_get(win);

        decompress_chs_glyph(buf, gidx, font_id);
        (void)print_glyph_px(win, tm3_tile_no(win),
                             TM3_LOWER_DELTA, TM3_COL_STRIDE, buf,
                             CHS_GLYPH_ADVANCE_PX, phase);
        chs_phase_advance(win, CHS_GLYPH_ADVANCE_PX);
        return;
    }
#endif

    decompress_chs_glyph(buf, gidx, font_id);

    for (col = 0; col < cols; col++) {
        const uint8_t *src_u = buf + (col ? 0x40u : 0x00u);
        const uint8_t *src_l = buf + (col ? 0x60u : 0x20u);

        blit_column_at_tile(win, tm3_tile_no(win), TM3_LOWER_DELTA,
                            src_u, src_l);
    }
#if CHS_ADVANCE_12
    chs_phase_advance(win, CHS_GLYPH_ADVANCE_JP_PX);
#endif
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
#if CHS_ADVANCE_12
        chs_phase_advance(win, CHS_GLYPH_ADVANCE_PX);
#endif
        break;
    case 2: {
        uint32_t dst = win_u32(win, WIN_TILE_DATA);

        if (dst != 0u)
            win_set_u32(win, WIN_TILE_DATA, dst + cols * 0x40u);
#if CHS_ADVANCE_12
        chs_phase_advance(win, CHS_GLYPH_ADVANCE_JP_PX);
#endif
        break;
    }
    default:
        break;
    }
}

/* =====================================================================
 * PCS 单字节（半角）统一入口 DrawHalfWidth
 *
 * 调用方：①fontfunc_hook.c 的 4 个 thunk（原生分发**之前**）；
 *         ②DrawGlyph（slot/phrase 替换流内的半角字节）。
 * 返回 1=已消费；0=交还调用方（仅 tm1/tm2 且非 SYM 时出现）。
 *
 * 分工：
 *   SYM 标点带（0x36-0x3E，tm0/tm3）→ draw_sym_px 用中文标点字库自绘，
 *     相位感知，不会画出 JP 同码字形，也不会打乱相位。
 *   其余半角（数字/拉丁/空格/… ，tm0/tm3）→ 先 chs_flush_to_col 把相位
 *     补齐到列首，再交原生从 startPixel=0 画（否则原生会压掉前一个汉字的
 *     尾 4px，并留下 4px 无人写的空洞 = 透明小格子）。
 *   tm1/tm2 无像素路径 → 直接交原生，不动相位。
 * ===================================================================== */
int DrawHalfWidth(TextPrinter *win, uint32_t cur_char)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;

    if (cur_char >= SYM_GLYPH_BASE
        && cur_char < SYM_GLYPH_BASE + SYM_GLYPH_COUNT)
        return draw_sym_px(win, cur_char - SYM_GLYPH_BASE);

    if (tm != 0u && tm != 3u)
        return 0;

#if CHS_ADVANCE_12
    if (tm == 0u)
        chs_flush_to_col(win, TM0_LOWER_DELTA, TM0_COL_STRIDE,
                         (uint16_t)(win_u16(win, WIN_TILE_BASE)
                                    + win_u16(win, WIN_TILE_OFFSET)));
    else
        chs_flush_to_col(win, TM3_LOWER_DELTA, TM3_COL_STRIDE,
                         tm3_tile_no(win));
#endif
    FontFunc_NativeDispatch(tm, win, cur_char);
#if CHS_ADVANCE_12
    chs_phase_advance(win, CHS_GLYPH_ADVANCE_JP_PX);
#endif
    return 1;
}

/* PCS 单字节渲染入口（text_translater.c 中文替换流内消费）。
 * 返回 1=已消费（引擎零回落：不可印位直接吞掉）。 */
int DrawGlyph(TextPrinter *win, uint32_t cur_char)
{
    if (cur_char >= 0xF7u)
        return 1;   /* 控制码/终止符：不占像素，不推进相位 */

    (void)DrawHalfWidth(win, cur_char);
    return 1;
}
