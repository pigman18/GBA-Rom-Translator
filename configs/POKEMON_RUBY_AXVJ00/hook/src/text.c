/* =====================================================================================
 * text.c — AXVJ 日版打印引擎（全面接管版）
 *
 * 架构：严格 pokeruby 数据流 + 日版语义（设计文档 docs/ruby_jp_design.md）：
 *   取码 → GetGlyph（唯一取址，逐字形字体属性）→ sPrintGlyphFuncs[textMode]
 *   → sWriteGlyphTilemapFuncs[fontNum] → UpdateTilemap(win, nCols, tiles..)
 *
 * 四行一分发（一行一原生语义，行间零共享可变状态）：
 *   tm0 = FontFunc[0] Linear 滚动光栅（TILE_BASE+TILE_OFF，对话/战斗/详情页）
 *   tm1 = FontFunc[1] 等宽：全局游标 scratch（7732 基线；等宽窗 tileData=共享
 *         只读 atlas，像素必须落自由区，表项经 UpdateTilemap 指向 scratch）
 *   tm2 = FontFunc[2] 指针缓冲（dst==0 幻影打印跳过）
 *   tm3 = 与 tm1 共用（菜单/对话主窗；font4 队伍窗走原生 Origin 路径）
 *   tm4..7 / 未验证 fontNum → UNKNOWN：消费返回 1、无绘制（缺字=排查信号）
 *
 * 字体为每字形属性（GetGlyph 返回 width/bank）：
 *   常规（fn3 等）= FontChsNormal 12px；队伍等 fn4 = FontChsSmall 8px 沉底小字
 *   （与原生 font4 8×8 混排节奏一致）；同流混排由像素制光标自然处理。
 *
 * 相位载体（2026-08-25 原生化定案）：12px 步进的半列相位存 win[0x1A]
 * （原生 cursorX，native 换行自动复位），表项列 = win[0x1B]（cursorTileX）
 * 直接增量推进——pitch 槽表/失配检测/页游标表全部移除（原 0x0203FFD2 页表
 * 落入游戏数据区，为背包/队伍死机根因）。
 *
 * hook 面：本文件有且只有一个 ROM hook——P01@0x032F8 → entry.s EngineEntry
 *   → PrintNextChar_Hook。除 PrintNextChar_Hook 与导出工具外全部 static；
 *   跨模块 API（PrintGlyph/DrawGlyph/TranslateHandleEscape）见 include/text.h。
 *
 * 模块划分（include/src 布局）：
 *   本文件 = 引擎；src/chinese_text.c = 中文内容解析（upstream 移植）；
 *   src/text_translate.c = F9 翻译链路（F900/F980/slot）。
 * 本文件取代 text_jp2chs.c 及旧多文件引擎（归档于 src/bak/text/，移出构建）。
 * ===================================================================================== */
#include "text.h"
#include "chinese_text.h"

/* =====================================================================
 * §1 常量与布局
 * ===================================================================== */
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

struct ChsGlyphTiles {
    uint8_t *tl;
    uint8_t *bl;
    uint8_t *tr;
    uint8_t *br;
};

/* ---- 前置声明（跨模块 API 见 include/text.h）---- */
static int  GetGlyph(TextPrinter *win, uint32_t code, uint8_t *out128, uint8_t *outWidth);
static void PrintGlyph_TextMode0(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth);
static void PrintGlyph_Unknown(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth);
static void PrintGlyph_TextMode1(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth);
int  PrintNextChar_Hook(TextPrinter *win);
static int  DrawMenuCursorEF(TextPrinter *win);

/* =====================================================================
 * §2 像素件
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
 * §2b 行相位表（0x0203FF80-FFCF 安全区；反汇编定案：原生引擎不维护
 * 像素相位——tm1 writer 只推 win[0x1B]，win[0x1A] 是窗口属性位域非游标）
 * ===================================================================== */
