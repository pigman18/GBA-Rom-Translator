/* =====================================================================================
 * text.c — AXVJ 日版打印引擎（全面接管版）
 *
 * 架构：严格 pokeruby 数据流 + 日版语义（设计文档 docs/ruby_jp_design.md）：
 *   取码 → GetGlyph（唯一取址，逐字形字体属性）→ sPrintGlyphFuncs[textMode]
 *   → sWriteGlyphTilemapFuncs[fontNum] → UpdateTilemap(win, nCols, tiles..)
 *
 * 四行一分发（一行一原生语义，行间零共享可变状态）：
 *   tm0 = FontFunc[0] Linear 滚动光栅（TILE_BASE+TILE_OFF，对话/战斗/详情页）
 *   tm1 = FontFunc[1] 等宽：保留区像素 + cursor 格表项（队伍名/请选择/选项）
 *   tm2 = FontFunc[2] 指针缓冲（dst==0 幻影打印跳过）
 *   tm3 = 与 tm1 共用（网格"就地画"对 CHS 动态字模不可行，等价实现）
 *   tm4..7 / 未验证 fontNum → UNKNOWN：消费返回 1、无绘制（缺字=排查信号）
 *
 * 字体为每字形属性（GetGlyph 返回 width/bank）：
 *   常规（fn3 等）= FontChsNormal 12px；队伍等 fn4 = FontChsSmall 8px 沉底小字
 *   （与原生 font4 8×8 混排节奏一致）；同流混排由像素制光标自然处理。
 *
 * hook 面（2026-08-24 收敛定案）：本文件有且只有一个 ROM hook——
 *   P01@0x032F8 → entry.s EngineEntry → PrintNextChar_Hook。
 *   除 PrintNextChar_Hook 与导出工具 GetStringWidth 外全部 static（内部专用）：
 *     Hook3/P02 已移除（GetGlyph 内部 static GetGlyphTilePointers 承担）；
 *     P05 已折入 static DrawInitialDownArrow（pokeruby text.c 同名）；
 *     P04 地名居中独立为 src/map_name_popup/（GetStringWidth 由本文件提供）。
 * 本文件取代 text_jp2chs.c 及旧多文件引擎（归档于 src/bak/text/，移出构建）。
 * ===================================================================================== */
#include "game.h"

/* =====================================================================
 * §1 常量与布局
 * ===================================================================== */
#define PCS_CTRL_BASE        0xFAu
#define PCS_MENU_CURSOR      0xEFu

enum {
    AXV_STATE_END = 0,
    AXV_STATE_BEGIN,
    AXV_STATE_NORMAL,
    AXV_STATE_CHAR_DELAY,
    AXV_STATE_PAUSE,
    AXV_STATE_WAIT_BUTTON,
    AXV_STATE_NEWLINE,
    AXV_STATE_PLACEHOLDER,
    AXV_STATE_WAIT_CLEAR,
    AXV_STATE_WAIT_SCROLL,
    AXV_STATE_WAIT_SOUND,
};

/* FC 子类型（sub_8003110，= pokeruby ExtCtrlCode 家族 1..16） */
#define FC_FG            1u
#define FC_BG            2u
#define FC_SHADOW        3u
#define FC_ALLCOLORS     4u
#define FC_PALETTE       5u
#define FC_FONT          6u
#define FC_DEFAULTFONT   7u
#define FC_PAUSE         8u
#define FC_WAITBUTTON    9u
#define FC_WAITSOUND     10u
#define FC_PLAYBGM       11u
#define FC_PLAYSE        12u
#define FC_ESCAPE        13u
#define FC_SHIFT_TILE_X  14u
#define FC_SHIFT_TILE_Y  15u
#define FC_CLEARWINDOW   16u

#define WIN_BUFFER_PTR   0x20

#define GLYPH_SRC_CHS 0x01000000u

struct ChsGlyphTiles {
    uint8_t *tl;
    uint8_t *bl;
    uint8_t *tr;
    uint8_t *br;
};

/* ---- 前置声明 ---- */
static int  GetGlyph(TextPrinter *win, uint32_t code, uint8_t *out128, uint8_t *outWidth);
static void PrintGlyph_TextMode0(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth);
static void PrintGlyph_TextMode2(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth);
static void PrintGlyph_Unknown(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth);
static void PrintGlyph_TextMode1(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth);
int  PrintNextChar_Hook(TextPrinter *win);
static int  DrawMenuCursorEF(TextPrinter *win);
static void PrintGlyph(TextPrinter *win, uint32_t gidx, unsigned glyphWidth);
static int  DrawGlyph(TextPrinter *win, uint32_t cur_char);

/* =====================================================================
 * §2 协议原语
 * ===================================================================== */
static int lead_trail_ok(uint8_t lead, uint8_t trail)
{
    if (lead >= 0xFA || trail >= 0xFA)
        return 0;
    if (lead < 0x01 || lead > 0x1E)
        return 0;
    if (lead == 0x06 || lead == 0x1B)
        return 0;
    return 1;
}

static uint16_t pack_glyph_index(uint8_t lead, uint8_t trail)
{
    uint32_t idx = lead;
    if (idx >= 6) {
        if (idx >= 0x1B)
            idx -= 1;
        idx -= 1;
    }
    idx -= 1;
    return (uint16_t)((idx << 8) | trail);
}

/* =====================================================================
 * §3 相位槽（按窗+文本流绑定；tm0/tm1 各自独立的行状态）
 * ===================================================================== */
static uint8_t CaptureBaseTileX(TextPrinter *win)
{
    return win_u8(win, WIN_CURSOR_TILE_X);
}

