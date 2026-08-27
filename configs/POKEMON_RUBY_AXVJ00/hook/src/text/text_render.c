/* text_render.c — refpr + pitch + 日版 GetCursorTileNum（薄路径，无 scene 门控） */
#include "text_render.h"

#define CHS_GLYPH_HALF_BIT   0x8000u
#define CHS_GLYPH_IDX_MASK   0x7FFFu
#define CHS_FONT_GLYPH_MAX   7168
#define CHS_PITCH_SLOT_COUNT 8u
#define CHS_LAST_OFF_ADDR    0x0203FF82u

struct ChineseTileState {
    uint8_t  char_base;
    uint8_t  write_op;
    uint8_t  base_tx;
    uint8_t  last_adv;
    uint16_t pitch_key;
    uint16_t chs_px;
};

struct ChsPitchCtrl {
    uint8_t cur;
    uint8_t gen;
    uint8_t pad[2];
    uint8_t age[CHS_PITCH_SLOT_COUNT];
};

void copy_tile32(void *dst_vram, const void *src_iwram)
{
    const uint32_t *s = (const uint32_t *)src_iwram;
    uint32_t *d = (uint32_t *)dst_vram;

    d[0] = s[0];
    d[1] = s[1];
    d[2] = s[2];
    d[3] = s[3];
    d[4] = s[4];
    d[5] = s[5];
    d[6] = s[6];
    d[7] = s[7];
}

uint8_t *vram_tile(TextPrinter *win, uint16_t tile)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, 0x0C);

    return tile_data + ((uint32_t)tile << 5);
}

void DecompressGlyph_Chinese(struct TextGlyph *glyph, uint16_t ChineseChar, uint8_t fontId)
{
    const uint8_t *base;
    const uint8_t *g;

    if (ChineseChar >= CHS_FONT_GLYPH_MAX)
        ChineseChar = 0;

    base = (fontId == 4u) ? (const uint8_t *)ADDR_FONT_CHS_SMALL
                          : (const uint8_t *)ADDR_FONT_CHS_NORMAL;
    g = base + ((uint32_t)(ChineseChar & CHS_GLYPH_IDX_MASK) << 7);
    if (ChineseChar & CHS_GLYPH_HALF_BIT)
        g += 64u;

    copy_tile32(&glyph->gfxBufferTop[0], g + 0u);
    copy_tile32(&glyph->gfxBufferTop[8], g + 64u);
    copy_tile32(&glyph->gfxBufferBottom[0], g + 32u);
    copy_tile32(&glyph->gfxBufferBottom[8], g + 96u);

    glyph->width = GetChineseFontWidthFunc(ChineseChar, fontId);
    glyph->height = (fontId == 4u) ? 8u : 12u;
}

uint8_t GetChineseFontWidthFunc(uint16_t ChineseChar, uint8_t fontId)
{
    (void)ChineseChar;
    switch (fontId) {
    case 4u:
        return 8u;
    default:
        return 12u;
    }
}

static uint8_t pitch_capture_base_tx(TextPrinter *win)
{
    return win_u8(win, WIN_CURSOR_TILE_X);
}

static uint16_t chs_pitch_key(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint16_t w = tpl ? (uint16_t)(((uintptr_t)tpl >> 2) & 0xFFFFu) : 0;

    return (uint16_t)(win_u16(win, WIN_TILE_BASE)
                      ^ ((uint16_t)win_u8(win, WIN_CURSOR_Y) << 8)
                      ^ (uint16_t)win_u8(win, WIN_CURSOR_TILE_Y)
                      ^ w);
}

static volatile struct ChineseTileState *chs_bind_pitch_slot(TextPrinter *win, int *out_is_new)
{
    volatile struct ChsPitchCtrl *ctrl =
        (volatile struct ChsPitchCtrl *)ADDR_CHS_PITCH_CTRL;
    volatile struct ChineseTileState *slots =
        (volatile struct ChineseTileState *)ADDR_CHS_PITCH_SLOTS;
    uint8_t *tpl = win_template(win);
    uint8_t char_base = tpl ? tpl[1] : 0;
    uint16_t key = chs_pitch_key(win);
    unsigned i;
    unsigned best;
    uint8_t best_age;
    uint8_t gen;

    if (out_is_new)
        *out_is_new = 0;

    for (i = 0; i < CHS_PITCH_SLOT_COUNT; i++) {
        if (slots[i].pitch_key == key && slots[i].char_base == char_base) {
            gen = (uint8_t)(ctrl->gen + 1u);
            ctrl->gen = gen;
            ctrl->age[i] = gen;
            ctrl->cur = (uint8_t)i;
            return &slots[i];
        }
    }

    best = 0;
    best_age = 255;
    for (i = 0; i < CHS_PITCH_SLOT_COUNT; i++) {
        if (ctrl->age[i] == 0) {
            best = i;
            break;
        }
        if (ctrl->age[i] < best_age) {
            best_age = ctrl->age[i];
            best = i;
        }
    }

    slots[best].char_base = char_base;
    slots[best].write_op = 0;
    slots[best].base_tx = pitch_capture_base_tx(win);
    slots[best].last_adv = (uint8_t)CHS_GLYPH_ADVANCE_PX;
    slots[best].pitch_key = key;
    slots[best].chs_px = 0;
    gen = (uint8_t)(ctrl->gen + 1u);
    ctrl->gen = gen;
    ctrl->age[best] = gen;
    ctrl->cur = (uint8_t)best;
    if (out_is_new)
        *out_is_new = 1;
    return &slots[best];
}