static uint16_t PhaseKey(TextPrinter *win)
{
    /* 行指纹：换行/换流自动换 key = 相位自动归零。勿折入 CURSOR_X
     * （原生每字推进，非行标识）与 TextPrinter*（栈上回收，中流抖动）。 */
    uint8_t *tpl = win_template(win);
    uint16_t w = tpl ? (uint16_t)(((uintptr_t)tpl >> 2) & 0xFFFFu) : 0;
    uint16_t stream = (uint16_t)((win_u32(win, WIN_TEXT_PTR) >> 2) & 0xFFFFu);
    return (uint16_t)(win_u16(win, WIN_TILE_BASE)
                      ^ ((uint16_t)win_u8(win, WIN_CURSOR_Y) << 8)
                      ^ (uint16_t)win_u8(win, WIN_CURSOR_TILE_Y)
                      ^ w
                      ^ stream);
}

static volatile struct ChsPhase *PhaseBind(TextPrinter *win, int *out_is_new)
{
    volatile struct ChsPhase *tab =
        (volatile struct ChsPhase *)ADDR_CHS_PITCH_SLOTS;
    volatile uint8_t *gen = (volatile uint8_t *)ADDR_CHS_PITCH_CTRL;
    volatile uint8_t *age = (volatile uint8_t *)(ADDR_CHS_PITCH_CTRL + 1u);
    uint16_t key = PhaseKey(win);
    uint8_t cur_tx = win_u8(win, WIN_CURSOR_TILE_X);
    unsigned i;
    unsigned best;
    uint8_t best_age;
    uint8_t g;

    if (out_is_new)
        *out_is_new = 0;

    for (i = 0; i < CHS_PHASE_COUNT; i++) {
        if (tab[i].key == key) {
            /* 失配检测：win[0x1B]（下一绘制格）≠ tx0+(px>>3) 且 > 之
             * ⇒ 中间插了原生字形（(1,4) 路径，整格步进）→ 相位归零、
             * 行锚前移到当前格（原生 8px 整格后相位恒 0，衔接无缝）；
             * ≤ 之 ⇒ 重印/换行残留 → 同样归零重锚。
             * out_is_new 语义（B3）：0=同行续接；1=新槽；2=同键重锚
             * （=同内容重绘信号，分配器据此原地复用本流带首）。 */
            uint8_t want = (uint8_t)(tab[i].tx0 + (tab[i].px >> 3));
            if (cur_tx != want) {
                tab[i].px = 0;
                tab[i].tx0 = cur_tx;
                if (cur_tx > want && out_is_new)
                    *out_is_new = 0;   /* 原生插字：同行续接，非新行 */
                else if (out_is_new)
                    *out_is_new = 2;   /* 重印/回退：同键重锚 */
            }
            g = (uint8_t)(*gen + 1u);
            *gen = g;
            age[i] = g;
            return &tab[i];
        }
    }

    /* 旧槽位版 LRU 语义（逐值等价）：优先 age==0 空闲槽；无空槽才驱逐
     * 最老。禁止 gen%8 轮转——会在有空槽时偷走活跃行的相位（继续画面
     * 单字空洞根因）。 */
    best = 0;
    best_age = 255;
    for (i = 0; i < CHS_PHASE_COUNT; i++) {
        if (age[i] == 0) {
            best = i;
            break;
        }
        if (age[i] < best_age) {
            best_age = age[i];
            best = i;
        }
    }
    g = (uint8_t)(*gen + 1u);
    *gen = g;
    age[best] = g;
    tab[best].key = key;
    tab[best].px = 0;
    tab[best].tx0 = cur_tx;
    tab[best].adv12 = 1;
    tab[best].scr_org = 0;
    tab[best].scr_next = 0;
    if (out_is_new)
        *out_is_new = 1;
    return &tab[best];
}

/* =====================================================================
 * §4 GetGlyph —— 字形源统一解析（每字形字体属性）
 * （CHS 汉库解压已移交 src/chinese_text.c DecompressGlyph_Chinese，
 *  经 gCurGlyph 直供 PrintGlyph；本函数只管 空白/SYM 标点带/日文。）
 * ===================================================================== */