static volatile struct ChineseTileState *BindPitchSlot(TextPrinter *win, int *out_is_new)
{
    volatile struct ChsPitchCtrl *ctrl =
        (volatile struct ChsPitchCtrl *)ADDR_CHS_PITCH_CTRL;
    volatile struct ChineseTileState *slots =
        (volatile struct ChineseTileState *)ADDR_CHS_PITCH_SLOTS;
    uint8_t *tpl = win_template(win);
    uint8_t char_base = tpl ? tpl[1] : 0;
    uint16_t key = PitchKey(win);
    unsigned i;
    unsigned best;
    uint8_t best_age;
    uint8_t gen;

    if (out_is_new)
        *out_is_new = 0;

    for (i = 0; i < CHS_PITCH_SLOT_COUNT; i++) {
        if (slots[i].pitch_key == key && SLOT_CHAR_BASE(slots + i) == char_base) {
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

    SLOT_SET_CHAR_BASE(&slots[best], char_base);
    slots[best].write_op = 0;
    SLOT_SET_BASE_TX(&slots[best], CaptureBaseTileX(win));
    SLOT_SET_ADV12(&slots[best], 1);
    slots[best].scratch_tx = 0xFFu;         /* 未分配哨兵：首绘时切起始偏移 */
    slots[best].tiles_drawn = 0;
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

static void PitchReset(TextPrinter *win)
{
    volatile struct ChineseTileState *st = BindPitchSlot(win, 0);
    st->chs_px = 0;
    SLOT_SET_BASE_TX(st, CaptureBaseTileX(win));
}

/* =====================================================================
 * §4 像素件
 * ===================================================================== */
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

static uint8_t *vram_tile(TextPrinter *win, uint16_t tile)
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

/* =====================================================================
 * §5 GetGlyph —— 字形源统一解析（每字形字体属性）
 * ===================================================================== */

/* CHS 汉库字模取址（内部专用；旧 Hook3/P02 外部分发已移除）。
 * glyph：低 15 位 = 字模号（CHS_GLYPH_IDX_MASK），bit15 = 右半（TR/BR），
 * 其余标志位（GLYPH_SRC_CHS 等）被掩码忽略。返回一对 32B tile：
 * 左半 → TL/BL，右半（+64B）→ TR/BR。队伍名等 fn4 窗走 Small 库。 */
static void GetGlyphTilePointers(uint8_t fontNum, uint32_t glyph,
                                 uint8_t **upperTilePtr, uint8_t **lowerTilePtr)
{
    /* 队伍名等 fn4 窗 = FontChsSmall；常规 = FontChsNormal（与 GetGlyph 同源） */
    const uint8_t *base = (fontNum == 4u) ? (const uint8_t *)ADDR_FONT_CHS_SMALL
                                          : (const uint8_t *)ADDR_FONT_CHS_NORMAL;

    base += (uint32_t)(glyph & CHS_GLYPH_IDX_MASK) << 7;
    if (glyph & CHS_GLYPH_HALF_BIT)
        base += 64u;
    *upperTilePtr = (uint8_t *)base;
    *lowerTilePtr = (uint8_t *)base + 32u;
}

static int GetGlyph(TextPrinter *win, uint32_t code, uint8_t *out128, uint8_t *outWidth)
{
    uint8_t fontNum = win_u8(win, WIN_FONTNUM_REAL);
    if (fontNum > 6u)
        fontNum = 3u;    /* bak DrawGlyph_JP_ViaCHS 钳制：非法 fontNum 回落 font3 */

    /* ---- CHS 汉库（128B 容器同构：TL,BL | TR,BR 各 64B） ---- */
    if (code & GLYPH_SRC_CHS) {
        uint8_t *up;
        uint8_t *lo;
        GetGlyphTilePointers(fontNum, code, &up, &lo);
        copy_tile32(out128 + 0x00, up);
        copy_tile32(out128 + 0x20, lo);
        GetGlyphTilePointers(fontNum, code | CHS_GLYPH_HALF_BIT, &up, &lo);
        copy_tile32(out128 + 0x40, up);
        copy_tile32(out128 + 0x60, lo);
        *outWidth = (fontNum == 4u) ? 8u : 12u;
        return 1;
    }

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

/* =====================================================================
 * §6 渲染件：单 tile 合成（归一化源 → 窗口 C/E/D 终色）
 * ===================================================================== */
static void DrawGlyphTile_ShadowedFont(
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

    /* 着色在渲染层（pokeruby ApplyColors 位于渲染侧）：
     * CopyGlyph(C,E,D): 15→ink, 14→shadow, 0→bg */
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

/* =====================================================================
 * §6b tm0 Linear 核心（TILE_OFF 连续光栅；floor=4；无 UI 重映射——
 * tm0 场景（对话 0x90 起/详情页 0x290 起）实测不与保留带重叠）
 * ===================================================================== */
static uint16_t GetCursorTileNum(
    TextPrinter *win, unsigned xOffset, unsigned yOffset)
{
    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    return (uint16_t)(tile_base + off + 2u * xOffset + yOffset);
}

/* pokeruby WriteGlyphTilemap：cursor 格落一对表项（upperTileNum/lowerTileNum）；
 * tx 为像素制游标折算出的 tile 列（CHS 相位槽承载，原生无此参）。 */
static void WriteGlyphTilemap(TextPrinter *win, uint8_t tx, uint16_t upperTileNum,
                              uint16_t lowerTileNum)
{
    win_set_u8(win, WIN_CURSOR_TILE_X, tx);
    UpdateTilemap_Origin(win, upperTileNum, lowerTileNum);
}

static void DrawGlyphTiles(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned linear,
    unsigned glyphWidth)
{
    (void)linear;    /* tm0 恒 Linear（网格语义归 tm1/tm3 共用行） */
    volatile struct ChineseTileState *st = BindPitchSlot(win, 0);
    unsigned startPixel;
    unsigned w2;
    uint16_t off, up0, lo0;
    uint8_t map_tx;
    struct GlyphTileInfo info;

    if (glyphWidth < 8u)
        glyphWidth = 8u;
    if (glyphWidth > 12u)
        glyphWidth = 12u;

    if (st->chs_px == 0) {
        SLOT_SET_BASE_TX(st, CaptureBaseTileX(win));
        /* bak ensure_linear_dest_floor 基础下限：tm0 空白 tile = TILE_BASE+0，
         * OFF<4 时首字形会踩掉空白对（之后清屏/翻页把碎片当背景铺出）。 */
        {
            uint16_t off0 = win_u16(win, WIN_TILE_OFFSET);
            if (off0 < 4u)
                win_set_u16(win, WIN_TILE_OFFSET, 4u);
        }
    }

    startPixel = (unsigned)(st->chs_px & 7u);
    map_tx = (uint8_t)(SLOT_BASE_TX(st) + (st->chs_px >> 3));

    info.textMode = 0;
    info.colors = 0;

    /* ---- 第一趟：宽 8（TL/BL，startPixel>0 时 spill 到右邻） ---- */
    off = win_u16(win, WIN_TILE_OFFSET);
    up0 = GetCursorTileNum(win, 0, 0);
    lo0 = GetCursorTileNum(win, 0, 1);
    info.startPixel = (uint8_t)startPixel;
    info.width = 8;
    info.src = tiles->tl;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, up0);
    if (startPixel > 0u)
        DrawGlyphTile_ShadowedFont(win, &info, (uint8_t *)(uintptr_t)vram_tile(win, up0 + 2));
    else
        DrawGlyphTile_ShadowedFont(win, &info, 0);
    info.src = tiles->bl;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, lo0);
    if (startPixel > 0u)
        DrawGlyphTile_ShadowedFont(win, &info, (uint8_t *)(uintptr_t)vram_tile(win, lo0 + 2));
    else
        DrawGlyphTile_ShadowedFont(win, &info, 0);
    WriteGlyphTilemap(win, map_tx, up0, lo0);
    win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));

    st->chs_px = (uint16_t)(st->chs_px + 8u);

    w2 = (glyphWidth > 8u) ? (glyphWidth - 8u) : 0u;
    if (w2 == 0u) {
        SLOT_SET_ADV12(st, glyphWidth == 12u);
        win_set_u8(win, WIN_CURSOR_TILE_X,
            (uint8_t)(SLOT_BASE_TX(st) + ((st->chs_px + glyphWidth - 1) >> 3)));
        return;
    }

    map_tx = (uint8_t)(SLOT_BASE_TX(st) + (st->chs_px >> 3));

    /* ---- 第二趟：宽 w2（TR/BR）——startPixel 复用第一趟相位（bak 同款）：
     * TR 写在本列 [startPixel, +w2)，与第一趟 spill [0,startPixel) 拼满
     * 整列；置 0 会覆盖 spill → 相位 4 的字隔字错乱。 ---- */
    off = win_u16(win, WIN_TILE_OFFSET);
    up0 = GetCursorTileNum(win, 0, 0);
    lo0 = GetCursorTileNum(win, 0, 1);
    info.width = (uint8_t)w2;
    info.src = tiles->tr;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, up0);
    DrawGlyphTile_ShadowedFont(win, &info, 0);
    info.src = tiles->br;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, lo0);
    DrawGlyphTile_ShadowedFont(win, &info, 0);
    WriteGlyphTilemap(win, map_tx, up0, lo0);
    /* bak 同款：相位 0 时第二趟落在第一趟推进后的列内（下一字形从同列
     * 相位 4 续接，不再推进）；相位 >0 时第二趟耗尽当前列（下一字形相位 0
     * 需新列，+2）。写反会导致 12px 序列逐字错位、互相啃食。 */
    win_set_u16(win, WIN_TILE_OFFSET,
                (uint16_t)(off + ((startPixel == 0u) ? 0u : 2u)));

    st->chs_px = (uint16_t)(st->chs_px + w2);
    SLOT_SET_ADV12(st, glyphWidth == 12u);
    win_set_u8(win, WIN_CURSOR_TILE_X,
        (uint8_t)(SLOT_BASE_TX(st) + ((st->chs_px + glyphWidth - 1) >> 3)));
}