static void pitch_reset(TextPrinter *win)
{
    volatile struct ChineseTileState *st = chs_bind_pitch_slot(win, 0);

    st->chs_px = 0;
    st->base_tx = pitch_capture_base_tx(win);
}

static int draw_use_linear(TextPrinter *win, uint8_t write_op)
{
    (void)write_op;
    if ((win_u8(win, WIN_TEXTMODE) & 7u) == 0u)
        return 1;
    if (win_u8(win, WIN_FONTNUM_REAL) == FONT_NORMAL_SHADOWED)
        return 0;
    return 1;
}

static void ensure_linear_dest_floor(TextPrinter *win)
{
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);

    if (off < 4u)
        win_set_u16(win, WIN_TILE_OFFSET, 4u);
}

static uint16_t GetCursorTileNum_Linear(TextPrinter *win, unsigned xOff, unsigned yOff)
{
    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);

    return (uint16_t)(tile_base + off + 2u * xOff + yOff);
}

static void GetCursorTileNum_Mode2(
    TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower)
{
    int x = (int)win_u8(win, WIN_CURSOR_X) + tile_x;
    int y = (int)win_u8(win, WIN_CURSOR_Y) + (int)win_u8(win, WIN_CURSOR_TILE_Y);
    uint32_t origin = 0;
    uint8_t *tpl = win_template(win);
    uint32_t idx;

    if (tpl && tpl[1] == 2u)
        origin = CHS_MODE2_ORIGIN_SHOP;
    idx = (uint32_t)(y * CHS_TILE_GRID_W + x);
    idx += win_u16(win, WIN_TILE_BASE);
    idx += origin;
    *upper = (uint16_t)idx;
    *lower = (uint16_t)(idx + CHS_TILE_GRID_W);
}

static void map_at(TextPrinter *win, uint8_t tx, uint16_t abs_u, uint16_t abs_l)
{
    win_set_u8(win, WIN_CURSOR_TILE_X, tx);
    UpdateTilemap_PreserveCursorX(win, abs_u, abs_l);
}

static uint8_t tile_get_px(const uint8_t *tile, unsigned x, unsigned y)
{
    unsigned bi = y * 4u + x / 2u;

    if (x & 1u)
        return (uint8_t)(tile[bi] & 0x0Fu);
    return (uint8_t)(tile[bi] >> 4);
}

static void tile_put_px(uint8_t *tile, unsigned x, unsigned y, uint8_t ink)
{
    unsigned bi = y * 4u + x / 2u;

    if (x & 1u)
        tile[bi] = (uint8_t)((tile[bi] & 0xF0u) | (ink & 0x0Fu));
    else
        tile[bi] = (uint8_t)((tile[bi] & 0x0Fu) | ((ink & 0x0Fu) << 4));
}

