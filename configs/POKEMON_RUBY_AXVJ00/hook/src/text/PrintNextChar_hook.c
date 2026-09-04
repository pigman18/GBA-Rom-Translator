/* =====================================================================================
 * PrintNextChar_hook.c — v8 渲染层（PrintNextChar hook 的消费端）
 *
 * 设计原则（用户拍板 2026-09-04，v8 顺序 tile 分配器）：
 *   - 一个字的 tile 号只有一个来源：顺序分配器 v8_alloc_tile()（tile_alloc.c），
 *     运行时读 tilemap 活引用得避让带，顺序放入、跳过占用。16px/12px/8px 统一
 *     走同一条路径，不再有「静态表命中走 A、未命中走 B」的分裂。
 *   - 渲染管线三段式、彼此独立，可 16+12+8 混排：
 *       Stage1 解压     GetGlyph(win, code, out128, &w)   —— text_translater.c 提供
 *       Stage2 栅格化   chs_rasterize(g128, fontSize, ...) —— 本文件，纯函数，
 *                       只把字模按字号切成若干 4bpp 列对，不碰 VRAM/游标
 *       Stage3 落址     chs_place(win, textMode, fontSize, ...) —— 本文件，
 *                       tile 号走 v8_alloc_tile，写 VRAM + UTM + 推游标
 *   - 字号决策 = getFontSize(win) 钩子（chs_print 内联），font4/tm2→8px，设置菜单
 *     左标签 16px / 右候选 12px（curX<8），其余 12px。
 *
 * 约定：
 *   - fontNum==4  → 8px 小字，fontSize 形参忽略；
 *     其余         → fontSize=12 或 16（默认 12，12px 相位共享）。
 *   - 半角（非中文标点）交 draw_jp_glyph（官方字库取字，统一走 v8 分配器）；
 *     中文标点带（0x36-0x3E）用中文标点字库自绘一列 8px。
 * ===================================================================================== */
#include "text.h"
#include "blend_glyph.h"
#include "scene_cfg.h"
#include "tile_alloc.h"

/* =====================================================================
 * §V8 Stage3 落址分配器（tile 号独立 + 位置交官方；2026-09-04 定案）
 *   两条腿解耦：
 *     【tile 号】（写 tile data 的索引）→ 顺序分配器 v8_alloc_tile()，
 *        每画一个字领连续 glyph_len 个空闲相对号，跳过避让带，顺序递增。
 *        每字独享 tile，替换/叠加不再发生。
 *     【屏幕位置】（写 tilemap 哪格）→ 继续交官方光标（继续调 UpdateTilemap，
 *        它内部经 GetCursorTilemapPointer 用 CX/TX/CY/TY 现算表项位置，官方
 *        管得对，保留）。
 *   各 textMode 只决定「屏幕光标怎么推」（决定下一字放屏幕哪列）：
 *     mode0 线性 → 官方推 TILE_OFFSET += 2 + cursorTileX += 1。
 *     mode1      → 与 mode0 同构。
 *     mode3 网格 → 官方只推 cursorTileX += 1，不推 TILE_OFFSET。
 *     mode2 血条 → 缓冲指针，无 VRAM/tilemap 分配。
 * ===================================================================== */
#define V6_PITCH12          12u
#define V6_PITCH16          16u

/* =====================================================================
 * §V8 场景字号查询（getFontSize 的落点；2026-09-04 简化）
 *   键 = 窗口模板地址（tpl = win[0x00]）。命中则按 curX 分区决定字号；
 *   未命中 → 默认 12px。不再有行基址表 / off 分区 / 标题带。
 *   （结构定义与配置实例见 scene_cfg.h / scene_cfg.c。）
 * ===================================================================== */

/* 查询访问器（结构/配置实例 extern 自 scene_cfg.h；本文件是唯一实现方） */
const struct V6SceneRule *v6_scene_lookup(uint32_t tpl)
{
    unsigned i;
    for (i = 0; i < kV6SceneN; i++)
        if (kV6Scenes[i].tpl == tpl)
            return &kV6Scenes[i];
    return 0;
}

const struct V6Zone *v6_scene_zone(const struct V6SceneRule *r, uint8_t cx)
{
    unsigned i;
    for (i = 0; i < r->zone_n; i++)
        if (cx < r->zones[i].cx_hi)
            return &r->zones[i];
    return &r->zones[r->zone_n - 1u];
}

uint8_t v6_scene_font(const struct V6SceneRule *r, uint8_t cx)
{
    return v6_scene_zone(r, cx)->font_px;
}

