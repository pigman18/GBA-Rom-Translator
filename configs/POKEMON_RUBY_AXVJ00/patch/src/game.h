/* AXVJ patch ??? ? ?? / Win ?? / ?????
 * ProcessCurrentChar ? pokeruby PrintNextChar
 */
#ifndef GAME_H
#define GAME_H

#include <stdint.h>

#define ADDR_CALL_VIA_R2           0x081B12DCu
#define ADDR_FONT_FUNC_TABLE       0x081BB3ACu
#define ADDR_COPY_GLYPH_2BPP_4BPP  0x080038A0u
#define ADDR_UPDATE_TILEMAP       0x080036DCu
#define ADDR_GAME_BIN              0x08800000u
#define ADDR_PHRASE_OFFSETS        0x08810000u
#define ADDR_PHRASE_TABLE          0x08820000u
#define ADDR_FONT_CHS_NORMAL       0x09000000u
#define ADDR_CHINESE_TILE_STATE    0x0203FFF8u

#define WIN_TEMPLATE        0x00
#define WIN_STATE           0x04
#define WIN_FONTNUM         0x0A
#define WIN_FONTNUM_REAL    0x0B
#define WIN_COLOR_B         0x0B
#define WIN_COLOR_C         0x0C
#define WIN_COLOR_D         0x0D
#define WIN_COLOR_E         0x0E
#define WIN_PALETTE         0x0F
#define WIN_TEXT_PTR        0x10
#define WIN_TEXT_INDEX      0x14
#define WIN_TILE_BASE       0x16
#define WIN_TILE_OFFSET     0x18
#define WIN_CURSOR_X        0x1A
#define WIN_CURSOR_TILE_X   0x1B
#define WIN_CURSOR_Y        0x1C
#define WIN_CURSOR_TILE_Y   0x1D

/* 8 bytes at IWRAM end (0x0203FFF8..FFFF). */
struct ChineseTileState {
    uint16_t char_base; /* +0 */
    uint8_t  write_op;  /* +2 */
    uint8_t  base_tx;   /* +3 pitch-run start CURSOR_TILE_X */
    uint16_t next_abs;  /* +4 unused by Linear dest (was floor/sticky hijack) */

    uint16_t chs_px;    /* +6 pixel X in pitch run (RS 12 path) */
};

/*
 * 12px = ink / advance / line metrics (product).
 * Hardware glyph container stays 8x16 (two 8x8 tiles) / 16x16 slot — do not change.
 * See docs/FONT_12PX_DRAW.md and .cursor/rules/axvj-font-12px-only.mdc.
 */
#define CHS_GLYPH_ADVANCE_PX 12
#define CHS_CHAR_HEIGHT_PX   12
#define CHS_LINE_FEED_PX     14
#define CHS_CELL_BYTES       128
#ifndef CHS_MODE2_PITCH12
#define CHS_MODE2_PITCH12 0
#endif
#ifndef CHS_LINE_FEED_PATCH
#define CHS_LINE_FEED_PATCH 0
#endif

#define chinese_tile_state() ((volatile struct ChineseTileState *)ADDR_CHINESE_TILE_STATE)

#define CHS_WRITE_AUTO    0
#define CHS_WRITE_GRID    1
#define CHS_WRITE_FOOTER  2
#define CHS_WRITE_LINEAR  3
#define CHS_WRITE_SLOT    4

#define CHS_TILE_GRID_W         30
#define CHS_TILE_POOL_END            0x180
#define CHS_LINEAR_STICKY_END        0x60
#define CHS_MENU_LINEAR_FLOOR        0x100
#define CHS_SHOP_DESC_LINEAR_FLOOR   0x228
#define CHS_SHOP_DESC_POOL_END       0x2D0
#define CHS_MODE2_FOOTER_BAND        0x100
#define CHS_MODE2_PARTY_FOOTER_BAND  0x140
#define CHS_MODE2_MENU_BAND          0x17A
#define CHS_MODE2_ORIGIN_SHOP        2
#define CHS_MODE2_ORIGIN_MENU        0x20
#define CHS_SHOP_LIST_LEFT           14
#define CHS_SHOP_DESC_TOP_PX         0x68
#define CHS_SHOP_DESC_TOP_TILE       13
#define CHS_PARTY_MENU_LEFT          20
#define CHS_PARTY_MENU_TOP           13
#define CHS_PARTY_FOOTER_TOP_TILE    17
#define CHS_PARTY_FOOTER_TOP_PX      (17 * 8)
#define CHS_BATTLE_FIXED_BASE   0x280
#define CHS_FONT_GLYPH_MAX      7168
#define CHS_ESCAPE              0xF9
#define CHS_PHRASE_DEFAULT      0x7F

#define FONT_NORMAL_UNSHADOWED  0
#define FONT_NORMAL_SHADOWED    3

typedef uint8_t TextPrinter;

static inline uint8_t  win_u8(const TextPrinter *w, unsigned off)  { return w[off]; }
static inline uint16_t win_u16(const TextPrinter *w, unsigned off)
{
    return (uint16_t)(w[off] | (w[off + 1] << 8));
}
static inline uint32_t win_u32(const TextPrinter *w, unsigned off)
{
    return (uint32_t)w[off]
         | ((uint32_t)w[off + 1] << 8)
         | ((uint32_t)w[off + 2] << 16)
         | ((uint32_t)w[off + 3] << 24);
}
static inline void win_set_u8(TextPrinter *w, unsigned off, uint8_t v) { w[off] = v; }
static inline void win_set_u16(TextPrinter *w, unsigned off, uint16_t v)
{
    w[off] = (uint8_t)(v & 0xFF);
    w[off + 1] = (uint8_t)(v >> 8);
}
static inline uint8_t *win_template(TextPrinter *w)
{
    return (uint8_t *)(uintptr_t)win_u32(w, WIN_TEMPLATE);
}

typedef void (*chs_fn3)(void *a0, uint32_t a1, uint32_t a2);
typedef void (*chs_fn5)(const void *src, void *dst, uint32_t c, uint32_t e, uint32_t d);

static inline void chs_update_tilemap(TextPrinter *win, uint16_t upper, uint16_t lower)
{
    ((chs_fn3)(ADDR_UPDATE_TILEMAP | 1u))(win, upper, lower);
}
static inline void chs_copy_glyph_2bpp_to_4bpp(
    const void *src, void *dst, uint32_t c, uint32_t e, uint32_t d)
{
    ((chs_fn5)(ADDR_COPY_GLYPH_2BPP_4BPP | 1u))(src, dst, c, e, d);
}

int PrintNextChar_C(TextPrinter *win, uint32_t cur_char);

void DrawGlyph_Chinese(TextPrinter *win, const uint8_t *glyph_src);
int  DrawGlyph_ShouldUseLinear(TextPrinter *win, uint8_t write_op);
void drawGlyph12(TextPrinter *win, const uint8_t *src18, int linear);
int  GetStringWidth_Chinese(TextPrinter *win, const uint8_t *s,
                            uint16_t *index, uint8_t *width);
uint8_t GetStringWidthChinese_Full(TextPrinter *win, const uint8_t *s);

int  scene_field_wants_linear(TextPrinter *win);
int  scene_menu_wants_mode2(TextPrinter *win);
int  scene_is_shop_desc(TextPrinter *win);
int  scene_is_party_footer(TextPrinter *win);
void scene_mode2_apply(TextPrinter *win, int *x, int *y, int *band, int *origin);
int  scene_battle_force_linear(TextPrinter *win);
int  scene_keep_linear_16(TextPrinter *win);

#endif /* GAME_H */
