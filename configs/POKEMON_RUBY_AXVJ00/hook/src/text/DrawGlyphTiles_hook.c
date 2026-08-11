/* DrawGlyphTiles_hook — pokeRS DrawGlyphTilesChinese algorithm for AXVJ.
 *
 * ROM glyph = 128B 4bpp TL,BL,TR,BR (Font_Patch / pokeRS layout).
 * Advance = CHS_GLYPH_ADVANCE_PX (12) via Font_Patch 8+4.
 *
 * Color via JP CopyGlyph2bppTo4bpp (IWRAM scratch → CpuSet).
 * NEVER byte-store into VRAM (GBA mirrors both bytes of a halfword → 重影).
 * Compose in IWRAM, then copy_tile32 to VRAM.
 * Linear floor: field 0x100 / shop_desc 0x228. Mode2: MENU_BAND only left≥20 & y≥13.
 */
#include "game.h"

static void copy_tile32(void *dst_vram, const void *src_iwram)
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

static uint8_t pitch_capture_base_tx(TextPrinter *win)
{
    return win_u8(win, WIN_CURSOR_TILE_X);
}

/*
 * SoftKeyboard / party / shop share one CHS tile pool (JP PCS must stay here).
 * Isolate pitch+write_op per printer fingerprint so switching windows does not
 * clobber another printer's chs_px (title glyph paste into keyboard rows).
 */
volatile struct ChineseTileState *chs_bind_pitch_slot(TextPrinter *win)
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
    return &slots[best];
}

static void pitch_reset(TextPrinter *win)
{
    volatile struct ChineseTileState *st = chs_bind_pitch_slot(win);
    st->chs_px = 0;
    st->base_tx = pitch_capture_base_tx(win);
}

void Chinese_PitchReset(TextPrinter *win)
{
    pitch_reset(win);
}

static uint8_t *vram_tile(TextPrinter *win, uint16_t tile)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, 0x0C);
    return tile_data + ((uint32_t)tile << 5);
}

/* Remap abs tile out of reserved UI bands. Mode2 + Linear. */
static uint16_t avoid_dex_ui_tile(uint16_t tile)
{
    /* ▶ pair only — wrap into Linear pool (never 0x1D0; that broke summary). */
    if (tile >= CHS_MENU_CURSOR_TILE && tile <= CHS_MENU_CURSOR_TILE_HI)
        return (uint16_t)(CHS_MENU_CURSOR_TILE_ALT
                          + (tile - CHS_MENU_CURSOR_TILE));
    if (tile >= CHS_UI_ICON_TILE_LO && tile <= CHS_UI_ICON_TILE_HI)
        return (uint16_t)(CHS_UI_ICON_TILE_ALT + (tile - CHS_UI_ICON_TILE_LO));
    return tile;
}

/* Field Linear @ 0x100 / shop_desc @ 0x228 — see configs/docs/CHS_TILE_LAYOUT.md */
static void ensure_linear_dest_floor(TextPrinter *win)
{
    uint8_t *tpl;
    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    uint16_t floor;

    if (tile_base >= CHS_BATTLE_FIXED_BASE)
        return;

    tpl = win_template(win);
    if (scene_is_party_footer(win))
        floor = CHS_PARTY_FOOTER_LINEAR_FLOOR;
    else if (scene_is_shop_bag_list(win))
        floor = CHS_SHOP_LIST_LINEAR_FLOOR;
    else if (scene_is_shop_desc(win))
        floor = CHS_SHOP_DESC_LINEAR_FLOOR;
    else if (tpl && tpl[1] == 2)
        floor = CHS_MENU_LINEAR_FLOOR;
    else
        floor = 4;

    if (off < floor)
        win_set_u16(win, WIN_TILE_OFFSET, floor);
}

static uint16_t linear_cursor_tile(TextPrinter *win, unsigned x_off, unsigned y_off)
{
    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    return avoid_dex_ui_tile(
        (uint16_t)(tile_base + off + 2u * x_off + y_off));
}

static void compute_mode2_pair(
    TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower)
{
    int x = (int)win_u8(win, WIN_CURSOR_X) + tile_x;
    int y = (int)win_u8(win, WIN_CURSOR_Y) + (int)win_u8(win, WIN_CURSOR_TILE_Y);
    int band = 0;
    int origin = CHS_MODE2_ORIGIN_SHOP;
    uint8_t *tpl = win_template(win);

    if (!tpl || tpl[1] != 2)
        origin = 0;
    scene_mode2_apply(win, &x, &y, &band, &origin);
    {
        uint32_t idx = (uint32_t)(y * CHS_TILE_GRID_W + x + band);
        idx += win_u16(win, WIN_TILE_BASE);
        idx += (uint32_t)origin;
        *upper = avoid_dex_ui_tile((uint16_t)idx);
        *lower = avoid_dex_ui_tile((uint16_t)(idx + CHS_TILE_GRID_W));
    }
}

