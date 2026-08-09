/* AXVJ patch ??? ? ?? / Win ?? / ?????
 * ProcessCurrentChar ? pokeruby PrintNextChar
 */
#ifndef GAME_H
#define GAME_H

#include <stdint.h>

#define ADDR_CALL_VIA_R2           0x081B12DCu
#define ADDR_FONT_FUNC_TABLE       0x081BB3ACu
#define ADDR_COPY_GLYPH_2BPP_4BPP  0x080038A0u
#define ADDR_COPY_GLYPH_1BPP_4BPP  0x08003830u
#define ADDR_UPDATE_TILEMAP       0x080036DCu
#define ADDR_GET_GLYPH_TILE_PTRS   0x08003730u
#define ADDR_GAME_BIN              0x08800000u
#define LANGUAGE_JAPANESE          1u
#define CHS_GLYPH_ADVANCE_JP_PX    8u
/*
 * 短语表（PhraseTable）—— 固定长度字段突破字符数限制的方案。
 * 日版 Gen3 的招式/特性/物种等字段有 stride 限制（6-8 字节），
 * 若用 F9 00 ll tt 侧载一个汉字占 4 字节，8 字节槽最多 2 汉字。
 * 短语表将"文本存储"和"字段引用"解耦：
 *   字段槽（8B）：F9 <op> hi lo FF          → 4 字节引用
 *   PhraseTable：F9 00×N + FE/FB… + FF      → 展开侧载流（含控制符）
 * 查找路径：F9 80/op →
 *   PhraseOffsets[code]（u32 数组 @ 0x08810000）
 *   → PhraseTable + offset（字节流 @ 0x08820000）
 *   → 父串未结束 + 无 FE/FB/FA：内联绘制，INDEX+3 续父串（对齐 GetStringWidth）
 *   → 父串即短语引用+FF：切流，短语 FF = 整句 EOS（地名等）
 * layout: .org 0x08810000 → offsets （u32[code_max], sentinel = total_size）
 *         .org 0x08820000 → streams （PCS bytes ending in FF）
 *
 * 样式表（styles_data.asm，与 phrase_data.asm 对仗，均来自 translate.build.json）：
 *   StyleLeft[256] @ 0x0880F000 — F9 第二字节 → left(px)
 * PrintNextChar：非 0x80 的短语 op sticky 后按 StyleLeft[op] 整体左移一次。
 * 勿在 0x0203FFF0/F7F8 放 PhraseResume（崩/踩图）。
 * 改 styles/phrases 只重生 asm + armips，不必重编 game.bin。
 */
#define ADDR_STYLE_LEFT            0x0880F000u
#define ADDR_PHRASE_OFFSETS        0x08810000u
#define ADDR_PHRASE_TABLE          0x08820000u
#define ADDR_FONT_CHS_NORMAL       0x09000000u
/* Sym punct bank (9×64B), after Small @ 0x09100000+0xE0000.
 * Font3 layout: upper+lower 8×8 @4bpp-index (0/E/F), NOT 16×16 2bpp.
 * Drawn via PrintNextChar_C → DrawGlyph_Chinese_Adv(..., 8). */
#define ADDR_FONT_CHS_SYM          0x091E0000u
#define SYM_GLYPH_BASE             0x36u
#define SYM_GLYPH_COUNT            9u
#define ADDR_CHINESE_TILE_STATE    0x0203FFF8u

#define WIN_TEMPLATE        0x00
#define WIN_STATE           0x04
/* AXVJ TextPrinter: +0x0A = textMode (FontFuncTable index in entry.s);
 * +0x0B = fontNum (GetGlyphTilePointers). Colors are C/D/E only — do NOT
 * alias fontNum as COLOR_B (that caused dual-path / wrong glyph fetches). */
#define WIN_TEXTMODE        0x0A
#define WIN_FONTNUM         0x0A  /* legacy alias = textMode */
#define WIN_FONTNUM_REAL    0x0B
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
/* JP RenderTextHandleBold (0x08002CC0): dest buffer ptr (FontFunc[2] blit). */
#define WIN_TILE_DATA       0x20

/* eBattleInterfaceGfxBuffer (AXVJ literal). Docs/ref only — gate is textMode==2. */
#define ADDR_BATTLE_IF_GFX  0x02020004u
#define BATTLE_IF_GFX_SIZE  0x1000u