static int GetGlyph(TextPrinter *win, uint32_t code, uint8_t *out128, uint8_t *outWidth)
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
 * tx 为行相位折算的 tile 列（行相位表承载；win[0x1B] 仅作镜像同步）。 */
static void WriteGlyphTilemap(TextPrinter *win, uint8_t tx, uint16_t upperTileNum,
                              uint16_t lowerTileNum)
{
    win_set_u8(win, WIN_CURSOR_TILE_X, tx);
    UpdateTilemap_Origin(win, upperTileNum, lowerTileNum);
}

/* 相位推进 + cursorTileX 同步。
 * win[0x1B] 语义 = 「下一绘制格」= tx0+(px>>3)：原生 writer（(1,4) 路径，
 * 表项写 win[0x1B] 后 +1）接续混排时恰好无缝衔接；纯 CHS 流内下一字形
 * map_tx 同式，PhaseBind 期望值同式，三方一致。 */
static void ChsAdvanceCursor(volatile struct ChsPhase *st, TextPrinter *win,
                             unsigned glyphWidth)
{
    st->px = (uint16_t)(st->px + glyphWidth);
    st->adv12 = (uint8_t)(glyphWidth == 12u);
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(st->tx0 + (st->px >> 3)));
}

static void DrawGlyphTiles(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned linear,
    unsigned glyphWidth)
{
    (void)linear;    /* tm0 恒 Linear（网格语义归 tm1/tm3 共用行） */
    volatile struct ChsPhase *st;
    unsigned startPixel;
    unsigned w2;
    uint16_t off, up0, lo0;
    uint8_t map_tx;
    struct GlyphTileInfo info;

    if (glyphWidth < 8u)
        glyphWidth = 8u;
    if (glyphWidth > 12u)
        glyphWidth = 12u;

    st = PhaseBind(win, 0);

    /* bak ensure_linear_dest_floor 基础下限：tm0 空白 tile = TILE_BASE+0，
     * OFF<4 时首字形会踩掉空白对（之后清屏/翻页把碎片当背景铺出）。 */
    {
        uint16_t off0 = win_u16(win, WIN_TILE_OFFSET);
        if (off0 < 4u)
            win_set_u16(win, WIN_TILE_OFFSET, 4u);
    }

    if (st->px == 0)
        st->tx0 = win_u8(win, WIN_CURSOR_TILE_X);

    startPixel = (unsigned)(st->px & 7u);
    map_tx = (uint8_t)(st->tx0 + (st->px >> 3));

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

    w2 = (glyphWidth > 8u) ? (glyphWidth - 8u) : 0u;
    if (w2 == 0u) {
        ChsAdvanceCursor(st, win, glyphWidth);
        return;
    }

    /* px 不在此推进（ChsAdvanceCursor 统一 +w）；pass2 列 = 起始列+1：
     * 12px 字形跨 2 列，pass2 落 tx0+((px+8)>>3)。双重推进（+8 再 +12）
     * 会使 px 每字 +20 → px>>3 整列数每字多 1 → pass2 表项右移一列
     * （2026-08-25 gdb 日志定案：px 序列 0/20/40/60，半字根因）。 */
    map_tx = (uint8_t)(st->tx0 + ((st->px + 8u) >> 3));
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

    ChsAdvanceCursor(st, win, glyphWidth);
}