static uint8_t get_px(const uint8_t *tile, unsigned x, unsigned y)
{
    unsigned bi = y * 4u + x / 2u;
    if (x & 1u)
        return (uint8_t)(tile[bi] & 0x0Fu);
    return (uint8_t)(tile[bi] >> 4);
}

static void put_px(uint8_t *tile, unsigned x, unsigned y, uint8_t ink)
{
    unsigned bi = y * 4u + x / 2u;
    if (x & 1u)
        tile[bi] = (uint8_t)((tile[bi] & 0xF0u) | (ink & 0x0Fu));
    else
        tile[bi] = (uint8_t)((tile[bi] & 0x0Fu) | ((ink & 0x0Fu) << 4));
}

/*
 * Remap via ROM CopyGlyph (15→C ink, 14→E shadow, 0→D bg) then place at startPixel.
 * All pixel work stays in IWRAM; VRAM only receives 32-bit word copies.
 *
 * GBA VRAM 禁止 byte 写入（会 mirror 到半字另一字节导致鬼影）。
 * 所有像素合成在栈上 IWRAM（temp/dest_l/spill_l）完成，最后通过
 * copy_tile32 以 8 次 32-bit word copy 刷入 VRAM。
 *
 * spill 机制：当 startPixel + width > 8 时（因 12px advance 必然
 * 跨 tile 列），need_spill=1，同时处理当前 tile 和下一 tile 的
 * IWRAM 副本。清像素列 → OR 墨水 → 两 tile 分别写回 VRAM。
 */
static void draw_glyph_tile_12(
    TextPrinter *win,
    uint8_t *dest, uint8_t *spill, const uint8_t src32[32],
    unsigned startPixel, unsigned width)
{
    uint32_t temp_words[8];
    uint32_t dest_words[8];
    uint32_t spill_words[8];
    uint8_t *temp = (uint8_t *)temp_words;
    uint8_t *dest_l = (uint8_t *)dest_words;
    uint8_t *spill_l = (uint8_t *)spill_words;
    unsigned r, c;
    unsigned gw_end = startPixel + width;
    uint8_t color_c = win_u8(win, WIN_COLOR_C);
    uint8_t color_d = win_u8(win, WIN_COLOR_D);
    uint8_t color_e = win_u8(win, WIN_COLOR_E);
    int need_spill = (spill != 0) && (gw_end > 8u);

    /* CopyGlyph(C,E,D): 15→ink, 14→shadow, 0→bg. Unshadow font has no 14. */
    chs_copy_glyph_2bpp_to_4bpp(src32, temp, color_c, color_e, color_d);

    /* Fast path: full 8px column, tile-aligned — CopyGlyph buffer → VRAM. */
    if (spill == 0 && startPixel == 0u && width == 8u) {
        copy_tile32(dest, temp);
        return;
    }

    /* Seed from existing VRAM (16-bit-safe read via words) when OR-shifting. */
    {
        const uint32_t *dv = (const uint32_t *)dest;
        for (c = 0; c < 8u; c++)
            dest_words[c] = dv[c];
    }
    if (need_spill) {
        const uint32_t *sv = (const uint32_t *)spill;
        for (c = 0; c < 8u; c++)
            spill_words[c] = sv[c];
    }

    /* Clear only the columns we own, then stamp ink (IWRAM only). */
    for (r = 0; r < 8; r++) {
        for (c = startPixel; c < gw_end && c < 8u; c++)
            put_px(dest_l, c, r, color_d);
        if (need_spill) {
            unsigned from = (startPixel > 8u) ? (startPixel - 8u) : 0u;
            unsigned to = gw_end - 8u;
            for (c = from; c < to && c < 8u; c++)
                put_px(spill_l, c, r, color_d);
        }
        for (c = 0; c < width; c++) {
            unsigned dc = startPixel + c;
            if (dc < 8u)
                put_px(dest_l, dc, r, get_px(temp, c, r));
            else if (need_spill)
                put_px(spill_l, dc - 8u, r, get_px(temp, c, r));
        }
        if (gw_end < 8u) {
            for (c = gw_end; c < 8u; c++)
                put_px(dest_l, c, r, color_d);
        }
        if (need_spill && gw_end > 8u) {
            for (c = gw_end - 8u; c < 8u; c++)
                put_px(spill_l, c, r, color_d);
        }
    }

    copy_tile32(dest, dest_l);
    if (need_spill)
        copy_tile32(spill, spill_l);
}

static void map_at(TextPrinter *win, uint8_t tx, uint16_t abs_u, uint16_t abs_l)
{
    win_set_u8(win, WIN_CURSOR_TILE_X, tx);
    chs_update_tilemap(win, abs_u, abs_l);
}