/* 8 bytes at EWRAM high (0x0203FFF8..FFFF). */
struct ChineseTileState {
    uint8_t  char_base;  /* +0 template charBaseBlock */
    uint8_t  write_op;   /* +1 */
    uint8_t  base_tx;    /* +2 pitch-run start CURSOR_TILE_X */
    uint8_t  last_adv;   /* +3 last glyph advance (8 JP / 12 CN) */
    uint16_t pitch_key;  /* +4 window fingerprint for pitch_reset */
    uint16_t chs_px;     /* +6 pixel X in pitch run */
};

/*
 * GBA 硬件以 8×8 tile 为单位（4bpp / tile 32B）。中文字模存储为 16×16
 * 标准 4-tile（TL/BL/TR/BR 各 32B 共 128B），但渲染时光标每次只推进
 * CHS_GLYPH_ADVANCE_PX（12px），而非 16px。原理：drawGlyph12 分两趟写
 * VRAM——左 8px（TL+BL）→ 右 4px（TR+BR 的左边 4px），两趟共进 12px。
 * 右 4px 跨入下一 tile 列形成 spill；下一字模的 startPixel 为 4（累积
 * chs_px & 7），其左 4px 覆盖上一字的溢出像素。由于汉字笔画集中在字模
 * 中部，外缘空白区域被覆盖不影响视觉。字模保持 16px 宽可复用原生 tilemap
 * 寻址逻辑（每列 2 tile，index +0/+1），兼容所有 Gen3 文本窗口。
 *
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
/* FE/FB newline: DrawGlyph_Chinese_Adv clears chs_px when cur_tx returns to
 * line start or pitch_key (Y) changes — see draw_glyph.c. */
#ifndef CHS_LINE_FEED_PATCH
#define CHS_LINE_FEED_PATCH 1
#endif

#define chinese_tile_state() ((volatile struct ChineseTileState *)ADDR_CHINESE_TILE_STATE)

#define CHS_WRITE_AUTO    0
#define CHS_WRITE_GRID    1
#define CHS_WRITE_FOOTER  2
#define CHS_WRITE_LINEAR  3
#define CHS_WRITE_SLOT    4

/* Shared low UI icon tiles (AXVJ JP) — Chinese Mode2/Linear must not blit here.
 * - Dex list No/ball: 0x1FC..0x1FF (CreateMonDexNum / CreateCaughtBall)
 * - Summary A/B prompt icons: 0x1E8..0x1FB (cancel/切换 still stomped at 0x1E8..1EF)
 * Remap into US dex range 0x3E8.. — unused on JP for these screens.
 * (Old ALT=0x1F0 was inside the protect band → cancelled the icons.) */
#define CHS_UI_ICON_TILE_LO     0x1E8u
#define CHS_UI_ICON_TILE_HI     0x1FFu
#define CHS_UI_ICON_TILE_ALT    0x3E8u
/* Aliases kept for call sites / docs */
#define CHS_DEX_UI_TILE_LO      CHS_UI_ICON_TILE_LO
#define CHS_DEX_UI_TILE_HI      CHS_UI_ICON_TILE_HI
#define CHS_DEX_UI_TILE_ALT     CHS_UI_ICON_TILE_ALT

