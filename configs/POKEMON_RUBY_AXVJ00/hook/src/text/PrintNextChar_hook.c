/* =====================================================================================
 * PrintNextChar_hook.c — 渲染落点（翻译通路消费端）
 *
 * 统一模型（2026-09-04）：
 *   1) 非 FA..FF → TranslateHandleChar / DrawGlyph（翻译通路）
 *   2) resolve(tm, fn) → font_px：fn4 / tm2 → 强制 8px；场景表 / 默认 12
 *   3) 取字 → g128 → chs_emit：按 tm 落点
 *        tm2     写 win[0x20] 缓冲，列步进 +0x40（官方血条再 CpuSet→OBJ）
 *        tm0/tm1 v8_alloc + UTM，并 TILE_OFFSET += adv*2
 *        tm3     v8_alloc + UTM，不推 TILE_OFFSET（网格只推 cursorTileX）
 *   tm1 是分配器的主因（预渲染窗无自写 VRAM）；tm0/tm3 中文叠字同样领号避 atlas。
 * ===================================================================================== */
#include "text.h"
#include "blend_glyph.h"
#include "scene_cfg.h"
#include "tile_alloc.h"

/* ---- 场景字号表（scene_cfg）---- */
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

/* ---- resolve：tm + fn → font_px ---- */
static void resolve_draw(TextPrinter *win, uint8_t *tm_out, uint8_t *fn_out,
                         uint8_t *font_px_out)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
    uint8_t fn = win_u8(win, WIN_FONTNUM_REAL);
    const struct V6SceneRule *rule;

    if (fn > 6u)
        fn = 3u;
    /* 血条 tm2 与官方模板一致：按 font4 取阴影小字 */
    if (tm == 2u)
        fn = 4u;

    *tm_out = tm;
    *fn_out = fn;

    if (fn == 4u || tm == 2u) {
        *font_px_out = 8u;
        return;
    }
    rule = v6_scene_lookup((uint32_t)(uintptr_t)win_template(win));
    if (rule)
        *font_px_out = v6_scene_font(rule, win_u8(win, WIN_CURSOR_X));
    else
        *font_px_out = 12u;
}

/* ---- Stage2：字模 → 列对（8/16）；12px 由相位路径 extract_cols ---- */
static unsigned chs_rasterize(const uint8_t g128[CHS_CELL_BYTES],
                              unsigned fontSize, uint8_t out[4][32])
{
    unsigned i;

    if (fontSize == 8u) {
        for (i = 0; i < 32u; i++) {
            out[0][i] = g128[0x00 + i];
            out[1][i] = g128[0x20 + i];
        }
        return 1u;
    }
    if (fontSize == 16u) {
        for (i = 0; i < 32u; i++) {
            out[0][i] = g128[0x00 + i];
            out[1][i] = g128[0x20 + i];
            out[2][i] = g128[0x40 + i];
            out[3][i] = g128[0x60 + i];
        }
        return 2u;
    }
    return 0u;
}

static void fill_colors(TextPrinter *win, uint8_t colors[16])
{
    uint8_t fg_ov = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    uint8_t color_c = fg_ov ? fg_ov : win_u8(win, WIN_COLOR_C);
    uint8_t color_d = win_u8(win, WIN_COLOR_D);
    uint8_t color_e = win_u8(win, WIN_COLOR_E);
    unsigned i;

    for (i = 0; i < 16u; i++)
        colors[i] = color_d;
    colors[14] = color_e;
    colors[15] = color_c;
}

/* 单列写入：tm2→缓冲；其余→ tile_data[tile] + UTM */
static void chs_place_col(TextPrinter *win, uint8_t tm, uint16_t tile,
                          uint16_t lower_delta,
                          const uint8_t *src_u, const uint8_t *src_l)
{
    uint8_t colors[16];

    fill_colors(win, colors);

    if (tm == 2u) {
        uint32_t dst = win_u32(win, WIN_TILE_DATA);
        if (dst == 0u)
            return;
        blend_glyph_4bpp((uint32_t *)(void *)dst, 0, src_u, 8u, 0u, colors);
        blend_glyph_4bpp((uint32_t *)(void *)(dst + 0x20u), 0, src_l, 8u, 0u,
                         colors);
        win_set_u32(win, WIN_TILE_DATA, dst + 0x40u);
        return;
    }

    {
        uint8_t *tpl = win_template(win);
        uint8_t *tile_data;
        uint16_t lower = (uint16_t)(tile + lower_delta);

        if (!tpl)
            return;
        tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
        if (!tile_data || tile == 0u)
            return;
        blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)tile << 5)),
                         0, src_u, 8u, 0u, colors);
        blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)lower << 5)),
                         0, src_l, 8u, 0u, colors);
        UpdateTilemap_PreserveCursorX(win, tile, lower);
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
    }
}

