/* text_render.c — refpr + pitch + GCTN（布局门控见 text_scene.c） */
#include "text_render.h"
#include "text_scene.h"

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
                      ^ ((uint16_t)win_u8(win, WIN_CURSOR_X) << 4)
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

uint8_t chs_pitch_write_op(TextPrinter *win)
{
    return chs_bind_pitch_slot(win, 0)->write_op;
}

void chs_pitch_set_write_op(TextPrinter *win, uint8_t op)
{
    chs_bind_pitch_slot(win, 0)->write_op = op;
}

static int draw_use_linear(TextPrinter *win, uint8_t write_op)
{
    return scene_should_use_linear(win, write_op);
}

static void ensure_linear_dest_floor(TextPrinter *win)
{
    scene_apply_linear_floor(win);
}

static uint16_t GetCursorTileNum_Linear(TextPrinter *win, unsigned xOff, unsigned yOff)
{
    return scene_gctn_linear(win, xOff, yOff);
}

static void GetCursorTileNum_Mode2(
    TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower)
{
    scene_gctn_mode2(win, tile_x, upper, lower);
}

static void map_at(TextPrinter *win, uint8_t tx, uint16_t abs_u, uint16_t abs_l)
{
    win_set_u8(win, WIN_CURSOR_TILE_X, tx);
    UpdateTilemap_PreserveCursorX(win, abs_u, abs_l);
}

/* ---- sChsShiftAmounts（pokeruby text.c sGlyphShiftAmounts 同构）----
 * left = startPixel*4：本 tile 内左移；right = 32-left：溢出段右移。
 * 恒等式 width-(gw_end-8) = 8-startPixel ⇒ right 对任意 width≤8 都成立；
 * need_spill 蕴含 startPixel≥1 ⇒ right≤28，无 >>32 UB。 */
static const struct ChsShiftAmount {
    uint32_t left;
    uint32_t right;
} sChsShiftAmounts[8] = {
    {  0, 32 },
    {  4, 28 },
    {  8, 24 },
    { 12, 20 },
    { 16, 16 },
    { 20, 12 },
    { 24,  8 },
    { 28,  4 },
};

/* 美版 DrawGlyphTile_ShadowedFont + ShiftGlyphTile_*_Width0..8 的合体字版实现：
 * src 经 CopyGlyph(C,E,D) 已烘焙调色板（= 美版 colors[] 逐 nibble 查表的等价
 * 前置），故整行按字移位即可，逐像素循环取缔。
 * 输出语义与旧 refpr 逐像素版逐字节一致：
 *   左 tile  [0,startPixel) 保留 | 字形覆盖 | [gw_end,8) 清底色
 *   spill    整 tile 重写 = 溢出字形 [0,gw_end-8) | 清底色 [gw_end-8,8) */
void DrawGlyphTile_refpr(
    TextPrinter *win, struct GlyphTileInfo *info,
    const uint8_t *src32, uint8_t *dest, uint8_t *spillTile)
{
    uint32_t temp_words[8];
    uint32_t dest_words[8];
    uint32_t spill_words[8];
    uint8_t *temp = (uint8_t *)temp_words;
    unsigned startPixel = info->startPixel;
    unsigned width = info->width;
    unsigned gw_end;
    unsigned r;
    uint8_t fg_ov = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    uint8_t color_c = (fg_ov != 0u) ? fg_ov : win_u8(win, WIN_COLOR_C);
    uint8_t color_d = win_u8(win, WIN_COLOR_D);
    uint8_t color_e = win_u8(win, WIN_COLOR_E);
    int need_spill;
    uint32_t bg_word = 0x11111111u * (color_d & 0x0Fu);
    const struct ChsShiftAmount *sa;
    uint32_t keep_mask;
    uint32_t val;

    /* CopyGlyph(C,E,D) + 清列盖字：与 bak DrawGlyphTile_CHS 同构，保缩进/相位 */
    CopyGlyph2bppTo4bpp_Origin(src32, temp, color_c, color_e, color_d);

    if (spillTile == 0 && startPixel == 0u && width == 8u) {
        copy_tile32(dest, temp);
        return;
    }

    if (width > 8u)
        width = 8u;
    gw_end = startPixel + width;
    need_spill = (spillTile != 0) && (gw_end > 8u);
    sa = &sChsShiftAmounts[startPixel & 7u];
    keep_mask = (startPixel >= 8u) ? 0xFFFFFFFFu
                                   : ((1u << (startPixel * 4u)) - 1u);

    {
        const uint32_t *dv = (const uint32_t *)dest;
        for (r = 0; r < 8u; r++)
            dest_words[r] = dv[r];
    }

    for (r = 0; r < 8u; r++) {
        val = temp_words[r];
        if (width < 8u)
            val &= (1u << (width * 4u)) - 1u;

        dest_words[r] = (dest_words[r] & keep_mask) | (val << sa->left);
        if (gw_end < 8u)
            dest_words[r] |= bg_word << (gw_end * 4u);

        if (need_spill)
            spill_words[r] = (val >> sa->right)
                           | (bg_word << ((gw_end - 8u) * 4u));
    }

    copy_tile32(dest, dest_words);
    if (need_spill)
        copy_tile32(spillTile, spill_words);
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

    if (slot_new && st->chs_px == 0) {
        newline_reset = 1;
        *(volatile uint16_t *)CHS_LAST_OFF_ADDR = 0;
    }

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

/* FontFunc[2] 血条缓冲：对齐原生 BlitGlyph + dst+=0x40（每列 upper|lower）。
 * dst==0 为幻影打印，消费字符但不写。 */
static void DrawGlyphTiles_buffer(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    uint32_t dst_u = win_u32(win, WIN_TILE_DATA);
    uint8_t *dst;
    struct GlyphTileInfo info;
    unsigned cols;
    unsigned i;

    if (dst_u == 0u)
        return;

    dst = (uint8_t *)(uintptr_t)dst_u;
    if (glyphWidth < 8u)
        glyphWidth = 8u;
    if (glyphWidth > 12u)
        glyphWidth = 12u;

    cols = (glyphWidth <= 8u) ? 1u : 2u;
    info.startPixel = 0;

    for (i = 0; i < cols; i++) {
        const uint8_t *src_u = (i == 0u) ? tiles->tl : tiles->tr;
        const uint8_t *src_l = (i == 0u) ? tiles->bl : tiles->br;

        info.width = (i == 0u) ? 8u : (uint8_t)(glyphWidth - 8u);
        if (info.width == 0u)
            break;
        if (info.width > 8u)
            info.width = 8u;
        DrawGlyphTile_refpr(win, &info, src_u, dst, 0);
        DrawGlyphTile_refpr(win, &info, src_l, dst + 0x20, 0);
        dst += 0x40;
    }
    win_set_u32(win, WIN_TILE_DATA, (uint32_t)(uintptr_t)dst);
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
    case 2:
        /* FontFunc[2]：写 win[0x20] 缓冲，每列 +0x40（血条 OBJ 刷走） */
        DrawGlyphTiles_buffer(win, tiles, glyphWidth);
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