void DrawGlyphTile_refpr(
    TextPrinter *win, struct GlyphTileInfo *info,
    const uint8_t *src32, uint8_t *dest, uint8_t *spillTile)
{
    uint32_t temp_words[8];
    uint32_t dest_words[8];
    uint32_t spill_words[8];
    uint8_t *temp = (uint8_t *)temp_words;
    uint8_t *dest_l = (uint8_t *)dest_words;
    uint8_t *spill_l = (uint8_t *)spill_words;
    unsigned startPixel = info->startPixel;
    unsigned width = info->width;
    unsigned gw_end = startPixel + width;
    unsigned r, c;
    uint8_t fg_ov = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    uint8_t color_c = (fg_ov != 0u) ? fg_ov : win_u8(win, WIN_COLOR_C);
    uint8_t color_d = win_u8(win, WIN_COLOR_D);
    uint8_t color_e = win_u8(win, WIN_COLOR_E);
    int need_spill = (spillTile != 0) && (gw_end > 8u);

    /* CopyGlyph(C,E,D) + 清列盖字：与 bak DrawGlyphTile_CHS 同构，保缩进/相位 */
    CopyGlyph2bppTo4bpp_Origin(src32, temp, color_c, color_e, color_d);

    if (spillTile == 0 && startPixel == 0u && width == 8u) {
        copy_tile32(dest, temp);
        return;
    }

    {
        const uint32_t *dv = (const uint32_t *)dest;
        for (c = 0; c < 8u; c++)
            dest_words[c] = dv[c];
    }
    if (need_spill) {
        const uint32_t *sv = (const uint32_t *)spillTile;
        for (c = 0; c < 8u; c++)
            spill_words[c] = sv[c];
    }

    for (r = 0; r < 8u; r++) {
        for (c = startPixel; c < gw_end && c < 8u; c++)
            tile_put_px(dest_l, c, r, color_d);
        if (need_spill) {
            unsigned from = (startPixel > 8u) ? (startPixel - 8u) : 0u;
            unsigned to = gw_end - 8u;

            for (c = from; c < to && c < 8u; c++)
                tile_put_px(spill_l, c, r, color_d);
        }
        for (c = 0; c < width; c++) {
            unsigned dc = startPixel + c;

            if (dc < 8u)
                tile_put_px(dest_l, dc, r, tile_get_px(temp, c, r));
            else if (need_spill)
                tile_put_px(spill_l, dc - 8u, r, tile_get_px(temp, c, r));
        }
        if (gw_end < 8u) {
            for (c = gw_end; c < 8u; c++)
                tile_put_px(dest_l, c, r, color_d);
        }
        if (need_spill && gw_end > 8u) {
            for (c = gw_end - 8u; c < 8u; c++)
                tile_put_px(spill_l, c, r, color_d);
        }
    }

    copy_tile32(dest, dest_l);
    if (need_spill)
        copy_tile32(spillTile, spill_l);
}

unsigned GetGlyphWidthChinese(TextPrinter *win, uint32_t gidx_or_code, unsigned glyphWidth)
{
    (void)win;
    (void)gidx_or_code;
    if (glyphWidth <= 8u)
        return 0u;
    return glyphWidth - 8u;
}

static void DrawGlyphTiles_core(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, int linear,
    unsigned glyphWidth)
{
    volatile struct ChineseTileState *st = chs_bind_pitch_slot(win, 0);
    unsigned startPixel;
    unsigned pass2_w;
    uint16_t off, abs_u, abs_l, su, sl;
    uint8_t *du, *dl, *du_sp, *dl_sp;
    uint8_t map_tx;
    int spilled;
    struct GlyphTileInfo info;

    if (glyphWidth < 8u)
        glyphWidth = 8u;
    if (glyphWidth > 12u)
        glyphWidth = 12u;
    pass2_w = glyphWidth - 8u;
    spilled = 0;

    if (st->chs_px == 0)
        st->base_tx = pitch_capture_base_tx(win);

    startPixel = (unsigned)(st->chs_px & 7u);
    map_tx = (uint8_t)(st->base_tx + (st->chs_px >> 3));
    info.startPixel = (uint8_t)startPixel;
    info.width = 8;

    if (linear) {
        if (st->chs_px == 0)
            ensure_linear_dest_floor(win);
        off = win_u16(win, WIN_TILE_OFFSET);
        abs_u = GetCursorTileNum_Linear(win, 0, 0);
        abs_l = GetCursorTileNum_Linear(win, 0, 1);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + 8u > 8u) {
            su = GetCursorTileNum_Linear(win, 1, 0);
            sl = GetCursorTileNum_Linear(win, 1, 1);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
            spilled = 1;
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        DrawGlyphTile_refpr(win, &info, tiles->tl, du, du_sp);
        DrawGlyphTile_refpr(win, &info, tiles->bl, dl, dl_sp);
        map_at(win, map_tx, abs_u, abs_l);
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
    } else {
        GetCursorTileNum_Mode2(win, (int)map_tx, &abs_u, &abs_l);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + 8u > 8u) {
            GetCursorTileNum_Mode2(win, (int)map_tx + 1, &su, &sl);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
            spilled = 1;
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        DrawGlyphTile_refpr(win, &info, tiles->tl, du, du_sp);
        DrawGlyphTile_refpr(win, &info, tiles->bl, dl, dl_sp);
        map_at(win, map_tx, abs_u, abs_l);
    }

    st->chs_px = (uint16_t)(st->chs_px + 8u);
    if (pass2_w == 0u) {
        if (spilled)
            map_at(win, (uint8_t)(map_tx + 1u), su, sl);
        st->last_adv = (uint8_t)glyphWidth;
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(st->base_tx + ((st->chs_px + glyphWidth - 1) >> 3)));
        return;
    }

    map_tx = (uint8_t)(st->base_tx + (st->chs_px >> 3));
    info.width = (uint8_t)pass2_w;

    if (linear) {
        off = win_u16(win, WIN_TILE_OFFSET);
        abs_u = GetCursorTileNum_Linear(win, 0, 0);
        abs_l = GetCursorTileNum_Linear(win, 0, 1);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + pass2_w > 8u) {
            su = GetCursorTileNum_Linear(win, 1, 0);
            sl = GetCursorTileNum_Linear(win, 1, 1);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        DrawGlyphTile_refpr(win, &info, tiles->tr, du, du_sp);
        DrawGlyphTile_refpr(win, &info, tiles->br, dl, dl_sp);
        map_at(win, map_tx, abs_u, abs_l);
        win_set_u16(win, WIN_TILE_OFFSET,
                    (uint16_t)(off + (startPixel == 0u ? 0u : 2u)));
    } else {
        GetCursorTileNum_Mode2(win, (int)map_tx, &abs_u, &abs_l);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + pass2_w > 8u) {
            GetCursorTileNum_Mode2(win, (int)map_tx + 1, &su, &sl);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        DrawGlyphTile_refpr(win, &info, tiles->tr, du, du_sp);
        DrawGlyphTile_refpr(win, &info, tiles->br, dl, dl_sp);
        map_at(win, map_tx, abs_u, abs_l);
    }

    st->chs_px = (uint16_t)(st->chs_px + pass2_w);
    st->last_adv = (uint8_t)glyphWidth;
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(st->base_tx + ((st->chs_px + glyphWidth - 1) >> 3)));
}

