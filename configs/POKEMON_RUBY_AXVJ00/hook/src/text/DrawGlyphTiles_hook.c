/* DrawGlyphTiles_hook.c — CHS 两趟绘制引擎（8+4 spill）+ pitch 相位槽。
 *
 * 命名对齐 pokeruby text.c：GetCursorTileNum_Linear/Mode2（官方
 * GetCursorTileNum 两分支）、DrawGlyphTile_CHS（官方 DrawGlyphTile_*）、
 * DrawGlyphTiles_CHS_Core（官方 DrawGlyphTiles）、PrintGlyph_*（官方
 * PrintGlyph_TextMode*）。8+4 spill 与 chs_px 相位为自实现保留（REQ§3/§4）。
 *
 * 本文件只含绘制引擎本体；各方法钩分文件：
 *   DrawGlyph_CHS_hook.c / DrawInitialDownArrow_hook.c /
 *   DrawMenuCursorEF_hook.c / GetGlyphTilePointers_hook.c
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

/* 一个 16×16 CHS 字模的四个 32B tile（TL/BL/TR/BR）。 */
struct ChsGlyphTiles {
    uint8_t *tl;
    uint8_t *bl;
    uint8_t *tr;
    uint8_t *br;
};

static uint8_t pitch_capture_base_tx(TextPrinter *win)
{
    return win_u8(win, WIN_CURSOR_TILE_X);
}

/*
 * SoftKeyboard / party / shop share one CHS tile pool (JP PCS must stay here).
 * Isolate pitch+write_op per printer fingerprint so switching windows does not
 * clobber another printer's chs_px (title glyph paste into keyboard rows).
 */
volatile struct ChineseTileState *chs_bind_pitch_slot(TextPrinter *win, int *out_is_new)
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

void Chinese_PitchReset(TextPrinter *win)
{
    pitch_reset(win);
}

uint8_t *vram_tile(TextPrinter *win, uint16_t tile)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, 0x0C);
    return tile_data + ((uint32_t)tile << 5);
}

/* Remap abs tile out of reserved UI bands. Mode2 + Linear.
 * Battle dialogue/menu keep 0x1E8.. — remapping to 0x3E8 leaves FillWindow
 * tile 0x0A visible as solid black bars. */