/* =====================================================================
 * §6c 表项写入分发（sWriteGlyphTilemapFuncs[fontNum]）
 * 已验证 fn3/fn4 = cursor 格成对写；未验证 fontNum → UNKNOWN 不写。
 * ===================================================================== */
typedef void (*WriteGlyphTilemapFunc)(TextPrinter *, uint16_t, uint16_t);

static void WriteGlyphTilemap_Unknown(TextPrinter *win, uint16_t up, uint16_t lo)
{
    (void)win;
    (void)up;
    (void)lo;    /* UNKNOWN：不写（缺字排查信号） */
}

static void WriteGlyphTilemap_Font3_Font4(TextPrinter *win, uint16_t up, uint16_t lo)
{
    UpdateTilemap_Origin(win, up, lo);
}

static const WriteGlyphTilemapFunc sWriteGlyphTilemapFuncs[8] = {
    WriteGlyphTilemap_Unknown,   /* 0：未观测 */
    WriteGlyphTilemap_Unknown,   /* 1：未观测 */
    WriteGlyphTilemap_Unknown,   /* 2：未观测 */
    WriteGlyphTilemap_Font3_Font4,   /* 3：对话/菜单/详情页（gdb 实证） */
    WriteGlyphTilemap_Font3_Font4,   /* 4：队伍名（gdb 实证） */
    WriteGlyphTilemap_Unknown,   /* 5 */
    WriteGlyphTilemap_Unknown,   /* 6 */
    WriteGlyphTilemap_Unknown,   /* 7 */
};

/* =====================================================================
 * §8 CHS scratch 分配（页游标制；pokeruby tm0「分区内顺序游标」结构，
 * 游标按页（tilemap）记账——同页块 disjoint，异页互斥显示共享区间）
 * ===================================================================== */

/* 自由区表（gdb 两轮采集实测，README §10.4；charBlock 绝对 tile 号，
 * TILE_BASE 恒 1——若未来出现 ≠1 的窗体需改 base 相对寻址）：
 *  cb=1（font4 队伍窗）：font4 预渲染区 [2,0xD6]（FontType1Map max=212，
 *   (1,4) PCS 原生表项指向它）+ 原生数字映射 [0x74,0xD5] + 图标章
 *   [0x14C-0x151]/[0x18C-0x19B] 均不可碰 → [0xD7,0x14B]（117 tile）。
 *  cb=2（font3 菜单/对话/图鉴/能力页）：能力页场景自加载字库
 *   LZ→0x06008000（tile [0x00,0x100)，不走 InitWindowTileData）+ 场景映射
 *   [0x1C9,0x1F7] + ▶/UI 章 → 公共自由区 [0x100,0x1C8]（201 tile ≈ 50 字/屏）。
 *  cb=0（弹窗/对话）：现状保留 [0x101,0x1AB]（地图 tileset 共存未明）。 */
static void GlyphScratchRange(TextPrinter *win, uint16_t *lo, uint16_t *hi)
{
    uint8_t *tpl = win_template(win);
    uint8_t cb = tpl ? tpl[1] : 0;
    switch (cb) {
    case 1:
        *lo = 0x00D7u;
        *hi = 0x014Bu;
        break;
    case 2:
        *lo = 0x0100u;
        *hi = 0x01C8u;
        break;
    default:
        *lo = 0x0101u;
        *hi = 0x01ABu;
        break;
    }
}

/* 页游标表：{u16 tilemap_lo, u16 cursor} × 8 @ ADDR_GLYPH_PAGE_CURTAB。
 * 同 tilemap（同页/同窗体）的块顺序 disjoint；异页共享同一自由区——
 * 页互斥显示（切页换 tilemap），互相覆盖不可见；页重入游戏重印 → 重绘自愈。
 * 扫描实证 0x0203FFD2-0x0203FFF7 无游戏字面量引用（FFD0/D1 为调色板覆盖）。 */
#define GLYPH_PAGE_N 8u

static uint16_t GlyphPageCur(uint16_t tmap_lo, uint16_t span, unsigned n)
{
    volatile uint16_t *tab = (volatile uint16_t *)ADDR_GLYPH_PAGE_CURTAB;
    volatile struct ChsPitchCtrl *ctrl =
        (volatile struct ChsPitchCtrl *)ADDR_CHS_PITCH_CTRL;
    unsigned i, free_i = GLYPH_PAGE_N;
    for (i = 0; i < GLYPH_PAGE_N; i++) {
        if (tab[i * 2u] == tmap_lo) {
            uint16_t cur = tab[i * 2u + 1u];
            if ((uint16_t)(cur + n) > span)
                cur = 0;                        /* 页内回绕（页容量边界） */
            tab[i * 2u + 1u] = (uint16_t)(cur + n);
            return cur;
        }
        if (tab[i * 2u] == 0u && free_i == GLYPH_PAGE_N)
            free_i = i;
    }
    if (free_i == GLYPH_PAGE_N) {               /* 表满：轮替驱逐（gen 计数轮转，
                                                 * 禁用 static——game.bin 无 .bss 初始化，
                                                 * 静态变量首读=ROM 垃圾→越界写崩溃） */
        free_i = (unsigned)(ctrl->gen % GLYPH_PAGE_N);
    }
    tab[free_i * 2u] = tmap_lo;
    tab[free_i * 2u + 1u] = (uint16_t)(n > span ? span : n);
    return 0;                                   /* 新页从区首画 */
}

/* 槽记帐分配（⚠️ 2026-08-25 深夜回退定案：页游标表 @0x0203FFD2 引入
 * 背包/队伍进入黑屏（rr 静态修复后依旧，疑似该区游戏数据冲突），
 * 回退到全局单游标 + §10.4 自由区表 = 7732 基线（全部测试无崩溃）。
 * 已知遗留：菜单重入/能力页多页容量回绕互踩（页游标表待专轮排查后再启）。
 * GlyphPageCur/GlyphPageReset/InitWindowTileData_Hook 保留但停用
 * （P24 桩已断开）。 */
static uint16_t GlyphScratchAlloc(TextPrinter *win, unsigned n)
{
    uint8_t *tpl = win_template(win);
    uint8_t cb = tpl ? tpl[1] : 0;
    uint16_t lo, hi;
    /* 自由区表（gdb 两轮采集实测，README §10.4；charBlock 绝对 tile 号，
     * TILE_BASE 恒 1）：
     *  cb=1（font4 队伍窗）：font4 预渲染区 [2,0xD6] + 原生数字映射
     *   [0x74,0xD5] + 图标章 [0x14C-0x151]/[0x18C-0x19B] → [0xD7,0x14B]。
     *  cb=2（font3 菜单/对话/图鉴/能力页）：能力页自加载字库 [0x00,0x100)
     *   + 场景映射 [0x1C9,0x1F7] + ▶/UI 章 → [0x100,0x1C8]。
     *  cb=0（弹窗/对话）：现状保留 [0x101,0x1AB]。 */
    if (cb == 1) {
        lo = 0x0102u;                       /* 258：框体图形区 [0,257) 之上
                                             * （旧池 [0x101,0x1FB] 跨全部测试
                                             * 框体无损=实证），图标章 0x14C 之下 */
        hi = 0x014Bu;
    } else if (cb == 2) {
        lo = 0x0100u;
        hi = 0x01C8u;
    } else {
        lo = 0x0101u;
        hi = 0x01ABu;
    }
    {
        uint16_t cur = *(volatile uint16_t *)ADDR_GLYPH_ALLOC_NEXT;
        if (cur < lo || (uint16_t)(cur + n - 1u) > hi)
            cur = lo;                           /* 越区回卷（容量边界） */
        *(volatile uint16_t *)ADDR_GLYPH_ALLOC_NEXT = (uint16_t)(cur + n);
        return cur;
    }
}