/* =====================================================================
 * §6c 表项写入分发（sWriteGlyphTilemapFuncs[fontNum]，tm1/tm3 路径）
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
 * §7 tm1/tm3 scratch 分配（B3 终版：流启动扫描定址 + 流内盲顺序 +
 * 带尾回卷本流带首；2026-08-25 嫁接至行相位表架构）
 * ---------------------------------------------------------------------
 * 等宽窗 tileData = 多窗共享静态只读 atlas，无私有可写区（2026-08-25
 * 实测四截图定案），像素必须落 charBlock 自由区，表项经
 * sWriteGlyphTilemapFuncs 指向 scratch。
 * 所有权：流启动（新绑/失配重锚/px==0）时扫本窗 BG tilemap 引用位图
 * （tpl+0x10，0x400 表项，&0x3FF）定空闲隙——tile 可写 ⇔ 无可见表项
 * 引用（原生不变量查实）。流状态 {scr_org,scr_next} 挂 ChsPhase 槽。
 * 流内盲顺序：own-next 恒相邻（t-2/n 链成立），不扫描不重定位；
 * own-next 被陈旧表项挡住也直写（误写代价=单字错 < 重定位破相邻=花屏）。
 * 带尾回卷 scr_org（本流带首，自踩语义）——关键性质：回卷永不落 0x100
 * 带首，先印流（列表）不会被后印流（描述重印）踩到，背包原 bug 根除。
 * 容量：8px 非溢出字形 2 tile（调用点 n=(w2==0&&!spilled)?2:4）；
 * cb=2 带 [0x100,0x1DF)（223 tile）——背包一屏 216 ≤ 223 实证可装下。
 * 流启动扫描带 16 tile 最小 run（防微碎片），无则退 n，再无则本流带首。
 * 残留风险：流超出所定空闲隙时顺写邻居（碎片场景，单字级）；
 * 带尾回卷点若恰为 spilled 字形，该字左半单字风险。
 * tilemap 缺失（防御）→ 退回全局游标路径。
 * 自由区表（gdb 两轮采集实测，README §10.4；charBlock 绝对 tile 号）：
 *  cb=1（font4 队伍窗）：font4 预渲染/数字映射/图标章之下
 *   → [0x0102,0x014B]。
 *  cb=2（font3 菜单/对话/图鉴/能力页）：场景自加载字库 [0,0x100) 与
 *   场景映射 [0x1C9,0x1F7] 之外 → [0x0100,0x01DF]（▶/UI 章 0x1E0 之下）。
 *  cb=0（弹窗/对话）：[0x0101,0x01AB]（地图 tileset 共存未明）。 */

/* 引用位图：扫本窗 BG tilemap 全部 0x400 表项，标记 [lo,lo+span) 内
 * 被引用 tile（bits[d>>5] 的 bit[d&31]，d=tile-lo）。 */
static void GlyphScanRefs(uint8_t *tpl, uint16_t lo, uint16_t span, uint32_t *bits)
{
    const uint16_t *tmap = (const uint16_t *)(uintptr_t)win_u32(tpl, 0x10);
    unsigned i;

    for (i = 0; i < 8u; i++)
        bits[i] = 0;
    if (!tmap)
        return;
    for (i = 0; i < 0x400u; i++) {
        uint32_t d = (uint32_t)(tmap[i] & 0x03FFu) - lo;
        if (d < span)
            bits[d >> 5] |= 1u << (d & 31u);
    }
}

/* 位图内首个连续 n 空位：自 prefer 起扫到带尾再回卷带首；无则 0xFFFF。 */
static uint16_t GlyphScanRun(const uint32_t *bits, uint16_t span, unsigned n, uint16_t prefer)
{
    uint16_t off;
    unsigned run = 0;

    if (prefer >= span)
        prefer = 0;
    for (off = 0; off < span; off++) {
        uint16_t idx = (uint16_t)(prefer + off);
        if (idx >= span)
            idx = (uint16_t)(idx - span);
        if (bits[idx >> 5] & (1u << (idx & 31u))) {
            run = 0;
            continue;
        }
        if (++run == n) {
            int first = (int)idx - (int)n + 1;
            if (first < 0)
                first += span;
            return (uint16_t)first;
        }
    }
    return 0xFFFFu;
}