static uint16_t avoid_dex_ui_tile(TextPrinter *win, uint16_t tile)
{
    if (scene_is_battle_text_window(win))
        return tile;
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
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    uint16_t floor;

    if (scene_is_battle_text_window(win))
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

/* pokeruby GetCursorTileNum 的 Linear 分支（tileDataOffset 线性推进）。 */
static uint16_t GetCursorTileNum_Linear(
    TextPrinter *win, unsigned xOffset, unsigned yOffset)
{
    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    return avoid_dex_ui_tile(
        win, (uint16_t)(tile_base + off + 2u * xOffset + yOffset));
}

/* pokeruby GetCursorTileNum 的 TEXT_MODE_UNKNOWN2 分支（Mode2 网格）+
 * scene_mode2_apply 场景修正。返回 upper/lower 一对 tile 号。 */
static void GetCursorTileNum_Mode2(
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
        *upper = avoid_dex_ui_tile(win, (uint16_t)idx);
        *lower = avoid_dex_ui_tile(win, (uint16_t)(idx + CHS_TILE_GRID_W));
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
 * 单 tile 绘制：官方 CopyGlyph 重映射到 IWRAM，再按 startPixel/width 合成。
 * 对齐官方 DrawGlyphTile_UnshadowedFont/ShadowedFont(struct GlyphTileInfo *)；
 * win 仅取 C/D/E 色（官方经 sGlyphBuffer.colors 预载，CHS 暂走 CopyGlyph，
 * 见 REQ§4）。spillTile=相邻 VRAM tile（跨列 spill），NULL=无。
 */
void DrawGlyphTile_CHS(
    TextPrinter *win, struct GlyphTileInfo *info, uint8_t *spillTile)
{
    uint32_t temp_words[8];
    uint32_t dest_words[8];
    uint32_t spill_words[8];
    uint8_t *temp = (uint8_t *)temp_words;
    uint8_t *dest_l = (uint8_t *)dest_words;
    uint8_t *spill_l = (uint8_t *)spill_words;
    uint8_t *dest = (uint8_t *)info->dest;
    const uint8_t *src32 = info->src;
    unsigned startPixel = info->startPixel;
    unsigned width = info->width;
    unsigned r, c;
    unsigned gw_end = startPixel + width;
    uint8_t fg_ov = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    uint8_t color_c = (fg_ov != 0u) ? fg_ov : win_u8(win, WIN_COLOR_C);
    uint8_t color_d = win_u8(win, WIN_COLOR_D);
    uint8_t color_e = win_u8(win, WIN_COLOR_E);
    int need_spill = (spillTile != 0) && (gw_end > 8u);

    /* CopyGlyph(C,E,D): 15→ink, 14→shadow, 0→bg. Unshadow font has no 14. */
    chs_copy_glyph_2bpp_to_4bpp(src32, temp, color_c, color_e, color_d);

    /* Fast path: full 8px column, tile-aligned — CopyGlyph buffer → VRAM. */
    if (spillTile == 0 && startPixel == 0u && width == 8u) {
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
        const uint32_t *sv = (const uint32_t *)spillTile;
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
        copy_tile32(spillTile, spill_l);
}

static void map_at(TextPrinter *win, uint8_t tx, uint16_t abs_u, uint16_t abs_l)
{
    win_set_u8(win, WIN_CURSOR_TILE_X, tx);
    chs_update_tilemap(win, abs_u, abs_l);
}

/*
 * DrawGlyphTiles_CHS_Core — 官方 DrawGlyphTiles(win,glyph,glyphWidth) 的 CHS 版：
 * 两趟 8+(glyphWidth-8)，dest 取址走 GetCursorTileNum_Linear/Mode2，
 * 字模四 tile 由调用方经 Hook3（GetGlyphTilePointers_CHS）或组合缓冲给出。
 */
static void DrawGlyphTiles_CHS_Core(
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
    su = 0;
    sl = 0;

    if (st->chs_px == 0)
        st->base_tx = pitch_capture_base_tx(win);

    startPixel = (unsigned)(st->chs_px & 7u);
    map_tx = (uint8_t)(st->base_tx + (st->chs_px >> 3));

    info.startPixel = (uint8_t)startPixel;
    info.textMode = 0;
    info.colors = 0;

    /* ---- pass width 8: TL + BL ---- */
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
        info.src = tiles->tl;
        info.dest = (uint32_t *)(uintptr_t)du;
        info.width = 8;
        DrawGlyphTile_CHS(win, &info, du_sp);
        info.src = tiles->bl;
        info.dest = (uint32_t *)(uintptr_t)dl;
        DrawGlyphTile_CHS(win, &info, dl_sp);
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
        info.src = tiles->tl;
        info.dest = (uint32_t *)(uintptr_t)du;
        info.width = 8;
        DrawGlyphTile_CHS(win, &info, du_sp);
        info.src = tiles->bl;
        info.dest = (uint32_t *)(uintptr_t)dl;
        DrawGlyphTile_CHS(win, &info, dl_sp);
        map_at(win, map_tx, abs_u, abs_l);
    }

    st->chs_px = (uint16_t)(st->chs_px + 8u);
    if (pass2_w == 0u) {
        /* Sym punct adv=8 at phase 4: right half lands in next tile via spill.
         * Hanzi adv=12 maps that tile in pass2; here pass2 is skipped — if we
         * omit map_at, line-final 。 is a crescent (mid-line OK: next Hanzi maps it). */
        if (spilled)
            map_at(win, (uint8_t)(map_tx + 1u), su, sl);
        st->last_adv = (uint8_t)glyphWidth;
        win_set_u8(win, WIN_CURSOR_TILE_X,
            (uint8_t)(st->base_tx + ((st->chs_px + glyphWidth - 1) >> 3)));
        /* Do NOT advance WIN_CURSOR_X here. Pitch uses chs_px; Mode2 is
         * CURSOR_X+tile_x. Syncing CURSOR_X (even Linear-only) desyncs
         * TILE_X vs chs_px → pitch_reset every glyph (scattered text). */
        return;
    }

    map_tx = (uint8_t)(st->base_tx + (st->chs_px >> 3));

    /* ---- pass width pass2_w: TR + BR ---- */
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
        info.src = tiles->tr;
        info.dest = (uint32_t *)(uintptr_t)du;
        info.width = (uint8_t)pass2_w;
        DrawGlyphTile_CHS(win, &info, du_sp);
        info.src = tiles->br;
        info.dest = (uint32_t *)(uintptr_t)dl;
        DrawGlyphTile_CHS(win, &info, dl_sp);
        map_at(win, map_tx, abs_u, abs_l);
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + (startPixel == 0u ? 0u : 2u)));
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
        info.src = tiles->tr;
        info.dest = (uint32_t *)(uintptr_t)du;
        info.width = (uint8_t)pass2_w;
        DrawGlyphTile_CHS(win, &info, du_sp);
        info.src = tiles->br;
        info.dest = (uint32_t *)(uintptr_t)dl;
        DrawGlyphTile_CHS(win, &info, dl_sp);
        map_at(win, map_tx, abs_u, abs_l);
    }

    st->chs_px = (uint16_t)(st->chs_px + pass2_w);
    st->last_adv = (uint8_t)glyphWidth;
    win_set_u8(win, WIN_CURSOR_TILE_X,
        (uint8_t)(st->base_tx + ((st->chs_px + glyphWidth - 1) >> 3)));
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