void drawGlyph12(TextPrinter *win, const uint8_t *src128, int linear)
{
    drawGlyph_Adv(win, src128, linear, CHS_GLYPH_ADVANCE_PX);
}

void drawGlyph_Adv(TextPrinter *win, const uint8_t *src128, int linear, unsigned adv_px)
{
    /*
     * 16px 字模 → adv_px advance（默认 12=8+4；JP via CHS 为 8=仅左半）。
     * 推进由 chs_px 累积；Mode2/Linear 落点与中文共用。
     */
    volatile struct ChineseTileState *st = chs_bind_pitch_slot(win);
    unsigned startPixel;
    unsigned pass2_w;
    uint16_t off, abs_u, abs_l, su, sl;
    uint8_t *du, *dl, *du_sp, *dl_sp;
    uint8_t map_tx;
    int spilled;

    if (adv_px < 8u)
        adv_px = 8u;
    if (adv_px > 12u)
        adv_px = 12u;
    pass2_w = adv_px - 8u;
    spilled = 0;
    su = 0;
    sl = 0;

    if (st->chs_px == 0)
        st->base_tx = pitch_capture_base_tx(win);

    startPixel = (unsigned)(st->chs_px & 7u);
    map_tx = (uint8_t)(st->base_tx + (st->chs_px >> 3));

    /* ---- pass width 8: TL + BL ---- */
    if (linear) {
        if (st->chs_px == 0)
            ensure_linear_dest_floor(win);
        off = win_u16(win, WIN_TILE_OFFSET);
        abs_u = linear_cursor_tile(win, 0, 0);
        abs_l = linear_cursor_tile(win, 0, 1);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + 8u > 8u) {
            su = linear_cursor_tile(win, 1, 0);
            sl = linear_cursor_tile(win, 1, 1);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
            spilled = 1;
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        draw_glyph_tile_12(win, du, du_sp, src128 + 0x00, startPixel, 8);
        draw_glyph_tile_12(win, dl, dl_sp, src128 + 0x20, startPixel, 8);
        map_at(win, map_tx, abs_u, abs_l);
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
    } else {
        compute_mode2_pair(win, (int)map_tx, &abs_u, &abs_l);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + 8u > 8u) {
            compute_mode2_pair(win, (int)map_tx + 1, &su, &sl);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
            spilled = 1;
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        draw_glyph_tile_12(win, du, du_sp, src128 + 0x00, startPixel, 8);
        draw_glyph_tile_12(win, dl, dl_sp, src128 + 0x20, startPixel, 8);
        map_at(win, map_tx, abs_u, abs_l);
    }

    st->chs_px = (uint16_t)(st->chs_px + 8u);
    if (pass2_w == 0u) {
        /* Sym punct adv=8 at phase 4: right half lands in next tile via spill.
         * Hanzi adv=12 maps that tile in pass2; here pass2 is skipped — if we
         * omit map_at, line-final 。 is a crescent (mid-line OK: next Hanzi maps it). */
        if (spilled)
            map_at(win, (uint8_t)(map_tx + 1u), su, sl);
        st->last_adv = (uint8_t)adv_px;
        win_set_u8(win, WIN_CURSOR_TILE_X,
            (uint8_t)(st->base_tx + ((st->chs_px + adv_px - 1) >> 3)));
        /* Do NOT advance WIN_CURSOR_X here. Pitch uses chs_px; Mode2 is
         * CURSOR_X+tile_x. Syncing CURSOR_X (even Linear-only) desyncs
         * TILE_X vs chs_px → pitch_reset every glyph (scattered text). */
        return;
    }

    map_tx = (uint8_t)(st->base_tx + (st->chs_px >> 3));

    /* ---- pass width pass2_w: TR + BR ---- */
    if (linear) {
        off = win_u16(win, WIN_TILE_OFFSET);
        abs_u = linear_cursor_tile(win, 0, 0);
        abs_l = linear_cursor_tile(win, 0, 1);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + pass2_w > 8u) {
            su = linear_cursor_tile(win, 1, 0);
            sl = linear_cursor_tile(win, 1, 1);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        draw_glyph_tile_12(win, du, du_sp, src128 + 0x40, startPixel, pass2_w);
        draw_glyph_tile_12(win, dl, dl_sp, src128 + 0x60, startPixel, pass2_w);
        map_at(win, map_tx, abs_u, abs_l);
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + (startPixel == 0u ? 0u : 2u)));
    } else {
        compute_mode2_pair(win, (int)map_tx, &abs_u, &abs_l);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + pass2_w > 8u) {
            compute_mode2_pair(win, (int)map_tx + 1, &su, &sl);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        draw_glyph_tile_12(win, du, du_sp, src128 + 0x40, startPixel, pass2_w);
        draw_glyph_tile_12(win, dl, dl_sp, src128 + 0x60, startPixel, pass2_w);
        map_at(win, map_tx, abs_u, abs_l);
    }

    st->chs_px = (uint16_t)(st->chs_px + pass2_w);
    st->last_adv = (uint8_t)adv_px;
    win_set_u8(win, WIN_CURSOR_TILE_X,
        (uint8_t)(st->base_tx + ((st->chs_px + adv_px - 1) >> 3)));
}