/* =====================================================================
 * §V8 getFontSize：字号决策钩子（回答用户「加个钩子决策字号」的设想）
 *   最少必要输入，不塞色号/TILE_BASE 等渲染层内部字段：
 *     font4 → 8px；tm2 → 8px；设置菜单 curX<8 → 16px 否则 12px；其余 12px。
 * ===================================================================== */
static uint8_t get_font_size(TextPrinter *win, uint8_t fn, uint8_t tm)
{
    const struct V6SceneRule *rule;

    if (fn == 4u)
        return 8u;
    if (tm == 2u)
        return 8u;
    rule = v6_scene_lookup((uint32_t)(uintptr_t)win_template(win));
    if (rule)
        return v6_scene_font(rule, win_u8(win, WIN_CURSOR_X));
    return 12u;
}

/* =====================================================================
 * §V8 Stage2 栅格化（纯函数，零状态）
 *   把 128B 中文字模（[TL@0][BL@32][TR@64][BR@96]）按字号切成若干列对，
 *   每个列对 = 一块 upper 32B + 一块 lower 32B 的 4bpp tile 数据。
 *   fontSize=8  → 1 列（TL/BL）；16 → 2 列（TL/BL, TR/BR）；12 → extract_cols。
 *   返回列数；cols==0 表示不可栅格化。
 * ===================================================================== */
static unsigned chs_rasterize(const uint8_t g128[CHS_CELL_BYTES],
                              unsigned fontSize,
                              uint8_t out[4][32])
{
    if (fontSize == 8u) {
        for (unsigned i = 0; i < 32u; i++) {
            out[0][i] = g128[0x00 + i];
            out[1][i] = g128[0x20 + i];
        }
        return 1u;
    }

    if (fontSize == 16u) {
        for (unsigned i = 0; i < 32u; i++) {
            out[0][i] = g128[0x00 + i];
            out[1][i] = g128[0x20 + i];
            out[2][i] = g128[0x40 + i];
            out[3][i] = g128[0x60 + i];
        }
        return 2u;
    }

    /* fontSize==12：墨迹 12px，输出列数与相位有关，由落址层经 extract_cols 处理 */
    return 2u;
}

/* =====================================================================
 * §V8 12px 相位共享（CHS_ADVANCE_12=1）
 *   12px 步进 12 mod 8 = 4 ⇒ 相位只在 0/4 两态。相位 = 「行内像素游标」px，
 *   phase = px & 7。用 tile_alloc.c 的按行隔离单变量（v8_phase_get 内部按
 *   tpl^curY 行标识失配即归零）——同一行续接、换行/换窗口归零，不再有
 *   全局 8 槽跨窗口残留。
 *   tile 号：phase==0 领新列（v8_alloc_tile 领 2 tile），phase!=0 复用上一列
 *   （v8_phase_last_tile），相邻 12px 字共享半列。
 * ===================================================================== */
#if CHS_ADVANCE_12

/* 底色填充：把某列 tile 的 [x0,x1) 像素区间写成 colors[0]（窗口底色）。
 * 4bpp 源恒 0 ⇒ expand 全 0 nibble ⇒ colors[0] = color_d。 */
static void chs_fill_bg(TextPrinter *win, uint16_t tile, unsigned x0, unsigned x1)
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

    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)tile << 5)),
                           0, zero, x1 - x0, x0, colors);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(tile + 1u) << 5)),
                           0, zero, x1 - x0, x0, colors);
}

/* 任意墨宽两段式渲染（12px 中文 ink=12 / 8px 标点 ink=8）：
 *   phase + ink 不是 8 的倍数时拆两段，两段都落在目标 tile 可用区间内，永不溢出。
 *   tile 号：phase==0 领新列（v8_alloc_tile 领 2 tile），phase!=0 复用 last_tile。
 *   返回推进列数 adv=(phase+ink)/8，已推 cursorTileX 并记 last_tile。
 *   TILE_OFFSET 由调用方按 adv*2 推进（mode0/1）。 */