/* 页游标复位：窗体初始化（字库预渲染）= 该页旧文本作废 → 游标归零。
 * 下一次分配从自由区首切带，跨场景累积清零。 */
static void GlyphPageReset(uint16_t tmap_lo)
{
    volatile uint16_t *tab = (volatile uint16_t *)ADDR_GLYPH_PAGE_CURTAB;
    unsigned i;
    for (i = 0; i < GLYPH_PAGE_N; i++)
        if (tab[i * 2u] == tmap_lo)
            tab[i * 2u + 1u] = 0;
}

/* 分区器钩子（XXX_Hook，经 entry.s GlyphIwtdTramp 跳板进入）：
 * a0 = 模板指针（ROM）。只做页游标复位——原版函数体由跳板回退执行
 * （重执行被覆盖的 4 条 prologue 指令后落回 0x2A58）。
 * 多帧加载器每帧调用一次（每窗 256 次），复位幂等廉价。 */
void InitWindowTileData_Hook(uint32_t a0)
{
    const uint8_t *t = (const uint8_t *)a0;
    if (t != 0) {
        uint16_t tmap_lo = (uint16_t)(*(volatile uint32_t *)(t + 0x10));
        GlyphPageReset(tmap_lo);
    }
}

/* =====================================================================
 * §9 打印行（sPrintGlyphFuncs 一行一语义）
 * ===================================================================== */

/* ---- tm0：FontFunc[0] Linear 滚动光栅（对话/战斗文本/详情页字段）----
 * 像素写 TILE_BASE+TILE_OFF 连续区（原生字段，ITP 清零=每打印新区域），
 * UpdateTilemap 写 cursor 格；12px 汉字 nCols=2、8px 日文 nCols=1。 */
static void PrintGlyph_TextMode0(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    int slot_new = 0;
    volatile struct ChineseTileState *st;
    uint8_t cur_tx;
    unsigned last;
    int newline_reset = 0;

    st = BindPitchSlot(win, &slot_new);
    cur_tx = win_u8(win, WIN_CURSOR_TILE_X);

    if (slot_new && st->chs_px == 0)
        newline_reset = 1;

    if (st->chs_px != 0 && cur_tx <= SLOT_BASE_TX(st)) {
        st->chs_px = 0;
        SLOT_SET_BASE_TX(st, CaptureBaseTileX(win));
        newline_reset = 1;
    } else if (st->chs_px != 0) {
        last = SLOT_LAST_ADV(st);
        {
            uint8_t expect = (uint8_t)(SLOT_BASE_TX(st) + ((st->chs_px + last - 1) >> 3));
            if (cur_tx != expect) {
                st->chs_px = 0;
                SLOT_SET_BASE_TX(st, CaptureBaseTileX(win));
                newline_reset = 1;
            }
        }
    } else {
        SLOT_SET_BASE_TX(st, CaptureBaseTileX(win));
    }

    if (newline_reset) {
        uint16_t off = win_u16(win, WIN_TILE_OFFSET);
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
    }

    DrawGlyphTiles(win, tiles, 1, glyphWidth);
}

/* ---- tm1/tm3：等宽（保留区像素 + cursor 格表项）----
 * 12px 汉字 = 2 列表项 + 1.5 列步进（半列相位由 pitch 槽 chs_px 承载，
 * 下一字形自动从半列续接）；8px 日文 = 1 列表项 + 整列步进（相位对齐）。
 * 不读写 TILE_OFFSET（tm0 专属状态，行间隔离）。
 * 两趟几何（bak DrawGlyphTiles_CHS_Core 同款）：第一趟 TL/BL 恒宽 8
 * @startPixel（跨列 spill → 保留区第 2 对）；第二趟 TR/BR 恒宽 w-8、
 * startPixel 复用（写第 2 对 [startPixel,+w2)，与 spill [0,startPixel)
 * 拼满整列）；8px 字形仅第一趟，行尾半列 spill 亦落表项。 */
static void PrintGlyph_TextMode1(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    volatile struct ChineseTileState *st;
    uint8_t cur_tx;
    unsigned w, startPixel, w2, spilled;
    uint16_t t, u1, l1, u2, l2;
    uint8_t fontNum = win_u8(win, WIN_FONTNUM_REAL) & 7u;
    struct GlyphTileInfo info;

    if (glyphWidth < 8u)
        glyphWidth = 8u;
    if (glyphWidth > 12u)
        glyphWidth = 12u;
    w = glyphWidth;

    st = BindPitchSlot(win, 0);
    cur_tx = win_u8(win, WIN_CURSOR_TILE_X);

    /* 相位失配检测（bak PrintGlyph_Common_CHS 三重守卫的前两重）：
     * 1) ITP 重印已将 cursor 归零而 chs_px 未清（A切B再切A）→ 重置；
     * 2) cursor 跳到既非行首也非期望点的位置（菜单重绘/SetCursorX 换列）
     *    → 带陈旧相位继续画会半字错列，重置（tm1 不用 TILE_OFFSET，
     *    无 OFF 副作用；与 tm0 行同款）。 */
    if (st->chs_px != 0 && cur_tx <= SLOT_BASE_TX(st)) {
        st->chs_px = 0;
        st->tiles_drawn = 0;
        SLOT_SET_BASE_TX(st, cur_tx);
    } else if (st->chs_px != 0) {
        unsigned last = SLOT_LAST_ADV(st);
        uint8_t expect = (uint8_t)(SLOT_BASE_TX(st) + ((st->chs_px + last - 1) >> 3));
        if (cur_tx != expect) {
            st->chs_px = 0;
            st->tiles_drawn = 0;
            SLOT_SET_BASE_TX(st, cur_tx);
        }
    }
    if (st->chs_px == 0)
        SLOT_SET_BASE_TX(st, cur_tx);

    startPixel = st->chs_px & 7u;
    /* bak 同款切分：第一趟恒宽 8，第二趟恒宽 w-8。不可按相位收缩第一趟——
     * 那会画错字节段（相位 4 时需要 TL[4,8) 却画成 TL[0,4)），第二趟还会
     * 以 8px 全覆盖抹掉 spill → 相位 4 的字全部水平错乱。 */
    w2 = (w > 8u) ? (w - 8u) : 0u;
    spilled = (startPixel > 0u);

    /* 共享列（bak 原地合成语义）：startPixel>0 ⇒ 首列即上一字形溢出列。
     * 槽记帐下流内分配严格顺序（恒 4 tile/字），上一字形溢出对 = t-2/-1：
     * pass1 在该对上 RMW 合成，[0,startPixel) 保留上一字右半像素。 */
    t = GlyphScratchAlloc(win, 4u);         /* 恒 4：首列对 + 溢出列对 */

    if (spilled) {
        u1 = (uint16_t)(t - 2u);
        l1 = (uint16_t)(t - 1u);
    } else {
        u1 = t;
        l1 = (uint16_t)(t + 1u);
        /* 表项：首列 cursor 格（仅全新列需要映射；共享列已指向 u1/l1） */
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(SLOT_BASE_TX(st) + (st->chs_px >> 3)));
        sWriteGlyphTilemapFuncs[fontNum](win, u1, l1);
    }
    u2 = (uint16_t)(t + 2u);
    l2 = (uint16_t)(t + 3u);

    info.textMode = 0;
    info.colors = 0;
    info.startPixel = (uint8_t)startPixel;
    info.width = 8;

    /* 第一趟：TL/BL 宽 8（跨列 spill 到新溢出对） */
    info.src = tiles->tl;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, u1);
    DrawGlyphTile_ShadowedFont(win, &info, spilled ? (uint8_t *)(uintptr_t)vram_tile(win, u2) : 0);
    info.src = tiles->bl;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, l1);
    DrawGlyphTile_ShadowedFont(win, &info, spilled ? (uint8_t *)(uintptr_t)vram_tile(win, l2) : 0);

    st->chs_px = (uint16_t)(st->chs_px + 8u);

    if (w2 == 0u) {
        /* 8px 字形（日文）：行尾半列 spill 也要落表项（bak 同款），
         * 否则右半像素落在无表项的列上 → 丢半边。 */
        if (spilled) {
            win_set_u8(win, WIN_CURSOR_TILE_X,
                       (uint8_t)(SLOT_BASE_TX(st) + (st->chs_px >> 3)));
            sWriteGlyphTilemapFuncs[fontNum](win, u2, l2);
        }
        SLOT_SET_ADV12(st, w == 12u);
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(SLOT_BASE_TX(st) + ((st->chs_px + w - 1) >> 3)));
        return;
    }

    /* 第二趟：TR/BR 宽 w-8，startPixel 复用（写第 2 对的
     * [startPixel, +w2)，与第一趟 spill [0,startPixel) 拼满整列） */
    info.width = (uint8_t)w2;
    info.src = tiles->tr;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, u2);
    DrawGlyphTile_ShadowedFont(win, &info, 0);
    info.src = tiles->br;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, l2);
    DrawGlyphTile_ShadowedFont(win, &info, 0);
    /* 表项：溢出列 cursor+1 格 */
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(SLOT_BASE_TX(st) + (st->chs_px >> 3)));
    sWriteGlyphTilemapFuncs[fontNum](win, u2, l2);

    /* 相位推进 + cursorTileX 同步（像素制，Field 同款公式） */
    st->chs_px = (uint16_t)(st->chs_px + w2);
    SLOT_SET_ADV12(st, w == 12u);
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(SLOT_BASE_TX(st) + ((st->chs_px + w - 1) >> 3)));
}