static uint16_t GlyphScratchAlloc(TextPrinter *win,
                                  volatile struct ChsPhase *st,
                                  int slot_new, unsigned n)
{
    uint8_t *tpl = win_template(win);
    uint8_t cb = tpl ? tpl[1] : 0;
    uint16_t lo, hi, span, base;
    int restart, initialized, in_place;

    if (cb == 1) {
        lo = 0x0102u;
        hi = 0x014Bu;
    } else if (cb == 2) {
        lo = 0x0100u;
        hi = 0x01DFu;
    } else {
        lo = 0x0101u;
        hi = 0x01ABu;
    }
    span = (uint16_t)(hi - lo + 1u);

    if (!tpl || !win_u32(tpl, 0x10)) {
        /* tilemap 缺失（防御）：退回全局游标路径（7732 基线行为） */
        uint16_t cur = *(volatile uint16_t *)ADDR_GLYPH_ALLOC_NEXT;
        if (cur < lo || (uint16_t)(cur + n - 1u) > hi)
            cur = lo;
        *(volatile uint16_t *)ADDR_GLYPH_ALLOC_NEXT = (uint16_t)(cur + n);
        return cur;
    }

    /* 流启动 = 新绑 / 失配重锚 / px==0（PhaseBind 重锚恒清 px；行内 px
     * 单调递增不回 0）。
     * slot_new 语义（PhaseBind）：0=同行续接；1=新槽（新流，扫描定隙）；
     * 2=同键重锚（=同内容重绘，gdb 实证选项页 297 次/格三空隙轮转 =
     * 闪烁根因）→ 原地复用 scr_org：同字形写同 tile、表项重写同值，
     * 幂等零闪烁，且不再消耗自由带。FE 换行因 key 含 cursorY 必换槽。 */
    initialized = (st->scr_org != 0u || st->scr_next != 0u);
    in_place = (slot_new == 2) && initialized;
    restart = !in_place &&
              ((slot_new != 0) || (st->px == 0u) || !initialized);

    if (in_place) {
        base = st->scr_org;                 /* 原地重画：表项已指向本带 */
        st->scr_next = (uint8_t)(base + n);
    } else if (restart) {
        uint32_t bits[8];
        uint16_t prefer = st->scr_org;
        uint16_t got;
        GlyphScanRefs(tpl, lo, span, bits);
        got = GlyphScanRun(bits, span, 16u, prefer);
        if (got == 0xFFFFu)
            got = GlyphScanRun(bits, span, n, prefer);
        if (got == 0xFFFFu)
            got = prefer;                       /* 全带满：本流带首自踩 */
        st->scr_org = (uint8_t)got;
        st->scr_next = (uint8_t)(got + n);
        base = got;
    } else {
        /* 流内盲顺序：own-next 恒相邻（t-2/n 链成立），不扫描不重定位；
         * 带尾回卷本流带首（自踩语义，非塌缩，永不落 0x100 踩他流）。 */
        uint16_t next = st->scr_next;
        if ((uint16_t)(next + n) > span) {
            next = st->scr_org;
        }
        st->scr_next = (uint8_t)(next + n);
        base = next;
    }

    return (uint16_t)(lo + base);
}

/* =====================================================================
 * §9 打印行（sPrintGlyphFuncs 一行一语义）
 * ===================================================================== */

/* ---- tm0：FontFunc[0] Linear 滚动光栅（对话/战斗文本/详情页字段）----
 * 像素写 TILE_BASE+TILE_OFF 连续区（原生字段，ITP 清零=每打印新区域），
 * UpdateTilemap 写 cursor 格；12px 汉字 nCols=2、8px 日文 nCols=1。
 * 相位由行相位表承载；新绑/失配重锚（=新行信号）→ TILE_OFFSET +=2
 * （旧槽位版 newline_reset 等价：上行尾 spill 对不被下行首字形覆盖）。 */
static void PrintGlyph_TextMode0(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    int slot_new = 0;

    (void)PhaseBind(win, &slot_new);
    if (slot_new) {
        uint16_t off = win_u16(win, WIN_TILE_OFFSET);
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
    }

    DrawGlyphTiles(win, tiles, 1, glyphWidth);
}

