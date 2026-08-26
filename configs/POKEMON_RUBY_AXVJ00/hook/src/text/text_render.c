/* =====================================================================================
 * text_render.c — render 家族共享原语库（纯机制、零策略）
 *
 * 内容：VRAM tile 寻址 / 32B 拷贝 / nibble 像素件 / 单 tile 合成器。
 * 策略 = render_inplace12（text_render_inplace12.c）。
 * ===================================================================================== */
#include "text_render.h"
#include "text.h"   /* struct TextGlyph（CHS 直拷区）*/

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

/* ------------------------------------------------------------------
 * 单 tile 合成器（原 text.c DrawGlyphTile_ShadowedFont / bak
 * DrawGlyphTile_CHS，两版逐值同构，合一）：
 * 官方 CopyGlyph 重映射到栈上缓冲（15→ink/14→shadow/0→bg，C/D/E 终色，
 * FG 覆盖 ADDR_OPT_FG_COLOR），再按 startPixel/width 合成进 dest tile；
 * gw_end>8 时溢出像素写 spillTile（相邻列）。spillTile=NULL=无溢出。
 * ------------------------------------------------------------------ */
void draw_tile(TextPrinter *win, struct GlyphTileInfo *info, uint8_t *spillTile)
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

/* ---- CHS 字库参数（自 chinese_text.h 并入）---- */
#define CHS_GLYPH_HALF_BIT   0x8000u
#define CHS_GLYPH_IDX_MASK   0x7FFFu
#define CHS_FONT_GLYPH_MAX   7168

/* =====================================================================
 * §glyph —— 字形源统一解析（每字形字体属性）+ CHS 汉库直拷
 *
 * heritage：CHS 两函数来自 rh-hideout-chinese/pokeemerald-expansion
 * src/chinese_text.c（原 hook/src/chinese_text.c，2026-08-27 并入注销）。
 * 与 upstream 三处差异维持不变：
 *   1) IsChineseChar/IsChinesePunctuation 不移植——汉字由 F9 帧定界状态机隔离；
 *   2) 字库源为 armips 侧载 ADDR_FONT_CHS_NORMAL/SMALL（4bpp 预展开直拷）；
 *   3) 显式传参替代 upstream 全局 gCurGlyph（game.bin 无 .bss）。
 * ===================================================================== */
int GetGlyph(TextPrinter *win, uint32_t code, uint8_t *out128, uint8_t *outWidth)
{
    uint8_t fontNum = win_u8(win, WIN_FONTNUM_REAL);
    if (fontNum > 6u)
        fontNum = 3u;    /* bak DrawGlyph_JP_ViaCHS 钳制：非法 fontNum 回落 font3 */

    /* ---- 空白 ---- */
    if (code == 0) {
        unsigned i;
        for (i = 0; i < 128u; i++)
            out128[i] = 0;
        *outWidth = 8u;
        return 1;
    }

    /* ---- Sym 标点带 ---- */
    if (code >= SYM_GLYPH_BASE && code < SYM_GLYPH_BASE + SYM_GLYPH_COUNT) {
        const uint8_t *src = (const uint8_t *)(ADDR_FONT_CHS_SYM
                                               + (code - SYM_GLYPH_BASE) * 64u);
        unsigned i;
        for (i = 0; i < 32u; i++) {
            out128[0x00 + i] = src[i];
            out128[0x20 + i] = src[32u + i];
        }
        for (i = 0; i < 64u; i++)
            out128[0x40 + i] = 0;
        *outWidth = 8u;
        return 1;
    }

    /* ---- 日文 fontNum 字库（官方 GGTP；宽度恒 8px） ---- */
    {
        uint8_t *upper = 0;
        uint8_t *lower = 0;

        if (code >= 0xF7)
            return 0;
        GetGlyphTilePointers_Origin(fontNum, (uint16_t)code, &upper, &lower);
        if (!upper || !lower)
            return 0;

        for (unsigned i = 0; i < 64u; i++)
            out128[0x40 + i] = 0;
        if (FontIsShadowed(fontNum)) {
            copy_tile32(out128 + 0x00, upper);
            copy_tile32(out128 + 0x20, lower);
        } else {
            CopyGlyph1bppTo4bpp_Origin(upper, (uint32_t *)(uintptr_t)(out128 + 0x00), 0xFu, 0x0u);
            CopyGlyph1bppTo4bpp_Origin(lower, (uint32_t *)(uintptr_t)(out128 + 0x20), 0xFu, 0x0u);
        }
        *outWidth = 8u;
        return 1;
    }
}