/*
 * PrintGlyph_Common_CHS — 官方 PrintGlyph_TextMode 系与 DrawGlyph_TextMode 系合流：
 * 相位槽绑定、FE 后重置、TILE_OFFSET 补偿，然后进两趟核心。
 */
static void PrintGlyph_Common_CHS(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    int slot_new = 0;
    volatile struct ChineseTileState *st = chs_bind_pitch_slot(win, &slot_new);
    uint8_t cur_tx = win_u8(win, WIN_CURSOR_TILE_X);
    unsigned last;
    int linear;
    int newline_reset = 0;

    /*
     * 换行（FE）后原版置 cursorTileX=0 且 cursorTileY+=2 → pitch_key 变化 →
     * 此处为新 slot。Linear 下行尾 pass2 spill（右 4px）仍挂在上一行末尾
     * 的 tile 上，若不 bump TILE_OFFSET，下一行首字 pass1 会复用该 tile →
     * 行尾出现下一行首字的前半拉（Bug3，奇数标点相位为 4 时必现）。
     * 历史版在 key 变化时 newline_reset=1；8 槽化后该补偿丢失，这里补回。
     */
    if (slot_new && st->chs_px == 0)
        newline_reset = 1;

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

    DrawGlyphTiles_CHS_Core(win, tiles, linear, glyphWidth);
}

/* F9 汉字：gidx 经 Hook3（GetGlyphTilePointers_CHS）解析左右半字模。 */
void PrintGlyph_CHS_Adv(TextPrinter *win, uint32_t gidx, unsigned glyphWidth)
{
    struct ChsGlyphTiles t;

    GetGlyphTilePointers_CHS(FONT_NORMAL_SHADOWED, gidx, &t.tl, &t.bl);
    GetGlyphTilePointers_CHS(FONT_NORMAL_SHADOWED,
                             gidx | CHS_GLYPH_HALF_BIT, &t.tr, &t.br);
    PrintGlyph_Common_CHS(win, &t, glyphWidth);
}

void PrintGlyph_CHS(TextPrinter *win, uint32_t gidx)
{
    PrintGlyph_CHS_Adv(win, gidx, CHS_GLYPH_ADVANCE_PX);
}

/* Sym 标点 / JP 组合缓冲（128B TL,BL,TR,BR 连续）入口。 */
void PrintGlyph_Tiles_CHS_Adv(
    TextPrinter *win, const uint8_t *tiles128, unsigned glyphWidth)
{
    struct ChsGlyphTiles t;
    t.tl = tiles128 + 0x00;
    t.bl = tiles128 + 0x20;
    t.tr = tiles128 + 0x40;
    t.br = tiles128 + 0x60;
    PrintGlyph_Common_CHS(win, &t, glyphWidth);
}