/* ---- tm1/tm3：等宽（全局游标 scratch + 行相位表）----
 * 12px 汉字 = 2 列表项 + 1.5 列步进（半列相位由行相位表承载，
 * 下一字形自动从半列续接）；8px 日文 = 1 列表项（相位续接同旧槽位版）。
 * 不读写 TILE_OFFSET（tm0 专属状态，行间隔离）。
 * 两趟几何（bak DrawGlyphTiles_CHS_Core 同款，逐值保留）：第一趟 TL/BL
 * 恒宽 8 @startPixel（跨列 spill → 紧邻下一对）；第二趟 TR/BR 恒宽 w-8、
 * startPixel 复用（写第 2 对 [startPixel,+w2)，与 spill [0,startPixel)
 * 拼满整列）；8px 字形仅第一趟，行尾半列 spill 亦落表项。
 * 容量：8px 非溢出字形只占 2 tile（分配 n=(w2==0&&!spilled)?2:4）。
 * 表项列 = 行相位表 tx0+px>>3（win[0x1B] 镜像）；
 * spill 共享列语义依赖分配器盲顺序（t-2 = 上一字形溢出对，7732 基线）。 */
static void PrintGlyph_TextMode1(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    volatile struct ChsPhase *st;
    unsigned w, startPixel, w2, spilled;
    uint16_t t, u1, l1, u2, l2;
    uint8_t fontNum = win_u8(win, WIN_FONTNUM_REAL) & 7u;
    int slot_new = 0;
    struct GlyphTileInfo info;

    if (glyphWidth < 8u)
        glyphWidth = 8u;
    if (glyphWidth > 12u)
        glyphWidth = 12u;
    w = glyphWidth;

    st = PhaseBind(win, &slot_new);
    if (st->px == 0)
        st->tx0 = win_u8(win, WIN_CURSOR_TILE_X);

    startPixel = (unsigned)(st->px & 7u);
    w2 = (w > 8u) ? (w - 8u) : 0u;
    spilled = (startPixel > 0u);

    /* 共享列（bak 原地合成语义）：startPixel>0 ⇒ 首列即上一字形溢出列。
     * 盲顺序分配下上一字形溢出对 = t-2/-1：pass1 在该对上 RMW 合成，
     * [0,startPixel) 保留上一字右半像素。8px 非溢出只消耗一对（2 tile）。
     * B3：流启动（新绑/失配重锚/px==0）扫描定空闲隙，流内盲顺序。 */
    t = GlyphScratchAlloc(win, st, slot_new, (w2 == 0u && !spilled) ? 2u : 4u);

    if (spilled) {
        u1 = (uint16_t)(t - 2u);
        l1 = (uint16_t)(t - 1u);
    } else {
        u1 = t;
        l1 = (uint16_t)(t + 1u);
        /* 表项：首列 cursor 格（仅全新列需要映射；共享列已指向 u1/l1） */
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(st->tx0 + (st->px >> 3)));
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

    /* px 不在此推进（pass1 的 +8 已并入下方表项列公式，ChsAdvanceCursor
     * 统一 +w）；双重推进会使 px 每字 +20 → 表项列右移一列（半字根因，
     * 2026-08-25 gdb 日志定案：px 序列 0/20/40/60）。 */

    if (w2 == 0u) {
        /* 8px 字形（日文）：行尾半列 spill 也要落表项（bak 同款），
         * 否则右半像素落在无表项的列上 → 丢半边。spill 列 = 起始列+1。 */
        if (spilled) {
            win_set_u8(win, WIN_CURSOR_TILE_X,
                       (uint8_t)(st->tx0 + ((st->px + 8u) >> 3)));
            sWriteGlyphTilemapFuncs[fontNum](win, u2, l2);
        }
        ChsAdvanceCursor(st, win, w);
        return;
    }

    /* 第二趟：TR/BR 宽 w-8，startPixel 复用（写第 2 对的
     * [startPixel, +w2)，与第一趟 spill [0,startPixel) 拼满整列）。
     * pass2 表项列 = tx0+((px+8)>>3)（12px 字形的右半列）。 */
    info.width = (uint8_t)w2;
    info.src = tiles->tr;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, u2);
    DrawGlyphTile_ShadowedFont(win, &info, 0);
    info.src = tiles->br;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, l2);
    DrawGlyphTile_ShadowedFont(win, &info, 0);
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(st->tx0 + ((st->px + 8u) >> 3)));
    sWriteGlyphTilemapFuncs[fontNum](win, u2, l2);

    /* 相位推进 + cursorTileX 同步（行相位表承载，单次 +w） */
    ChsAdvanceCursor(st, win, w);
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
    PrintGlyph_TextMode1,   /* 1：等宽（全局游标 scratch + 原生列推进） */
    PrintGlyph_TextMode2,   /* 2：缓冲（占位） */
    PrintGlyph_TextMode1,   /* 3：对话/菜单主窗（font4 队伍窗经 Tm1 表走 Origin） */
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