/* ---- tm2：指针缓冲（占位）----
 * FontFunc[2]/RenderTextHandleBold@0x02CC0 语义（组色写 [win+0x20]、步进
 * 0x40）已 RE 定案；【幻影守卫】战斗/槽位数字经 0x02CFC 包装从不设
 * win[0x20]（恒 0，原生写 0=BIOS 忽略）——跳过即与原生一致。
 * 【待办】真实缓冲渲染待 battle_interface/summary 渲染链研究后启用。 */
static void PrintGlyph_TextMode2(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    (void)win;
    (void)tiles;
    (void)glyphWidth;
}

/* ---- UNKNOWN：未验证组合——消费、无绘制（缺字排查信号） ---- */
static void PrintGlyph_Unknown(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    (void)win;
    (void)tiles;
    (void)glyphWidth;
}

/* ---- 分发表 ---- */
typedef void (*PrintGlyphFunc)(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth);

static const PrintGlyphFunc sPrintGlyphFuncs[8] = {
    PrintGlyph_TextMode0,   /* 0：Linear 滚动光栅 */
    PrintGlyph_TextMode1,   /* 1：等宽（保留区 + cursor 格表项） */
    PrintGlyph_TextMode2,   /* 2：缓冲（占位） */
    PrintGlyph_TextMode1,   /* 3：对话主窗（高频；网格对 CHS 同构） */
    PrintGlyph_Unknown,     /* 4：UNKNOWN */
    PrintGlyph_Unknown,     /* 5：UNKNOWN */
    PrintGlyph_Unknown,     /* 6：UNKNOWN */
    PrintGlyph_Unknown,     /* 7：UNKNOWN */
};
#define PRINT_GLYPH_MODES 8u

/* =====================================================================
 * §11 单字节分发（PCS 两级表，镜像原生 sPrintGlyphFuncs × sWriteGlyphTilemapFuncs）
 * ===================================================================== */
typedef void (*PcsPrintFunc)(TextPrinter *win, uint32_t glyph);

/* 自绘：GetGlyph 取字模 → 既有 sPrintGlyphFuncs[textMode]（原逻辑不动；
 * CHS/SYM 亦经此）。 */
static void PcsPrint_Custom(TextPrinter *win, uint32_t cur_char)
{
    uint8_t buf[128];
    uint8_t width = 8;
    struct ChsGlyphTiles t;
    unsigned m = win_u8(win, WIN_TEXTMODE);

    if (!GetGlyph(win, cur_char, buf, &width))
        return;                         /* 引擎零回落：不可印位直接消费 */
    t.tl = buf + 0x00;
    t.bl = buf + 0x20;
    t.tr = buf + 0x40;
    t.br = buf + 0x60;
    if (m >= PRINT_GLYPH_MODES)
        m = 0;
    sPrintGlyphFuncs[m](win, &t, width);
}

/* 第二级 [fontNum]，镜像原生 sWriteGlyphTilemapFuncs——每格对应日志实证窗口：
 *  [4]=PrintGlyph_TextMode1_Origin 队伍名窗 0x081BB43C（charBase1）：font4 走
 *                FontType1Map 紧凑区 [TILE_BASE,+0xD5]，在 CHS scratch 带
 *                [0xD7,0x14B] 下方，原生表项指向的 tile 完好（gdb 实证；
 *                ♂/♀/Lv/状态图标 0x14C-0x151/0x18C-0x19B 不再被覆写）。
 *  [3]=Custom    弹窗 0x081BB49C（charBase0）/请选择 0x081BB484：font3 线性
 *                区 [1,0x1BC] 与 scratch 带重叠（数字 0xA2→tile0x145，208 处实证）。
 *  [1]=Custom    无实证，默认安全（原生同为紧凑区，将来可切 Origin）。
 *  其余=Custom。 */
static const PcsPrintFunc sPcsTm1FontFuncs[8] = {
    PcsPrint_Custom,       /* font0 */
    PcsPrint_Custom,       /* font1：无实证，默认自绘 */
    PcsPrint_Custom,       /* font2 */
    PcsPrint_Custom,       /* font3：线性区与 scratch 带重叠 */
    PrintGlyph_TextMode1_Origin,    /* font4：FontType1Map 区在 scratch 带下方 */
    PcsPrint_Custom,       /* font5 */
    PcsPrint_Custom,       /* font6 */
    PcsPrint_Custom,       /* font7 */
};

static void PcsPrint_Tm1(TextPrinter *win, uint32_t cur_char)
{
    sPcsTm1FontFuncs[win_u8(win, WIN_FONTNUM_REAL) & 7u](win, cur_char);
}

/* 第一级 [textMode]，镜像原生 sPrintGlyphFuncs：
 *  [1]=Tm1      二级查 fontNum（上表）。
 *  [3]=Custom   菜单/对话 0x081BB46C：原生 tm3 = FontFuncTable[3]@0x08003494
 *               另一策略未 RE；上版误派 tm1 函数致数字/假名蓝块（140 处实证）。
 *  其余=Custom（tm0/tm2 自绘，已验证）。 */
static const PcsPrintFunc sPcsPrintFuncs[8] = {
    PcsPrint_Custom,       /* 0：tm0 自绘 */
    PcsPrint_Tm1,          /* 1：二级查 fontNum */
    PcsPrint_Custom,       /* 2：tm2 占位 */
    PcsPrint_Custom,       /* 3：tm3 自绘（原生 tm3 未 RE） */
    PcsPrint_Custom,       /* 4 */
    PcsPrint_Custom,       /* 5 */
    PcsPrint_Custom,       /* 6 */
    PcsPrint_Custom,       /* 7 */
};