/* =============================================================================
 * 场景布局门控（scene gates）—— 原 DrawGlyphTiles_scene.c 并入（2026-08-22）
 * pokeruby 对应: 各界面 tilemap 排布差异（pokedex.c / shop / battle_interface 等）
 * A/B 实测(2026-08-22, scene_off_test ROM)：关闭后战斗招式说明黑块、商店串台、
 * 队伍底部错位、血条乱码 —— 全部门控确认必要，勿删。
 * 全部为无副作用判断函数；新增界面支持时在此追加门控。
 * ============================================================================= */

/**
 * Party DoWhat at (1,17): often F9 00 after \0F.
 * Mode2 with y'=y-16 + PARTY_FOOTER_BAND, origin=+2 (same grid as nick).
 */
int scene_is_party_footer(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint8_t left;
    uint8_t top;

    if (!tpl || tpl[1] != 2)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    left = win_u8(win, WIN_CURSOR_X);
    if (left >= CHS_SHOP_LIST_LEFT)
        return 0;
    top = win_u8(win, WIN_CURSOR_Y);
    return (top == CHS_PARTY_FOOTER_TOP_TILE || top == CHS_PARTY_FOOTER_TOP_PX);
}

/**
 * Legacy helper. DrawGlyph_ShouldUseLinear no longer forces Linear on
 * left<14 (that caught title/shop multichoice → shared-tile 串台).
 */
int scene_field_wants_linear(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    if (!tpl)
        return 0;
    if (tpl[1] != 2)
        return 1;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 1;
    if (scene_is_party_footer(win))
        return 0;
    if (scene_is_shop_desc(win))
        return 1;
    return 0;
}

/** Font3 Mode2 grid: charBase 0 (naming SoftKeyboard/title) or 2 (menus).
 * SoftKeyboard BG1 is charBase 0 — requiring only charBase2 forced Linear and
 * aliased every keyboard row + title onto the same low Linear tiles. */
int scene_menu_wants_mode2(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint8_t char_base;

    if (!tpl)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    char_base = tpl[1];
    if (char_base != 0 && char_base != 2)
        return 0;
    if (scene_is_shop_desc(win))
        return 0;
    if (scene_is_shop_bag_list(win))
        return 0;
    return 1;
}

int scene_is_shop_desc(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint8_t left;
    uint8_t top;

    if (!tpl || tpl[1] != 2)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    left = win_u8(win, WIN_CURSOR_X);
    if (left >= CHS_SHOP_LIST_LEFT)
        return 0;
    if (scene_is_party_footer(win))
        return 0;
    top = win_u8(win, WIN_CURSOR_Y);
    return (top == CHS_SHOP_DESC_TOP_PX || top == CHS_SHOP_DESC_TOP_TILE);
}

/**
 * Shop buy / bag item rows — Mode2 grid can stomp window-frame tiles.
 * Keep Linear (cursor ▶ uses CHS_MENU_CURSOR_TILE, not the shared pool).
 *
 * Narrow gates (continue-screen left=2 must NOT match):
 * - Bag names/qty: high TILE_BASE from bag printers (0x8A… / 0x66…)
 * - Shop+bag while InitMenu(1,1,n≥7) active: names left=2, price/qty left=7
 */
int scene_is_shop_bag_list(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    const uint8_t *gmenu;
    uint8_t left;
    uint16_t tile_base;

    if (!tpl || tpl[1] != 2)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    if (scene_is_shop_desc(win) || scene_is_party_footer(win))
        return 0;

    left = win_u8(win, WIN_CURSOR_X);
    tile_base = win_u16(win, WIN_TILE_BASE);

    /* Bag item-name printer: TILE_BASE = 0x8A + 14*row */
    if (left == 2u && tile_base >= 0x80u && tile_base < 0x120u)
        return 1;
    /* Bag quantity printer: TILE_BASE = 0x66 / 0x6c / … */
    if (left == 7u && tile_base >= 0x60u && tile_base < 0x90u)
        return 1;

    gmenu = (const uint8_t *)ADDR_GMENU;
    if (gmenu[GMENU_LEFT] == 1u && gmenu[GMENU_TOP] == 1u
        && gmenu[GMENU_MAX_MINUS_1] >= 6u) {
        if (left == 2u || left == 7u)
            return 1;
    }
    return 0;
}