int DrawGlyph_ShouldUseLinear(TextPrinter *win, uint8_t write_op)
{
    /*
     * Align with pokeruby Font3 + pokeRS GetCursorTileNum: SoftKeyboard/title
     * use Mode2 (y*30+x) so rows do not share Linear tiles ~4 with the title.
     * Shop list/desc keep Linear; battle fixed base stays Linear.
     * JP PCS still draws via CHS — only the tile index formula changes.
     */
    if (scene_battle_force_linear(win))
        return 1;
    if (scene_is_shop_desc(win) || scene_is_shop_bag_list(win))
        return 1;
    (void)write_op;
    if (scene_menu_wants_mode2(win))
        return 0;
    /* Other Font3 (should be rare): still Mode2 like vanilla Font3. */
    if (win_u8(win, WIN_FONTNUM_REAL) == FONT_NORMAL_SHADOWED)
        return 0;
    return 1;
}

/* InitMenu ▶: blit JP glyph into CHS_MENU_CURSOR_TILE; map cursor cell only. */
int DrawMenuCursorEF(TextPrinter *win)
{
    uint8_t *upper = 0;
    uint8_t *lower = 0;
    uint8_t src[128];
    uint8_t font;
    uint8_t *du;
    uint8_t *dl;
    unsigned i;
    uint16_t abs_u = CHS_MENU_CURSOR_TILE;
    uint16_t abs_l = CHS_MENU_CURSOR_TILE_HI;

    if (!win)
        return 0;

    font = win_u8(win, WIN_FONTNUM_REAL);
    if (font > 6u)
        font = FONT_NORMAL_SHADOWED;
    if (!chs_font_is_shadowed(font))
        return 0;

    chs_get_glyph_tile_pointers(font, 0xEFu, &upper, &lower);
    if (!upper || !lower)
        return 0;

    for (i = 0; i < 128u; i++)
        src[i] = 0;
    for (i = 0; i < 32u; i++) {
        src[0x00 + i] = upper[i];
        src[0x20 + i] = lower[i];
    }

    du = vram_tile(win, abs_u);
    dl = vram_tile(win, abs_l);
    draw_glyph_tile_12(win, du, 0, src + 0x00, 0, 8);
    draw_glyph_tile_12(win, dl, 0, src + 0x20, 0, 8);
    chs_update_tilemap(win, abs_u, abs_l);
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
    return 1;
}

void DrawGlyph_Chinese(TextPrinter *win, const uint8_t *glyph_src)
{
    DrawGlyph_Chinese_Adv(win, glyph_src, CHS_GLYPH_ADVANCE_PX);
}

void DrawGlyph_Chinese_Adv(TextPrinter *win, const uint8_t *glyph_src, unsigned adv_px)
{
    volatile struct ChineseTileState *st = chs_bind_pitch_slot(win);
    uint8_t cur_tx = win_u8(win, WIN_CURSOR_TILE_X);
    unsigned last;
    int linear;
    int newline_reset = 0;

    /* Slot bind already switched windows without wiping other printers.
     * Only reset pitch inside this slot on FE / cursor desync. */
    if (st->chs_px != 0 && cur_tx <= st->base_tx) {
        /* FE reset CURSOR_TILE_X to line start while chs_px still mid-run
         * → first glyph would start at startPixel=chs_px&7 (左缘切半). */
        st->chs_px = 0;
        st->base_tx = pitch_capture_base_tx(win);
        newline_reset = 1;
    } else if (st->chs_px != 0) {
        last = st->last_adv ? st->last_adv : CHS_GLYPH_ADVANCE_PX;
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

    linear = DrawGlyph_ShouldUseLinear(win, st->write_op);
    /*
     * Linear 8+4: pass2 (startPixel==0) does not advance TILE_OFFSET, so the
     * next glyph's pass1 reuses those VRAM tiles. Same-line overlap is
     * intentional; after FE the next row still shares that offset → left
     * edge of 捉/性 appears as a sliver at the end of the previous line.
     * Bump offset on newline so the new row gets fresh tiles.
     */
    if (newline_reset && linear) {
        uint16_t off = win_u16(win, WIN_TILE_OFFSET);
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
    }

    drawGlyph_Adv(win, glyph_src, linear, adv_px);
}