static int DrawGlyph(TextPrinter *win, uint32_t cur_char)
{
    /* CHS 标点 SYM 带走自绘（自建 sym 字库）；≥0xF7 不可印位直接消费。
     * 其余按 textMode（tm1 再查 fontNum）两级表分发。 */
    if (cur_char >= SYM_GLYPH_BASE
        && cur_char < SYM_GLYPH_BASE + SYM_GLYPH_COUNT) {
        PcsPrint_Custom(win, cur_char);
        return 1;
    }
    if (cur_char >= 0xF7u)
        return 1;
    sPcsPrintFuncs[win_u8(win, WIN_TEXTMODE) & 7u](win, cur_char);
    return 1;
}

/* F9 汉字：gidx 经 GetGlyph（CHS 汉库，宽度随 fontNum 8/12）产出后进分发。
 * glyphWidth 形参仅为兼容旧签名——实际宽度以 GetGlyph 返回为准。 */
static void PrintGlyph(TextPrinter *win, uint32_t gidx, unsigned glyphWidth)
{
    uint8_t buf[128];
    uint8_t width = 8;
    struct ChsGlyphTiles t;

    (void)glyphWidth;
    if (!GetGlyph(win, GLYPH_SRC_CHS | (gidx & CHS_GLYPH_IDX_MASK), buf, &width))
        return;
    t.tl = buf + 0x00;
    t.bl = buf + 0x20;
    t.tr = buf + 0x40;
    t.br = buf + 0x60;
    {
        unsigned m = win_u8(win, WIN_TEXTMODE);
        if (m >= PRINT_GLYPH_MODES)
            m = 0;
        sPrintGlyphFuncs[m](win, &t, width);
    }
}

/* =====================================================================
 * §12 F9 协议
 * ===================================================================== */
static const uint8_t *phrase_stream_lookup(uint16_t code)
{
    const uint32_t *offsets = (const uint32_t *)ADDR_PHRASE_OFFSETS;
    const uint8_t *table = (const uint8_t *)ADDR_PHRASE_TABLE;
    uint32_t off = offsets[code];

    if (off >= 0x01000000u)
        return 0;
    return table + off;
}

static int phrase_stream_no_wait_controls(const uint8_t *stream)
{
    unsigned i = 0;

    if (!stream)
        return 0;
    while (stream[i] != 0xFF) {
        if (stream[i] == CHS_ESCAPE) {
            if (stream[i + 1] != 0)
                return 0;
            i += 4;
            if (i > 256u)
                return 0;
            continue;
        }
        if (stream[i] >= 0xFAu)
            return 0;
        i++;
    }
    return 1;
}

static int phrase_parent_continues(const uint8_t *text, uint16_t index)
{
    return text[index + 3] != 0xFF;
}

static int inline_phrase_no_controls(TextPrinter *win, uint16_t index, uint16_t code)
{
    const uint8_t *stream = phrase_stream_lookup(code);
    unsigned i = 0;
    unsigned n = 0;

    if (!stream || !phrase_stream_no_wait_controls(stream))
        return 0;

    while (stream[i] != 0xFF) {
        if (stream[i] == CHS_ESCAPE && stream[i + 1] == 0) {
            uint8_t lead = stream[i + 2];
            uint8_t trail = stream[i + 3];
            uint16_t gidx;
            if (!lead_trail_ok(lead, trail))
                return 0;
            gidx = pack_glyph_index(lead, trail);
            if (gidx < CHS_FONT_GLYPH_MAX)
                PrintGlyph(win, gidx, CHS_GLYPH_ADVANCE_PX);
            i += 4;
        } else {
            if (!DrawGlyph(win, stream[i]))
                return 0;
            i++;
        }
        if (++n > 32u)
            break;
    }
    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 3));
    return 1;
}

static void redirect_phrase_stream(TextPrinter *win, uint16_t code)
{
    const uint8_t *stream = phrase_stream_lookup(code);

    if (!stream)
        return;
    win_set_u32(win, WIN_TEXT_PTR, (uint32_t)(uintptr_t)stream);
    win_set_u16(win, WIN_TEXT_INDEX, 0);
}

/* =====================================================================
 * §13 SlotTable 查找族（'SLT2' 分桶 / legacy 平铺）
 * ===================================================================== */
static uint32_t fnv1a_hash(const uint8_t *data, unsigned len)
{
    uint32_t h = 0x811c9dc5u;
    unsigned i;
    for (i = 0; i < len; i++) {
        h ^= data[i];
        h *= 0x01000193u;
    }
    return h;
}

static uint32_t slot_rd_le32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static int slot_draw_chinese(TextPrinter *win, const uint8_t *chinese,
                             uint16_t next_index)
{
    unsigned ci = 0;

    while (chinese[ci] != 0xFF) {
        if (chinese[ci] == CHS_ESCAPE && chinese[ci + 1] == 0) {
            uint8_t lead = chinese[ci + 2];
            uint8_t trail = chinese[ci + 3];
            uint16_t gidx;
            if (lead_trail_ok(lead, trail)) {
                gidx = pack_glyph_index(lead, trail);
                if (gidx < CHS_FONT_GLYPH_MAX)
                    PrintGlyph(win, gidx, CHS_GLYPH_ADVANCE_PX);
            }
            ci += 4;
        } else {
            DrawGlyph(win, chinese[ci]);
            ci++;
        }
    }
    win_set_u16(win, WIN_TEXT_INDEX, next_index);
    return 1;
}

#define SLOT_TABLE_MAGIC_V2   0x32544C53u  /* 'SLT2' */
#define SLOT_V2_MAX_WINDOW    32u

static int slot_lookup_v2(TextPrinter *win, uint32_t cur_char,
                          const uint8_t *table,
                          const uint8_t *text, uint16_t index)
{
    uint16_t n_buckets = (uint16_t)(table[4] | (table[5] << 8));
    uint16_t max_jp = (uint16_t)(table[6] | (table[7] << 8));
    const uint8_t *offs;
    uint32_t beg, end, i;
    uint8_t stream_buf[SLOT_V2_MAX_WINDOW];
    uint32_t ph[SLOT_V2_MAX_WINDOW + 1];
    unsigned cap;
    unsigned cnt = 0;

    if (n_buckets == 0 || cur_char >= n_buckets || max_jp == 0)
        return 0;
    if (max_jp > SLOT_V2_MAX_WINDOW)
        max_jp = SLOT_V2_MAX_WINDOW;

    offs = table + 8;
    beg = slot_rd_le32(offs + (uint32_t)cur_char * 4u);
    end = slot_rd_le32(offs + (uint32_t)cur_char * 4u + 4u);
    if (beg >= end)
        return 0;

    ph[0] = 0x811c9dc5u;
    {
        int pos = (int)index - 1;
        cap = max_jp;
        while (cnt < cap) {
            uint8_t b = (cnt == 0) ? (uint8_t)cur_char : text[pos + cnt];
            if (b == 0xFF)
                break;
            stream_buf[cnt] = b;
            ph[cnt + 1] = (ph[cnt] ^ b) * 0x01000193u;
            cnt++;
        }
    }
    if (cnt == 0)
        return 0;

    for (i = beg; i < end;) {
        uint16_t len = (uint16_t)(table[i + 4] | (table[i + 5] << 8));
        if (len >= 1u && len <= cnt && slot_rd_le32(table + i) == ph[len]) {
            unsigned k, match = 1;
            for (k = 0; k < len; k++) {
                if (table[i + 6 + k] != stream_buf[k]) {
                    match = 0;
                    break;
                }
            }
            if (match)
                return slot_draw_chinese(
                    win, table + i + 6u + len,
                    (uint16_t)(index - 1 + len));
        }
        i += 6u + len;
        while (i < end && table[i] != 0xFF)
            i++;
        i++;
    }
    return 0;
}