static unsigned print_glyph_px(TextPrinter *win,
                               const uint8_t g128[CHS_CELL_BYTES],
                               unsigned ink)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
    uint8_t fg_ov, color_c, color_d, color_e;
    uint8_t colors[16];
    uint8_t up[32], lo[32];
    unsigned px = v8_phase_get(win);
    unsigned phase = px & 7u;
    unsigned w0 = (8u - phase < ink) ? (8u - phase) : ink;
    unsigned w1 = ink - w0;
    unsigned adv = (phase + ink) / 8u;
    uint16_t t0, t1;
    uint8_t tx0 = win_u8(win, WIN_CURSOR_TILE_X);
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

    /* tile 号：phase==0 领新列，phase!=0 复用上一列（相位共享半列） */
    if (phase == 0u) {
        t0 = v8_alloc_tile(win, 12u, 2u);
        if (t0 == 0u)
            return adv;                       /* 无空闲：放弃，宁缺不砸 UI */
    } else {
        t0 = v8_phase_last_tile();
    }
    t1 = (w1 != 0u) ? v8_alloc_tile(win, 12u, 2u) : 0u;

    /* 第一段：源列 [0,w0) → t0 的 [phase, phase+w0) */
    extract_cols(g128, 0u, w0, up, lo);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)t0 << 5)),
                           0, up, w0, phase, colors);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(t0 + 1u) << 5)),
                           0, lo, w0, phase, colors);

    if (w1 != 0u) {
        /* 第二段：源列 [w0,ink) → t1 的 [0,w1) */
        extract_cols(g128, w0, w1, up, lo);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)t1 << 5)),
                               0, up, w1, 0u, colors);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(t1 + 1u) << 5)),
                               0, lo, w1, 0u, colors);
        /* 尾像素补齐：t1 剩余 [w1,8) 补底色 */
        chs_fill_bg(win, t1, w1, 8u);
    }

    /* tilemap：t0 列必写；第二段存在时 t1 列也写（表项位置走官方光标） */
    UpdateTilemap_PreserveCursorX(win, t0, (uint16_t)(t0 + 1u));
    if (w1 != 0u) {
        win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(tx0 + 1u));
        UpdateTilemap_PreserveCursorX(win, t1, (uint16_t)(t1 + 1u));
    }
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(tx0 + adv));

    v8_phase_advance((uint16_t)ink);
    v8_phase_set_last_tile((w1 != 0u) ? t1 : t0);
    return adv;
}

#endif /* CHS_ADVANCE_12 */

/* §V8 Stage3 单列写像素 + UTM（tile 号来自 v8_alloc_tile）：
 *   tile_data[tile*32] 和 tile_data[(tile+lower_delta)*32] 各写一个 8x8 tile。
 *   UpdateTilemap_PreserveCursorX 用传入的 tile/lower 作表项**值**，表项**位置**
 *   由内部 cursorX/cursorTileX/cursorY/cursorTileY 算（必须保留官方语义）。
 *   cursorTileX += 1 保留——光标推进是"下一字屏幕列"，与 tile 号解耦。 */
static void chs_place_col(TextPrinter *win, uint16_t tile, uint16_t lower_delta,
                          const uint8_t *src_u, const uint8_t *src_l)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
    uint8_t fg_ov, color_c, color_d, color_e;
    uint8_t colors[16];
    uint16_t lower = (uint16_t)(tile + lower_delta);

    if (!tpl)
        return;
    tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!tile_data || tile == 0u)
        return;

    fg_ov   = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    color_c = fg_ov ? fg_ov : win_u8(win, WIN_COLOR_C);
    color_d = win_u8(win, WIN_COLOR_D);
    color_e = win_u8(win, WIN_COLOR_E);
    for (unsigned i = 0; i < 16u; i++)
        colors[i] = color_d;
    colors[14] = color_e;
    colors[15] = color_c;

    blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)tile << 5)),
                     0, src_u, 8u, 0u, colors);
    blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)lower << 5)),
                     0, src_l, 8u, 0u, colors);
    UpdateTilemap_PreserveCursorX(win, tile, lower);
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
}

/* =====================================================================
 * §V8 日文/半角统一绘制（官方字库取字 + 统一 v8 分配器）
 *   中文走中文字库 GetGlyph，日文/半角走官方字库 GetGlyphTilePointers，
 *   字形统一进 128B 4bpp 容器 → print_glyph_px / chs_place_col，共用 v8_alloc_tile
 *   领 tile，不再交回官方 FontFunc（官方 base+TILE_OFFSET 每行清零 → 行间替换）。
 * ===================================================================== */