#if CHS_ADVANCE_12

static void chs_fill_bg(TextPrinter *win, uint16_t tile, unsigned x0, unsigned x1)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
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
    fill_colors(win, colors);
    for (i = 0; i < 32u; i++)
        zero[i] = 0u;
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)tile << 5)),
                           0, zero, x1 - x0, x0, colors);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(tile + 1u) << 5)),
                           0, zero, x1 - x0, x0, colors);
}

/* 12px（及相位上的 8px 标点）：两段式 + v8 领号；返回 adv 列数 */
static unsigned print_glyph_px(TextPrinter *win,
                               const uint8_t g128[CHS_CELL_BYTES],
                               unsigned ink)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
    uint8_t colors[16];
    uint8_t up[32], lo[32];
    unsigned px, phase, w0, w1, adv;
    uint16_t t0, t1;
    uint8_t tx0;

    v8_phase_before_glyph(win);

    px = v8_phase_get(win);
    phase = px & 7u;
    w0 = (8u - phase < ink) ? (8u - phase) : ink;
    w1 = ink - w0;
    adv = (phase + ink) / 8u;
    tx0 = win_u8(win, WIN_CURSOR_TILE_X);
    if (adv < 1u)
        adv = 1u;
    if (!tpl)
        return adv;
    tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!tile_data)
        return adv;

    fill_colors(win, colors);

    if (phase == 0u) {
        t0 = v8_alloc_tile(win, 12u, 2u);
        if (t0 == 0u)
            return adv;
    } else {
        t0 = v8_phase_last_tile();
    }
    t1 = (w1 != 0u) ? v8_alloc_tile(win, 12u, 2u) : 0u;

    extract_cols(g128, 0u, w0, up, lo);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)t0 << 5)),
                           0, up, w0, phase, colors);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(t0 + 1u) << 5)),
                           0, lo, w0, phase, colors);

    if (w1 != 0u) {
        extract_cols(g128, w0, w1, up, lo);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)t1 << 5)),
                               0, up, w1, 0u, colors);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(t1 + 1u) << 5)),
                               0, lo, w1, 0u, colors);
        chs_fill_bg(win, t1, w1, 8u);
    }

    UpdateTilemap_PreserveCursorX(win, t0, (uint16_t)(t0 + 1u));
    if (w1 != 0u) {
        win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(tx0 + 1u));
        UpdateTilemap_PreserveCursorX(win, t1, (uint16_t)(t1 + 1u));
    }
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(tx0 + adv));

    v8_phase_advance((uint16_t)ink);
    v8_phase_set_last_tile((w1 != 0u) ? t1 : t0);
    v8_phase_after_glyph(win);
    return adv;
}

#endif /* CHS_ADVANCE_12 */

/* ---- 唯一落点：按 tm 写目标；返回推进列数（供 TILE_OFFSET）---- */
static unsigned chs_emit(TextPrinter *win, uint8_t tm, unsigned font_px,
                         const uint8_t g128[CHS_CELL_BYTES], unsigned ink)
{
    uint8_t buf[4][32];
    unsigned cols, col, adv = 1u;

    if (tm == 2u)
        font_px = 8u;
    if (ink == 0u)
        ink = font_px;

#if CHS_ADVANCE_12
    /* tm2 无相位；12px 汉字与 8px 标点/半角走两段式（含奇数位换行清理） */
    if (tm != 2u && ink != 16u && (ink == 12u || ink == 8u)) {
        adv = print_glyph_px(win, g128, ink);
        if (tm == 0u || tm == 1u)
            win_set_u16(win, WIN_TILE_OFFSET,
                        (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + adv * 2u));
        return adv;
    }
#endif

    cols = chs_rasterize(g128, (tm == 2u || font_px == 8u) ? 8u : font_px, buf);
    if (cols == 0u)
        return 0u;

    for (col = 0; col < cols; col++) {
        uint16_t tile = 1u;
        if (tm != 2u) {
            tile = v8_alloc_tile(win, (uint8_t)font_px, 2u);
            if (tile == 0u)
                return col;
        }
        chs_place_col(win, tm, tile, 1u, buf[col * 2u], buf[col * 2u + 1u]);
        if (tm == 0u || tm == 1u)
            win_set_u16(win, WIN_TILE_OFFSET,
                        (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + 2u));
    }
    return cols;
}