#define CHS_TILE_GRID_W         30
#define CHS_TILE_POOL_END            0x180
#define CHS_LINEAR_STICKY_END        0x60
#define CHS_MENU_LINEAR_FLOOR        0x100
#define CHS_SHOP_DESC_LINEAR_FLOOR   0x228
#define CHS_SHOP_DESC_POOL_END       0x2D0
#define CHS_MODE2_FOOTER_BAND        0x100
/* Far from MENU_BAND 0x17A and UI icons 0x1E8 — party DoWhat vs 查看能力 串台 */
#define CHS_MODE2_PARTY_FOOTER_BAND  0x2A0
#define CHS_MODE2_MENU_BAND          0x17A
#define CHS_PARTY_FOOTER_LINEAR_FLOOR 0x2C0
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
#define CHS_PHRASE_DEFAULT      0x80

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
static inline void win_set_u32(TextPrinter *w, unsigned off, uint32_t v)
{
    w[off] = (uint8_t)(v & 0xFF);
    w[off + 1] = (uint8_t)((v >> 8) & 0xFF);
    w[off + 2] = (uint8_t)((v >> 16) & 0xFF);
    w[off + 3] = (uint8_t)((v >> 24) & 0xFF);
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

typedef void (*chs_fn4)(const void *src, void *dst, uint32_t a, uint32_t b);

static inline void chs_copy_glyph_1bpp_to_4bpp(
    const void *src, void *dst, uint32_t fg, uint32_t bg)
{
    ((chs_fn4)(ADDR_COPY_GLYPH_1BPP_4BPP | 1u))(src, dst, fg, bg);
}

static inline uint16_t chs_pitch_key(TextPrinter *win)
{
    /* Window identity only — do NOT fold CURSOR_X (JP advances it each glyph).
     * XOR template ptr so party footer (y=17) ≠ action menu item (also y=17). */
    uint8_t *tpl = win_template(win);
    uint16_t w = tpl ? (uint16_t)(((uintptr_t)tpl >> 2) & 0xFFFFu) : 0;
    return (uint16_t)(win_u16(win, WIN_TILE_BASE)
                      ^ ((uint16_t)win_u8(win, WIN_CURSOR_Y) << 8)
                      ^ (uint16_t)win_u8(win, WIN_CURSOR_TILE_Y)
                      ^ w);
}

int PrintNextChar_C(TextPrinter *win, uint32_t cur_char);

void DrawGlyph_Chinese(TextPrinter *win, const uint8_t *glyph_src);
void DrawGlyph_Chinese_Adv(TextPrinter *win, const uint8_t *glyph_src, unsigned adv_px);
/* Clear ChineseTileState pitch after FE/FB/FA (optional asm hook). */
void Chinese_PitchReset(TextPrinter *win);
/* FA/FB DrawInitialDownArrow：同步 TILE_OFFSET / CURSOR，避免双▼。 */
void WaitArrow_Prepare_C(TextPrinter *win);
int  DrawGlyph_ShouldUseLinear(TextPrinter *win, uint8_t write_op);
void drawGlyph12(TextPrinter *win, const uint8_t *src18, int linear);
void drawGlyph_Adv(TextPrinter *win, const uint8_t *src128, int linear, unsigned adv_px);
int  GetStringWidth_Chinese(TextPrinter *win, const uint8_t *s,
                           uint16_t *index, uint8_t *width);
uint8_t GetStringWidthChinese_Full(TextPrinter *win, const uint8_t *s);
/* Kept for link compat; map popup trampoline no longer calls this. */
uint8_t MapName_DisplayCellLength_C(const uint8_t *s);

int  scene_field_wants_linear(TextPrinter *win);
int  scene_menu_wants_mode2(TextPrinter *win);
int  scene_is_shop_desc(TextPrinter *win);
int  scene_is_party_footer(TextPrinter *win);
int  scene_jp_via_chs(TextPrinter *win);
int  scene_is_battle_interface_dest(TextPrinter *win);
void scene_mode2_apply(TextPrinter *win, int *x, int *y, int *band, int *origin);
int  scene_battle_force_linear(TextPrinter *win);
int  scene_keep_linear_16(TextPrinter *win);

/*
 * AXVJ GetGlyphTilePointers @ 0x08003730 is 4-arg (JP ROM; language baked
 * into sFonts[fontNum]):
 *   void GetGlyphTilePointers(u8 fontNum, u16 glyph, u8 **upper, u8 **lower);
 * pokeruby US has an extra language arg — do NOT pass LANGUAGE_JAPANESE here
 * or r1 becomes glyph=1 and r2 is treated as a pointer → blank text.
 */
static inline void chs_get_glyph_tile_pointers(
    uint8_t font_num, uint16_t glyph,
    uint8_t **upper, uint8_t **lower)
{
    typedef void (*fn_t)(uint32_t, uint32_t, uint8_t **, uint8_t **);
    ((fn_t)(ADDR_GET_GLYPH_TILE_PTRS | 1u))(
        font_num, glyph, upper, lower);
}

/* Fonts 0/1/2/6 = 1bpp (8B/tile); 3/4/5 = shadowed 4bpp-index (32B/tile). */
static inline int chs_font_is_shadowed(uint8_t font_num)
{
    return font_num >= 3u && font_num <= 5u;
}

#endif /* GAME_H */