/**
 * Mode2 layout (write.op upper config unchanged):
 * - party DoWhat geometry: shop origin(+2) + PARTY_FOOTER_BAND + y'=y-16
 * - left≥20 AND y≥13: MENU_BAND + y'=y-13 + origin 0x20 + x++（仅队伍选项）
 * - save/续关等 left≥20 但 y 小：vanilla origin+2，无 BAND
 */
void scene_mode2_apply(TextPrinter *win, int *x, int *y, int *band, int *origin)
{
    volatile struct ChineseTileState *st = chs_bind_pitch_slot(win, 0);
    uint8_t op = st->write_op;
    uint8_t left = win_u8(win, WIN_CURSOR_X);

    *band = 0;
    *origin = CHS_MODE2_ORIGIN_SHOP;

    if (scene_is_party_footer(win)) {
        *origin = CHS_MODE2_ORIGIN_SHOP;
        if (*y >= CHS_PARTY_FOOTER_TOP_PX)
            *y /= 8;
        if (*y >= 16) {
            *y -= 16;
            *band = CHS_MODE2_PARTY_FOOTER_BAND;
        }
        return;
    }
    if (op != 0)
        return;
    if (*y <= 20 && (*y & 1) == 0)
        return;
    if (left >= CHS_PARTY_MENU_LEFT && *y >= CHS_PARTY_MENU_TOP) {
        (*x)++;
        *y -= CHS_PARTY_MENU_TOP;
        *band = CHS_MODE2_MENU_BAND;
        *origin = CHS_MODE2_ORIGIN_MENU;
    }
}

int scene_is_battle_text_window(TextPrinter *win)
{
    uint16_t tb = win_u16(win, WIN_TILE_BASE);

    if (tb == CHS_BATTLE_DIALOG_BASE_LO)
        return 1;
    if (tb >= CHS_BATTLE_TEXT_BASE_LO && tb < CHS_BATTLE_TEXT_BASE_HI)
        return 1;
    return tb >= CHS_BATTLE_FIXED_BASE;
}

int scene_battle_force_linear(TextPrinter *win)
{
    return scene_is_battle_text_window(win);
}

int scene_is_battle_interface_dest(TextPrinter *win)
{
    return win_u8(win, WIN_TEXTMODE) == 2u;
}

/*
 * 缓冲型打印机（dest=win[0x20] 调用方 RAM 缓冲，之后 CpuSet 刷走，
 * 不碰 BG VRAM/tilemap）——CHS 引擎（template+0x0C 寻址 + UpdateTileMap）
 * 对它们全是错误语义，必须整体回官方 FontFunc：
 * - textMode==2: TextPrintBattleInterface 血条缓冲。
 * - textMode==1 && fontNum==4: RenderTextHandleBold（JP 0x08002CC0）
 *   共享静态窗 0x03004170（pokeruby gWindowTemplate_81E6C74:
 *   tilemap=NULL, font=4）——战斗队伍名称/概览列表实测路径
 *   （2026-08-22 gdb 日志：'ＭＥＷ'=c7bfd1 → 血条显示 '/AP'）。
 *   漏拦时字模写不进 win[0x20]，缓冲残留旧 tile → CpuSet 刷出固定乱码，
 *   且真 VRAM/tilemap 被顺带写花。
 */
int scene_is_buffer_printer(TextPrinter *win)
{
    if (scene_is_battle_interface_dest(win))
        return 1;
    return win_u8(win, WIN_TEXTMODE) == 1u
        && win_u8(win, WIN_FONTNUM_REAL) == 4u;
}

int scene_jp_via_chs(TextPrinter *win)
{
    return !scene_is_battle_interface_dest(win);
}

int scene_keep_linear_16(TextPrinter *win)
{
    (void)win;
    return 0;
}