void DecompressGlyph_Chinese(struct TextGlyph *glyph, uint16_t ChineseChar, uint8_t fontId)
{
    const uint8_t *base;
    const uint8_t *g;

    if (ChineseChar >= CHS_FONT_GLYPH_MAX)
        ChineseChar = 0;

    /* 根据字体类别选择字库（upstream 同款分支；fontId 语义对齐原生 fontNum）：
     * font4（队伍名等小字窗）→ FontChsSmall 8px；其余 → FontChsNormal 12px。 */
    base = (fontId == 4u) ? (const uint8_t *)ADDR_FONT_CHS_SMALL
                          : (const uint8_t *)ADDR_FONT_CHS_NORMAL;
    g = base + ((uint32_t)(ChineseChar & CHS_GLYPH_IDX_MASK) << 7);
    if (ChineseChar & CHS_GLYPH_HALF_BIT)
        g += 64u;

    /* 本工程字模布局：TL+0 / BL+32 / TR+64 / BR+96（各 32B tile）。
     * 填入 upstream struct TextGlyph 行主序：Top = TL|TR，Bottom = BL|BR。 */
    copy_tile32(&glyph->gfxBufferTop[0], g + 0u);
    copy_tile32(&glyph->gfxBufferTop[8], g + 64u);
    copy_tile32(&glyph->gfxBufferBottom[0], g + 32u);
    copy_tile32(&glyph->gfxBufferBottom[8], g + 96u);

    glyph->width = GetChineseFontWidthFunc(ChineseChar, fontId);
    glyph->height = (fontId == 4u) ? 8u : 12u;
}

/* 根据字体类别返回字宽（upstream 同名；本工程汉字宽 = 库定宽，无逐字表）。 */
uint8_t GetChineseFontWidthFunc(uint16_t ChineseChar, uint8_t fontId)
{
    (void)ChineseChar;
    switch (fontId) {
    case 4u:
        return 8u;   /* FontChsSmall：与原生 font4 半角小字同节奏 */
    default:
        return 12u;  /* FontChsNormal：12px 产品字宽 */
    }
}

/* =====================================================================
 * §policy —— render orchestration（原 src/text_render_inplace12.c 全量并入）
 *
 * 职责：scene 门控 / tm0-linear 与 tm2 槽指针两路 / pitch 相位状态机 /
 *       两趟（pass1 w=8 · pass2 w∈[0,4]）绘制编排；tile 合成经共享 draw_tile。
 * 注：16px 整列方案已放弃，pitch 相位家族维持现状。
 * ===================================================================== */
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

/* ---- pitch 状态（bak game.h 原样）---- */
#define CHS_PITCH_SLOT_COUNT 8u

/* TILE_OFFSET 高水位记录 @0x0203FF82（ChsPitchCtrl pad[2]，两代布局均空闲）：
 * 游戏把说明文本拆成多个 print 调用、每次重置 TILE_OFFSET——检测到回退即
 * 接续高水位，防止新块覆写前块 tile（缺口/重复字根因，2026-08-26 日志定案：
 * hover1 行12 格 386-388 与 389-391 写入完全相同的 tile 116/118/11A）。 */
#define CHS_LAST_OFF_ADDR 0x0203FF82u

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

    /* ---- 分块 print 检测（仅 Linear；行中 chs_px 续跑时 off 回退 =
     * 游戏开了新 print 调用并重置 TILE_OFFSET）→ 接续我方高水位，
     * 新块拿新 tile，不覆写前块（缺口/重复字根因修复）---- */
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

    inplace12_core(win, tiles, linear, glyphWidth);

    /* 记录 TILE_OFFSET 高水位（仅 Linear；供分块检测） */
    if (linear)
        *(volatile uint16_t *)CHS_LAST_OFF_ADDR = win_u16(win, WIN_TILE_OFFSET);
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