static void jp_glyph_to_g128(uint8_t font_num, uint16_t glyph,
                             uint8_t g128[CHS_CELL_BYTES])
{
    uint8_t *up, *lo;
    unsigned i;

    GetGlyphTilePointers_Origin(font_num, glyph, &up, &lo);
    for (i = 0; i < CHS_CELL_BYTES; i++)
        g128[i] = 0u;

    if (FontIsShadowed(font_num)) {           /* font 3/4/5：4bpp 索引 0/14/15 */
        copy_tile32(g128 + 0x00u, up);
        copy_tile32(g128 + 0x20u, lo);
    } else {                                  /* font 0/1/2/6：1bpp → 索引 15/0 */
        CopyGlyph1bppTo4bpp_Origin(up, g128 + 0x00u, 15u, 0u);
        CopyGlyph1bppTo4bpp_Origin(lo, g128 + 0x20u, 15u, 0u);
    }
}

static int draw_jp_glyph(TextPrinter *win, uint8_t font_num, uint16_t glyph)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
    uint8_t g128[CHS_CELL_BYTES];

    if (tm != 0u && tm != 1u && tm != 3u)
        return 0;                             /* tm2 缓冲 / 未知：交原生 */
    if (font_num > 6u)
        font_num = 3u;

    jp_glyph_to_g128(font_num, glyph, g128);

#if CHS_ADVANCE_12
    {
        unsigned adv = print_glyph_px(win, g128, CHS_GLYPH_ADVANCE_JP_PX);
        if (tm == 0u || tm == 1u)
            win_set_u16(win, WIN_TILE_OFFSET,
                        (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + adv * 2u));
    }
#else
    {
        uint16_t tile = v8_alloc_tile(win, 12u, 2u);
        chs_place_col(win, tile, 1u, g128 + 0x00u, g128 + 0x20u);
        if (tm == 0u || tm == 1u)
            win_set_u16(win, WIN_TILE_OFFSET,
                        (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + 2u));
    }
#endif
    return 1;
}

/* =====================================================================
 * §V8 Stage3 落址：统一走 v8_alloc_tile（无静态表分支）。
 * ===================================================================== */
static void chs_place(TextPrinter *win, uint8_t textMode,
                      uint8_t fontNum, unsigned fontSize,
                      const uint8_t g128[CHS_CELL_BYTES])
{
    uint8_t tm = textMode & 7u;
    uint8_t buf[4][32];
    unsigned cols, col;

    (void)fontNum;

    if (tm == 2u) {
        /* mode2 血条缓冲：无 VRAM 分配，推缓冲指针（8px 槽每列 +0x40） */
        uint32_t dst = win_u32(win, WIN_TILE_DATA);
        if (dst != 0u)
            win_set_u32(win, WIN_TILE_DATA,
                        dst + ((fontSize == 8u) ? 1u : 2u) * 0x40u);
        return;
    }
    if (tm != 0u && tm != 1u && tm != 3u)
        return;

#if CHS_ADVANCE_12
    if (fontSize == 12u) {
        /* 12px 主字体：两段式 + 相位共享（tile 号走 v8_alloc_tile）。 */
        unsigned adv = print_glyph_px(win, g128, 12u);
        if (tm == 0u || tm == 1u)
            win_set_u16(win, WIN_TILE_OFFSET,
                        (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + adv * 2u));
        return;
    }
#endif

    cols = chs_rasterize(g128, fontSize, buf);
    if (cols == 0u)
        return;

    /* 8px / 16px 整格：每列领 2 tile（v8_alloc_tile）。 */
    for (col = 0; col < cols; col++) {
        uint16_t tile = v8_alloc_tile(win, (uint8_t)fontSize, 2u);
        if (tile == 0u)
            return;                           /* 无空闲：放弃 */
        chs_place_col(win, tile, 1u, buf[col * 2u], buf[col * 2u + 1u]);
        if (tm == 0u || tm == 1u)
            win_set_u16(win, WIN_TILE_OFFSET,
                        (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + 2u));
    }
}

/* =====================================================================
 * §V8 统一渲染入口（PrintNextChar / translater 消费端共调）：
 *   getFontSize 决策字号 → GetGlyph 解压 → chs_place 落址。
 * ===================================================================== */
void chs_print(TextPrinter *win, uint32_t code, uint8_t fontSize)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
    uint8_t fn = win_u8(win, WIN_FONTNUM_REAL);
    uint8_t g128[CHS_CELL_BYTES];
    uint8_t w = 0;

    if (fn > 6u)
        fn = 3u;

    /* 字号决策钩子（getFontSize）：font4/tm2→8，设置菜单 curX<8→16 否则12，其余12 */
    fontSize = get_font_size(win, fn, tm);

    if (!GetGlyph(win, code, g128, &w))
        return;
    chs_place(win, tm, fn, fontSize, g128);
}