static int slot_lookup_legacy(TextPrinter *win, uint32_t cur_char,
                              const uint8_t *text, uint16_t index)
{
    const uint8_t *table = (const uint8_t *)ADDR_SLOT_TABLE;
    unsigned i = 0;
    uint8_t stream_buf[256];
    uint8_t stream_len = 0;
    unsigned k;

    /* cnt 必须 int：uint8_t 对 sizeof 比较恒真会被编译器删边界 → 回绕死循环 */
    {
        int pos = (int)index - 1;
        int cnt = 0;
        while (cnt < (int)sizeof(stream_buf)) {
            uint8_t b = (cnt == 0) ? (uint8_t)cur_char : text[pos + cnt];
            if (b == 0xFF)
                break;
            stream_buf[cnt] = b;
            cnt++;
        }
        if (cnt > 255)
            cnt = 255;
        stream_len = (uint8_t)cnt;
    }

    if (stream_len == 0)
        return 0;

    while (table[i] != 0 || table[i + 1] != 0 || table[i + 2] != 0 || table[i + 3] != 0) {
        uint32_t entry_key;
        uint16_t entry_len;
        entry_key = (uint32_t)table[i] | ((uint32_t)table[i + 1] << 8)
                  | ((uint32_t)table[i + 2] << 16) | ((uint32_t)table[i + 3] << 24);
        i += 4;
        entry_len = (uint16_t)table[i] | ((uint16_t)table[i + 1] << 8);
        i += 2;

        if (entry_len > 0 && entry_len <= stream_len) {
            uint32_t h = fnv1a_hash(stream_buf, entry_len);
            if (h == entry_key) {
                unsigned match = 1;
                for (k = 0; k < entry_len; k++) {
                    if (table[i + k] != stream_buf[k]) {
                        match = 0;
                        break;
                    }
                }
                if (match)
                    return slot_draw_chinese(
                        win, &table[i + entry_len],
                        (uint16_t)(index - 1 + entry_len));
            }
        }
        i += entry_len;
        while (table[i] != 0xFF)
            i++;
        i++;
    }
    return 0;
}

static int slot_lookup_and_draw(TextPrinter *win, uint32_t cur_char)
{
    const uint8_t *table = (const uint8_t *)ADDR_SLOT_TABLE;
    const uint8_t *text =
        (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    uint16_t index = win_u16(win, WIN_TEXT_INDEX);

    if (cur_char >= 0x100u)
        return 0;

    if (slot_rd_le32(table) == SLOT_TABLE_MAGIC_V2)
        return slot_lookup_v2(win, cur_char, table, text, index);

    return slot_lookup_legacy(win, cur_char, text, index);
}

/* =====================================================================
 * §14 FC 子处理器（sub_8003110 类型 1..16）
 * ===================================================================== */
typedef void (*axv_fn1)(uint32_t a0);
static void axv_play_bgm(uint16_t id) { ((axv_fn1)(ADDR_PLAY_BGM | 1u))(id); }
static void axv_play_se(uint16_t id)  { ((axv_fn1)(ADDR_PLAY_SE | 1u))(id); }
typedef void (*axv_win_fn)(TextPrinter *);
static void axv_clear_window(TextPrinter *win)    { ((axv_win_fn)(ADDR_TEXT_CLEAR_WINDOW | 1u))(win); }

/* =====================================================================
 * §14b 等 A 箭头前置同步（pokeruby text.c DrawInitialDownArrow 同名收敛）
 * ---------------------------------------------------------------------
 * 原 P05 补丁（0x08003F4C 桩 → WaitArrow_Prepare_Hook 跳板）折入本函数：
 *   1) CHS 相位对齐：chs_px 折算 tile 列回写 CURSOR_TILE_X，半列相位
 *      时 TILE_OFFSET +=2（防 FA/FB 翻页双▼，B04）；
 *   2) downArrowCounter 清零（原跳板 strh [r0,#6]，见 game.h
 *      WIN_DOWN_ARROW_COUNTER）；
 *   3) 尾跳原版主体延续点 DrawInitialDownArrow_Body@0x08003DAD——
 *      与旧跳板逐语义一致（跳过原生序言，延续点自含所需状态）。
 * ===================================================================== */
static void DrawInitialDownArrow(TextPrinter *win)
{
    volatile struct ChineseTileState *st;
    uint16_t cols;
    uint16_t off;
    uint8_t want;
    uint8_t cur_tx;

    if (!win)
        return;

    st = BindPitchSlot(win, 0);
    if (st->chs_px) {
        cols = (uint16_t)((st->chs_px + 7u) >> 3);
        want = (uint8_t)(SLOT_BASE_TX(st) + cols);
        cur_tx = win_u8(win, WIN_CURSOR_TILE_X);

        if (cur_tx == 0u && want > 0u) {
            off = win_u16(win, WIN_TILE_OFFSET);
            if (st->chs_px & 7u)
                win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
            PitchReset(win);
        } else {
            win_set_u8(win, WIN_CURSOR_TILE_X, want);
            off = win_u16(win, WIN_TILE_OFFSET);
            if (st->chs_px & 7u)
                win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
            PitchReset(win);
        }
    }

    win_set_u16(win, WIN_DOWN_ARROW_COUNTER, 0);
    ((axv_win_fn)(ADDR_DRAW_INITIAL_DOWN_ARROW_BODY | 1u))(win);
}

static int HandleExtCtrlCode(TextPrinter *win)
{
    const uint8_t *text = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    uint16_t index = win_u16(win, WIN_TEXT_INDEX);
    uint8_t type;
    uint8_t a1;

    if (index >= 0xFFFF)
        return 2;
    type = text[index];
    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 1));

    switch (type) {
    case FC_FG:
        win_set_u8(win, WIN_COLOR_C, text[win_u16(win, WIN_TEXT_INDEX)]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 2;
    case FC_BG:
        win_set_u8(win, WIN_COLOR_D, text[win_u16(win, WIN_TEXT_INDEX)]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 2;
    case FC_SHADOW:
        win_set_u8(win, WIN_COLOR_E, text[win_u16(win, WIN_TEXT_INDEX)]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 2;
    case FC_ALLCOLORS:
        a1 = text[win_u16(win, WIN_TEXT_INDEX)];
        win_set_u8(win, WIN_COLOR_C, a1);
        win_set_u8(win, WIN_COLOR_D, text[win_u16(win, WIN_TEXT_INDEX) + 1]);
        win_set_u8(win, WIN_COLOR_E, text[win_u16(win, WIN_TEXT_INDEX) + 2]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 3));
        return 2;
    case FC_PALETTE:
        win_set_u8(win, WIN_PALETTE, text[win_u16(win, WIN_TEXT_INDEX)]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 2;
    case FC_FONT:
        win_set_u8(win, WIN_FONTNUM_REAL, text[win_u16(win, WIN_TEXT_INDEX)]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 2;
    case FC_DEFAULTFONT: {
        uint8_t *tpl = win_template(win);
        win_set_u8(win, WIN_FONTNUM_REAL, tpl ? tpl[8] : 0);
        return 2;
    }
    case FC_PAUSE:
        win_set_u8(win, WIN_DELAY, text[win_u16(win, WIN_TEXT_INDEX)]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        win_set_u16(win, WIN_STATE, AXV_STATE_PAUSE);
        return 2;
    case FC_WAITBUTTON:
        win_set_u16(win, WIN_STATE, AXV_STATE_WAIT_BUTTON);
        return 2;
    case FC_WAITSOUND:
        win_set_u16(win, WIN_STATE, AXV_STATE_WAIT_SOUND);
        return 2;
    case FC_PLAYBGM: {
        uint8_t lo = text[win_u16(win, WIN_TEXT_INDEX)];
        uint8_t hi = text[win_u16(win, WIN_TEXT_INDEX) + 1];
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 2));
        axv_play_bgm((uint16_t)(lo | (hi << 8)));
        return 2;
    }
    case FC_PLAYSE: {
        uint8_t lo = text[win_u16(win, WIN_TEXT_INDEX)];
        uint8_t hi = text[win_u16(win, WIN_TEXT_INDEX) + 1];
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 2));
        axv_play_se((uint16_t)(lo | (hi << 8)));
        return 2;
    }
    case FC_ESCAPE: {
        uint8_t c = text[win_u16(win, WIN_TEXT_INDEX)];
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        DrawGlyph(win, c);
        return 1;
    }
    case FC_SHIFT_TILE_X:
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X)
                             + text[win_u16(win, WIN_TEXT_INDEX)]));
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 1;
    case FC_SHIFT_TILE_Y:
        win_set_u8(win, WIN_CURSOR_TILE_Y,
                   (uint8_t)(win_u8(win, WIN_CURSOR_TILE_Y)
                             + text[win_u16(win, WIN_TEXT_INDEX)]));
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 1;
    case FC_CLEARWINDOW:
        axv_clear_window(win);
        return 2;
    default:
        return 2;
    }
}