static void DrawGlyphTiles_common(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    int slot_new = 0;
    volatile struct ChineseTileState *st = chs_bind_pitch_slot(win, &slot_new);
    uint8_t cur_tx = win_u8(win, WIN_CURSOR_TILE_X);
    unsigned last;
    int linear;
    int newline_reset = 0;

    if (slot_new && st->chs_px == 0)
        newline_reset = 1;

    if (st->chs_px != 0 && cur_tx <= st->base_tx) {
        st->chs_px = 0;
        st->base_tx = pitch_capture_base_tx(win);
        newline_reset = 1;
    } else if (st->chs_px != 0) {
        last = st->last_adv ? st->last_adv : (unsigned)CHS_GLYPH_ADVANCE_PX;
        {
            uint8_t expect = (uint8_t)(st->base_tx + ((st->chs_px + last - 1) >> 3));

            if (cur_tx != expect) {
                st->chs_px = 0;
                st->base_tx = pitch_capture_base_tx(win);
                newline_reset = 1;
            }
        }
    } else {
        st->base_tx = pitch_capture_base_tx(win);
    }

    linear = draw_use_linear(win, st->write_op);

    if (linear && st->chs_px != 0u) {
        uint16_t off_now = win_u16(win, WIN_TILE_OFFSET);
        uint16_t off_last = *(volatile uint16_t *)CHS_LAST_OFF_ADDR;

        if (off_last != 0u && off_now < off_last)
            win_set_u16(win, WIN_TILE_OFFSET, off_last);
    }

    if (newline_reset && linear) {
        uint16_t off = win_u16(win, WIN_TILE_OFFSET);

        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
    }

    DrawGlyphTiles_core(win, tiles, linear, glyphWidth);

    if (linear)
        *(volatile uint16_t *)CHS_LAST_OFF_ADDR = win_u16(win, WIN_TILE_OFFSET);
}

void DrawGlyphTiles(TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    uint8_t tm;

    if (!win || !tiles)
        return;

    tm = win_u8(win, WIN_TEXTMODE) & 7u;
    switch (tm) {
    case 0:
    case 1:
    case 3:
        DrawGlyphTiles_common(win, tiles, glyphWidth);
        break;
    default:
        break;
    }
}

void DrawGlyphTiles_arrow_prepare(TextPrinter *win)
{
    volatile struct ChineseTileState *st;
    uint16_t cols;
    uint16_t off;
    uint8_t want;
    uint8_t cur_tx;

    if (!win)
        return;
    st = chs_bind_pitch_slot(win, 0);
    if (!st->chs_px)
        return;

    cols = (uint16_t)((st->chs_px + 7u) >> 3);
    want = (uint8_t)(st->base_tx + cols);
    cur_tx = win_u8(win, WIN_CURSOR_TILE_X);

    if (cur_tx == 0u && want > 0u) {
        off = win_u16(win, WIN_TILE_OFFSET);
        if (st->chs_px & 7u)
            win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
        pitch_reset(win);
        return;
    }

    win_set_u8(win, WIN_CURSOR_TILE_X, want);
    off = win_u16(win, WIN_TILE_OFFSET);
    if (st->chs_px & 7u)
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
    pitch_reset(win);
}

void arrow_inplace12(TextPrinter *win)
{
    DrawGlyphTiles_arrow_prepare(win);
}