/* =====================================================================
 * 半角 PCS 单字节渲染
 *   SYM 标点带（0x36-0x3E，tm0/tm3/tm1）→ 中文标点字库自绘一列 8px；
 *   其余半角（数字/拉丁/空格…）→ draw_jp_glyph（官方字库取字）。
 * 返回 1=已消费；0=未消费（交调用方原生分发）。
 * ===================================================================== */
int DrawHalfWidth(TextPrinter *win, uint32_t cur_char)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;

    if (cur_char >= SYM_GLYPH_BASE
        && cur_char < SYM_GLYPH_BASE + SYM_GLYPH_COUNT) {
        const uint8_t *sym =
            (const uint8_t *)ADDR_FONT_CHS_SYM + (cur_char - SYM_GLYPH_BASE) * 64u;
        uint8_t g128[CHS_CELL_BYTES];
        unsigned i;

        if (tm != 0u && tm != 3u && tm != 1u)
            return 0;
        for (i = 0; i < CHS_CELL_BYTES; i++)
            g128[i] = 0u;
        for (i = 0; i < 32u; i++) {
            g128[0x00 + i] = sym[i];
            g128[0x20 + i] = sym[32u + i];
        }
#if CHS_ADVANCE_12
        {
            /* 标点 8px 也走相位（ink=8 不改变 phase，但 phase!=0 时须跨列共享） */
            unsigned adv = print_glyph_px(win, g128, 8u);
            if (tm == 0u || tm == 1u)
                win_set_u16(win, WIN_TILE_OFFSET,
                            (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + adv * 2u));
        }
#else
        chs_place(win, tm, 0u, 8u, g128);
#endif
        return 1;
    }

    return 0;
}

/* PCS 单字节渲染入口（translater 替换流内消费）。恒返回 1=已消费。 */
int DrawGlyph(TextPrinter *win, uint32_t cur_char)
{
    if (cur_char >= 0xF7u)
        return 1;
    if (!DrawHalfWidth(win, cur_char)) {
        uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
        if (!draw_jp_glyph(win, win_u8(win, WIN_FONTNUM_REAL), cur_char))
            FontFunc_NativeDispatch(tm, win, cur_char);
    }
    return 1;
}

/* =====================================================================
 * 原生 FontFunc 分发（直调 Origin 地址常量；严禁经 FontFuncTable）。
 * ===================================================================== */
void FontFunc_NativeDispatch(uint8_t tm, TextPrinter *win, uint32_t c)
{
    typedef void (*fontfunc_t)(TextPrinter *, uint32_t);
    fontfunc_t fn;

    switch (tm & 7u) {
    case 0:
        fn = (fontfunc_t)(ADDR_FONT_FUNC_TM0_ORIGIN | 1u);
        break;
    case 1:
        fn = (fontfunc_t)(ADDR_PRINT_GLYPH_TM1_ORIGIN | 1u);
        break;
    case 2:
        fn = (fontfunc_t)(ADDR_FONT_FUNC_TM2_ORIGIN | 1u);
        break;
    case 3:
        fn = (fontfunc_t)(ADDR_FONT_FUNC_TM3_ORIGIN | 1u);
        break;
    default:
        return;
    }
    fn(win, c);
}

/* =====================================================================
 * PrintNextChar 唯一 hook：读编码 → 译（translater）→ 半角/回落。
 *   FA..FF：完整交还官方（含 index 推进）。
 *   F9 汉字/短语/slot：TranslateHandleChar（内部经 chs_print 渲染）。
 *   半角：DrawHalfWidth；未消费则 draw_jp_glyph / 原生 FontFunc。
 * ===================================================================== */
int PrintNextChar_Hook(TextPrinter *win)
{
    const uint8_t *text;
    uint16_t idx;
    uint8_t c;

    if (!win)
        return 0;

    text = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    idx = win_u16(win, WIN_TEXT_INDEX);
    c = text[idx];

    if (c >= 0xFAu)
        return PrintNextChar_Origin(win);

    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx + 1u));

    if (*(volatile uint8_t *)ADDR_V6_BYPASS != 0u)
        return 1;

    if (TranslateHandleChar(win, c))
        return 1;
    if (c < 0xF7u && DrawHalfWidth(win, c))
        return 1;

    if (!draw_jp_glyph(win, win_u8(win, WIN_FONTNUM_REAL), c))
        FontFunc_NativeDispatch(win_u8(win, WIN_TEXTMODE), win, c);
    return 1;
}