/* =====================================================================
 * §15 主入口（原生 PrintNextChar_Hook 整函数替换）
 * ===================================================================== */
int PrintNextChar_Hook(TextPrinter *win)
{
    uint32_t tptr;
    uint16_t index;
    uint8_t c;

    /* 复刻原生前 8 条指令：u16 回绕推进 + 取字符 */
    index = win_u16(win, WIN_TEXT_INDEX);
    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 1));
    tptr = win_u32(win, WIN_TEXT_PTR);
    c = *(const uint8_t *)(uintptr_t)(tptr + index);

    if (c >= PCS_CTRL_BASE) {
        switch (c) {
        case 0xFA:
            DrawInitialDownArrow(win);
            win_set_u16(win, WIN_STATE, AXV_STATE_WAIT_SCROLL);
            return 2;
        case 0xFB:
            DrawInitialDownArrow(win);
            win_set_u16(win, WIN_STATE, AXV_STATE_WAIT_CLEAR);
            return 2;
        case 0xFC:
            return HandleExtCtrlCode(win);
        case 0xFD:
            win_set_u16(win, WIN_STATE, AXV_STATE_PLACEHOLDER);
            return 2;
        case 0xFE:
            win_set_u16(win, WIN_STATE, AXV_STATE_NEWLINE);
            return 2;
        case 0xFF:
            win_set_u16(win, WIN_STATE, AXV_STATE_END);
            return 0;
        default:
            break;
        }
    }

    if (c == PCS_MENU_CURSOR && win_u8(win, WIN_TEXTMODE) != 2u) {
        if (DrawMenuCursorEF(win))
            return 1;
    }

    /* ---- F9 协议 ---- */
    if (c == CHS_ESCAPE) {
        const uint8_t *text =
            (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
        uint16_t idx2 = win_u16(win, WIN_TEXT_INDEX);
        const uint8_t *p = text + idx2;
        uint8_t op = p[0];

        if (op == 0) {
            uint32_t tp = win_u32(win, WIN_TEXT_PTR);
            if (idx2 == 1
                && (tp < ADDR_PHRASE_TABLE || tp >= ADDR_FONT_CHS_NORMAL))
                BindPitchSlot(win, 0)->write_op = 0;
            {
                uint8_t lead = p[1];
                uint8_t trail = p[2];
                uint16_t gidx;
                if (!lead_trail_ok(lead, trail)) {
                    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx2 + 3));
                    return 1;
                }
                win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx2 + 3));
                gidx = pack_glyph_index(lead, trail);
                if (gidx >= CHS_FONT_GLYPH_MAX)
                    return 1;
                PrintGlyph(win, gidx, CHS_GLYPH_ADVANCE_PX);
                return 1;
            }
        }

        {
            volatile struct ChineseTileState *st = BindPitchSlot(win, 0);
            uint16_t code = (uint16_t)((p[1] << 8) | p[2]);
            int parent_cont = phrase_parent_continues(text, idx2);

            if (op == CHS_PHRASE_DEFAULT || parent_cont)
                st->write_op = 0;
            else
                st->write_op = op;

            if (parent_cont && inline_phrase_no_controls(win, idx2, code))
                return 1;

            redirect_phrase_stream(win, code);
            return 1;
        }
    }

    /* ---- type=slot ---- */
    if (slot_lookup_and_draw(win, c))
        return 1;

    /* ---- 可印字符：GetGlyph → tm 分发 ---- */
    DrawGlyph(win, c);
    return 1;
}

/* =====================================================================
 * §16 内部出口与导出工具
 * （旧过渡出口 WaitArrow_Prepare 已折入 §14b DrawInitialDownArrow；
 *   MapNamePopup_CalcLeftPx 迁至 src/map_name_popup/MapNamePopup_hook.c）
 * ===================================================================== */
static int DrawMenuCursorEF(TextPrinter *win)
{
    uint8_t buf[128];
    uint8_t width = 8;
    uint8_t *du;
    uint8_t *dl;
    struct GlyphTileInfo info;

    if (!win)
        return 0;
    if (!FontIsShadowed(win_u8(win, WIN_FONTNUM_REAL)))
        return 0;

    if (!GetGlyph(win, PCS_MENU_CURSOR, buf, &width))
        return 0;

    du = vram_tile(win, CHS_MENU_CURSOR_TILE);
    dl = vram_tile(win, CHS_MENU_CURSOR_TILE_HI);
    info.textMode = 0;
    info.colors = 0;
    info.startPixel = 0;
    info.width = 8;
    info.dest = (uint32_t *)(uintptr_t)du;
    info.src = buf + 0x00;
    DrawGlyphTile_ShadowedFont(win, &info, 0);
    info.dest = (uint32_t *)(uintptr_t)dl;
    info.src = buf + 0x20;
    DrawGlyphTile_ShadowedFont(win, &info, 0);
    UpdateTilemap_Origin(win, CHS_MENU_CURSOR_TILE, CHS_MENU_CURSOR_TILE_HI);
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
    return 1;
}

/* ---- CHS 文本流像素宽度 ---- */
static uint32_t phrase_width_px(const uint8_t *stream)
{
    uint32_t w = 0;
    uint32_t i = 0;

    if (!stream)
        return CHS_GLYPH_ADVANCE_PX;
    while (i < 256u && stream[i] != 0xFF) {
        uint8_t b = stream[i];
        if (b == CHS_ESCAPE) {
            if (stream[i + 1] == 0)
                w += CHS_GLYPH_ADVANCE_PX;
            i += 4;
            continue;
        }
        if (b >= PCS_CTRL_BASE) {
            i += 1;
            continue;
        }
        w += CHS_GLYPH_ADVANCE_JP_PX;
        i += 1;
    }
    return w;
}

uint32_t GetStringWidth(const uint8_t *buf, uint32_t max_bytes)
{
    uint32_t w = 0;
    uint32_t len = 0;
    const uint32_t *offsets = (const uint32_t *)ADDR_PHRASE_OFFSETS;

    while (len < max_bytes && buf[len] != 0xFF) {
        if (buf[len] == CHS_ESCAPE && len + 3 < max_bytes) {
            uint8_t op = buf[len + 1];
            uint16_t code = (uint16_t)((buf[len + 2] << 8) | buf[len + 3]);
            if (op == 0) {
                w += CHS_GLYPH_ADVANCE_PX;
            } else if (code < 0x2000u) {
                uint32_t off = offsets[code];
                w += (off < 0x01000000u)
                         ? phrase_width_px((const uint8_t *)ADDR_PHRASE_TABLE + off)
                         : CHS_GLYPH_ADVANCE_PX;
            } else {
                w += CHS_GLYPH_ADVANCE_PX;
            }
            len += 4;
        } else if (buf[len] >= PCS_CTRL_BASE) {
            len += 1;
        } else {
            w += CHS_GLYPH_ADVANCE_JP_PX;
            len += 1;
        }
    }
    return w;
}