static void jp_glyph_to_g128(uint8_t font_num, uint16_t glyph,
                             uint8_t g128[CHS_CELL_BYTES])
{
    uint8_t *up, *lo;
    unsigned i;

    GetGlyphTilePointers_Origin(font_num, glyph, &up, &lo);
    for (i = 0; i < CHS_CELL_BYTES; i++)
        g128[i] = 0u;
    if (FontIsShadowed(font_num)) {
        copy_tile32(g128 + 0x00u, up);
        copy_tile32(g128 + 0x20u, lo);
    } else {
        CopyGlyph1bppTo4bpp_Origin(up, g128 + 0x00u, 15u, 0u);
        CopyGlyph1bppTo4bpp_Origin(lo, g128 + 0x20u, 15u, 0u);
    }
}

void chs_print(TextPrinter *win, uint32_t code, uint8_t fontSize)
{
    uint8_t tm, fn, font_px;
    uint8_t g128[CHS_CELL_BYTES];
    uint8_t w = 0;
    uint8_t saved_fn;

    (void)fontSize;
    resolve_draw(win, &tm, &fn, &font_px);

    saved_fn = win_u8(win, WIN_FONTNUM_REAL);
    win_set_u8(win, WIN_FONTNUM_REAL, fn);
    if (!GetGlyph(win, code, g128, &w)) {
        win_set_u8(win, WIN_FONTNUM_REAL, saved_fn);
        return;
    }
    win_set_u8(win, WIN_FONTNUM_REAL, saved_fn);
    (void)chs_emit(win, tm, font_px, g128, font_px);
}

int DrawHalfWidth(TextPrinter *win, uint32_t cur_char)
{
    uint8_t tm, fn, font_px;
    uint8_t g128[CHS_CELL_BYTES];
    unsigned i;

    if (cur_char < SYM_GLYPH_BASE
        || cur_char >= SYM_GLYPH_BASE + SYM_GLYPH_COUNT)
        return 0;

    resolve_draw(win, &tm, &fn, &font_px);
    (void)fn;
    (void)font_px;

    {
        const uint8_t *sym =
            (const uint8_t *)ADDR_FONT_CHS_SYM
            + (cur_char - SYM_GLYPH_BASE) * 64u;
        for (i = 0; i < CHS_CELL_BYTES; i++)
            g128[i] = 0u;
        for (i = 0; i < 32u; i++) {
            g128[0x00 + i] = sym[i];
            g128[0x20 + i] = sym[32u + i];
        }
    }
    (void)chs_emit(win, tm, 8u, g128, 8u);
    return 1;
}

int DrawGlyph(TextPrinter *win, uint32_t cur_char)
{
    uint8_t tm, fn, font_px;
    uint8_t g128[CHS_CELL_BYTES];

    if (cur_char >= 0xF7u)
        return 1;
    if (DrawHalfWidth(win, cur_char))
        return 1;

    resolve_draw(win, &tm, &fn, &font_px);
    jp_glyph_to_g128(fn, (uint16_t)cur_char, g128);
    /* 半角 JP：墨宽 8；落点仍按 resolve 的 font_px/tm */
    (void)chs_emit(win, tm, font_px, g128, CHS_GLYPH_ADVANCE_JP_PX);
    return 1;
}

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

    /* FA..FF：Origin 尾调用进 ROM，返回后本函数后续语句不会执行 */
    if (c >= 0xFAu)
        return PrintNextChar_Origin(win);

    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx + 1u));

    if (*(volatile uint8_t *)ADDR_V6_BYPASS != 0u)
        return 1;

    if (TranslateHandleChar(win, c))
        return 1;
    DrawGlyph(win, c);
    return 1;
}
