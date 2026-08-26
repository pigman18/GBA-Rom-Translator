/* =====================================================================================
 * text_render_inplace12.c — 原生寻址原地写 12px 渲染（bak 引擎移植，纯搬移）
 *
 * 来源：hook/src/bak/text/DrawGlyphTiles_hook.c + DrawInitialDownArrow_hook.c。
 * 策略：像素/表项写进**窗口自己的原生 tile 区**——Linear（TILE_OFFSET 行军）
 * 或 Mode2（y*30+x 网格），DrawGlyph_ShouldUseLinear 场景门控选择；战场=窗内，
 * 无跨窗竞争。相位状态 = ChineseTileState 槽（0x0203FF90，8B×8）+
 * ChsPitchCtrl LRU（0x0203FF80）。
 *
 * 与 bak 的差异（仅两处，均向上兼容）：
 *   1. tile 合成器改用共享 draw_tile（两版逐值同构）；
 *   2. render 入口加 textMode 分发：tm2（缓冲语义）与 tm4-7（未验证）不绘制
 *      ——bak 时代由引擎分发层拦截，现架构同等收口。
 * ===================================================================================== */
#include "game.h"
#include "text_render.h"

/* ---- pitch 状态（bak game.h 原样）---- */
#define CHS_PITCH_SLOT_COUNT 8u

struct ChineseTileState {
    uint8_t  char_base;  /* +0 template charBaseBlock */
    uint8_t  write_op;   /* +1 */
    uint8_t  base_tx;    /* +2 pitch-run start CURSOR_TILE_X */
    uint8_t  last_adv;   /* +3 last glyph advance (8 JP / 12 CN) */
    uint16_t pitch_key;  /* +4 window fingerprint for pitch_reset */
    uint16_t chs_px;     /* +6 pixel X in pitch run */
};

struct ChsPitchCtrl {
    uint8_t cur;                         /* +0 last bound slot */
    uint8_t gen;                         /* +1 bump on each bind */
    uint8_t pad[2];                      /* +2 */
    uint8_t age[CHS_PITCH_SLOT_COUNT];   /* +4 last-used gen per slot */
};

/* 窗口身份指纹（bak chs_pitch_key：不含 stream，不含 CURSOR_X） */
static uint16_t chs_pitch_key(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint16_t w = tpl ? (uint16_t)(((uintptr_t)tpl >> 2) & 0xFFFFu) : 0;
    return (uint16_t)(win_u16(win, WIN_TILE_BASE)
                      ^ ((uint16_t)win_u8(win, WIN_CURSOR_Y) << 8)
                      ^ (uint16_t)win_u8(win, WIN_CURSOR_TILE_Y)
                      ^ w);
}