int DrawGlyph(TextPrinter *win, uint32_t cur_char)
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

/* F9 汉字：DecompressGlyph_Chinese 解压进栈上字形缓冲（宽度随 fontNum 8/12，
 * upstream 同款分层：解压填缓冲 → 渲染行写窗口），再进 tm 分发。
 * glyphWidth 形参仅为兼容旧签名——实际宽度以 glyph.width 为准。
 * 缓冲在栈：game.bin 无 RAM 段（link/game.ld），全局落 ROM 写无效。 */
void PrintGlyph(TextPrinter *win, uint32_t gidx, unsigned glyphWidth)
{
    struct TextGlyph glyph;
    struct ChsGlyphTiles t;
    unsigned width;
    unsigned m;

    (void)glyphWidth;
    DecompressGlyph_Chinese(&glyph, (uint16_t)(gidx & 0xFFFFu),
                            win_u8(win, WIN_FONTNUM_REAL));
    width = glyph.width;
    t.tl = (uint8_t *)&glyph.gfxBufferTop[0];
    t.tr = (uint8_t *)&glyph.gfxBufferTop[8];
    t.bl = (uint8_t *)&glyph.gfxBufferBottom[0];
    t.br = (uint8_t *)&glyph.gfxBufferBottom[8];
    m = win_u8(win, WIN_TEXTMODE);
    if (m >= PRINT_GLYPH_MODES)
        m = 0;
    sPrintGlyphFuncs[m](win, &t, width);
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
 *   1) CHS 相位对齐：半列相位（cursorX&7）时 TILE_OFFSET +=2（防 FA/FB
 *      翻页双▼，B04）；cursorTileX 由渲染行增量维护，无需槽位折算回写；
 *   2) downArrowCounter 清零（原跳板 strh [r0,#6]，见 game.h
 *      WIN_DOWN_ARROW_COUNTER）；
 *   3) 尾跳原版主体延续点 DrawInitialDownArrow_Body@0x08003DAD——
 *      与旧跳板逐语义一致（跳过原生序言，延续点自含所需状态）。
 * ===================================================================== */
static void DrawInitialDownArrow(TextPrinter *win)
{
    volatile struct ChsPhase *st;

    if (!win)
        return;

    st = PhaseBind(win, 0);
    if (st->px) {
        uint16_t cols = (uint16_t)((st->px + 7u) >> 3);
        uint8_t want = (uint8_t)(st->tx0 + cols);
        uint8_t cur_tx = win_u8(win, WIN_CURSOR_TILE_X);

        if (cur_tx == 0u && want > 0u) {
            /* 翻页后 cursor 归零：半列相位时 TILE_OFFSET +=2（防双▼，B04），
             * 相位归零重锚行首 */
            if (st->px & 7u) {
                uint16_t off = win_u16(win, WIN_TILE_OFFSET);
                win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
            }
            st->px = 0;
            st->tx0 = win_u8(win, WIN_CURSOR_TILE_X);
        } else {
            win_set_u8(win, WIN_CURSOR_TILE_X, want);
            if (st->px & 7u) {
                uint16_t off = win_u16(win, WIN_TILE_OFFSET);
                win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
            }
            st->px = 0;
            st->tx0 = win_u8(win, WIN_CURSOR_TILE_X);
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

    /* ---- 翻译链路（F9 协议 + slot 替换，src/text_translate.c）---- */
    if (TranslateHandleChar(win, c))
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