static uint8_t pitch_capture_base_tx(TextPrinter *win)
{
    return win_u8(win, WIN_CURSOR_TILE_X);
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

/* ---- 场景布局门控（scene gates，bak 原样；A/B 实测全部必要，勿删）---- */
static int scene_is_party_footer(TextPrinter *win);
static int scene_menu_wants_mode2(TextPrinter *win);
static int scene_is_shop_desc(TextPrinter *win);
static int scene_is_shop_bag_list(TextPrinter *win);
static int scene_is_battle_text_window(TextPrinter *win);
static int scene_battle_force_linear(TextPrinter *win);
static void scene_mode2_apply(TextPrinter *win, int *x, int *y, int *band, int *origin);

static int scene_is_party_footer(TextPrinter *win)
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

static int scene_menu_wants_mode2(TextPrinter *win)
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

static int scene_is_shop_desc(TextPrinter *win)
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

static int scene_is_shop_bag_list(TextPrinter *win)
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

static void scene_mode2_apply(TextPrinter *win, int *x, int *y, int *band, int *origin)
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

static int scene_is_battle_text_window(TextPrinter *win)
{
    uint16_t tb = win_u16(win, WIN_TILE_BASE);

    if (tb == CHS_BATTLE_DIALOG_BASE_LO)
        return 1;
    if (tb >= CHS_BATTLE_TEXT_BASE_LO && tb < CHS_BATTLE_TEXT_BASE_HI)
        return 1;
    return tb >= CHS_BATTLE_FIXED_BASE;
}

static int scene_battle_force_linear(TextPrinter *win)
{
    return scene_is_battle_text_window(win);
}

/* ---- 寻址（pokeruby GetCursorTileNum 两分支 + UI 保护区重映射）---- */

static uint16_t avoid_dex_ui_tile(TextPrinter *win, uint16_t tile)
{
    if (scene_is_battle_text_window(win))
        return tile;
    if (tile >= CHS_MENU_CURSOR_TILE && tile <= CHS_MENU_CURSOR_TILE_HI)
        return (uint16_t)(CHS_MENU_CURSOR_TILE_ALT
                          + (tile - CHS_MENU_CURSOR_TILE));
    if (tile >= CHS_UI_ICON_TILE_LO && tile <= CHS_UI_ICON_TILE_HI)
        return (uint16_t)(CHS_UI_ICON_TILE_ALT + (tile - CHS_UI_ICON_TILE_LO));
    return tile;
}

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

static uint16_t GetCursorTileNum_Linear(
    TextPrinter *win, unsigned xOffset, unsigned yOffset)
{
    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    return avoid_dex_ui_tile(
        win, (uint16_t)(tile_base + off + 2u * xOffset + yOffset));
}

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

static void map_at(TextPrinter *win, uint8_t tx, uint16_t abs_u, uint16_t abs_l)
{
    win_set_u8(win, WIN_CURSOR_TILE_X, tx);
    UpdateTilemap_Origin(win, abs_u, abs_l);
}

/* ---- 场景门控：Linear / Mode2 选择（bak 原样）---- */
static int DrawGlyph_ShouldUseLinear(TextPrinter *win, uint8_t write_op)
{
    if (scene_battle_force_linear(win))
        return 1;
    if (scene_is_shop_desc(win) || scene_is_shop_bag_list(win))
        return 1;
    (void)write_op;
    if (scene_menu_wants_mode2(win))
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) == FONT_NORMAL_SHADOWED)
        return 0;
    return 1;
}

/* ---- 两趟核心（bak DrawGlyphTiles_CHS_Core 逐值原样；合成器走共享 draw_tile）---- */
static void inplace12_core(
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
        draw_tile(win, &info, du_sp);
        info.src = tiles->bl;
        info.dest = (uint32_t *)(uintptr_t)dl;
        draw_tile(win, &info, dl_sp);
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
        draw_tile(win, &info, du_sp);
        info.src = tiles->bl;
        info.dest = (uint32_t *)(uintptr_t)dl;
        draw_tile(win, &info, dl_sp);
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
        draw_tile(win, &info, du_sp);
        info.src = tiles->br;
        info.dest = (uint32_t *)(uintptr_t)dl;
        draw_tile(win, &info, dl_sp);
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
        info.src = tiles->tr;
        info.dest = (uint32_t *)(uintptr_t)du;
        info.width = (uint8_t)pass2_w;
        draw_tile(win, &info, du_sp);
        info.src = tiles->br;
        info.dest = (uint32_t *)(uintptr_t)dl;
        draw_tile(win, &info, dl_sp);
        map_at(win, map_tx, abs_u, abs_l);
    }

    st->chs_px = (uint16_t)(st->chs_px + pass2_w);
    st->last_adv = (uint8_t)glyphWidth;
    win_set_u8(win, WIN_CURSOR_TILE_X,
        (uint8_t)(st->base_tx + ((st->chs_px + glyphWidth - 1) >> 3)));
}

/* ---- 策略主体（bak PrintGlyph_Common_CHS 原样：相位校验 + FE 补偿）---- */
static void inplace12_common(
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
    if (newline_reset && linear) {
        uint16_t off = win_u16(win, WIN_TILE_OFFSET);
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
    }

    inplace12_core(win, tiles, linear, glyphWidth);
}

/* ---- render 入口：内部 textMode 分发（tm2/未验证不绘制）---- */
void render_inplace12(TextPrinter *win, const struct ChsGlyphTiles *t, unsigned w)
{
    switch (win_u8(win, WIN_TEXTMODE) & 7u) {
    case 0:
    case 1:
    case 3:
        inplace12_common(win, t, w);
        break;
    default:
        break;
    }
}

/* ---- FA/FB 箭头前置同步（bak WaitArrow_Prepare_C 原样，仅同步不设计数）---- */
void arrow_inplace12(TextPrinter *win)
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
