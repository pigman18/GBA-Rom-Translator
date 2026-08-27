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
 * 相位载体：12px 半列相位存 pitch 槽 chs_px；win[0x1A]=窗左缘（Init 后恒定，
 * 原生 UpdateTilemap 会误推它 → map_at 用 PreserveCursorX）；表项列 = win[0x1B]。
 *
 * hook 面：本文件有且只有一个 ROM hook——P01@0x032F8 → entry.s EngineEntry
 *   → PrintNextChar_Hook。除 PrintNextChar_Hook 与导出工具外全部 static；
 *   跨模块 API（PrintGlyph/DrawGlyph/TranslateHandleEscape）见 include/text.h。
 *
 * 模块划分（include/src 布局）：
 *   本文件 = 引擎；src/text_translter.c = F9 翻译链路（F900/F980/slot）；
 *   src/text_render.c = 共享渲染原语 + GetGlyph 字形源解析；
 *   src/text_render.c = refpr + pitch + 日版 GetCursorTileNum（薄路径）。
 * 本文件取代 text_jp2chs.c 及旧多文件引擎（归档于 src/bak/text/，移出构建）。
 * ===================================================================================== */
#include "text.h"
#include "text_render.h"
#include "text_scene.h"

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

/* struct ChsGlyphTiles（含 glyph_id）→ include/text_render.h */

/* ---- 前置声明（跨模块 API 见 include/text.h）---- */
int  PrintNextChar_Hook(TextPrinter *win);
static int  DrawMenuCursorEF(TextPrinter *win);

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

    if (!GetGlyph(win, cur_char, buf, &width))
        return;                         /* 引擎零回落：不可印位直接消费 */
    {
        /* 缓存键基底：JP/SYM/空白 = (fontNum<<8)|code（钳制与 GetGlyph 一致） */
        uint8_t fn = win_u8(win, WIN_FONTNUM_REAL);
        if (fn > 6u)
            fn = 3u;
        t.glyph_id = (uint16_t)((fn << 8) | (cur_char & 0xFFu));
    }
    t.tl = buf + 0x00;
    t.bl = buf + 0x20;
    t.tr = buf + 0x40;
    t.br = buf + 0x60;
    DrawGlyphTiles(win, &t, width);
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

    (void)glyphWidth;
    DecompressGlyph_Chinese(&glyph, (uint16_t)(gidx & 0xFFFFu),
                            win_u8(win, WIN_FONTNUM_REAL));
    width = glyph.width;
    t.glyph_id = (uint16_t)(0x8000u | (gidx & 0x1FFFu));
    t.tl = (uint8_t *)&glyph.gfxBufferTop[0];
    t.tr = (uint8_t *)&glyph.gfxBufferTop[8];
    t.bl = (uint8_t *)&glyph.gfxBufferBottom[0];
    t.br = (uint8_t *)&glyph.gfxBufferBottom[8];
    DrawGlyphTiles(win, &t, width);
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
    if (!win)
        return;
    arrow_inplace12(win);
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

    if (scene_is_buffer_printer(win))
        return scene_delegate_buffer_print(win);

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

    /* ---- 翻译链路（F9 协议 + slot 替换，src/text_translter.c）---- */
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
    struct GlyphTileInfo info;
    uint8_t *du;
    uint8_t *dl;

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
    DrawGlyphTile_refpr(win, &info, buf + 0x00, du, 0);
    DrawGlyphTile_refpr(win, &info, buf + 0x20, dl, 0);
    UpdateTilemap_PreserveCursorX(win, CHS_MENU_CURSOR_TILE, CHS_MENU_CURSOR_TILE_HI);
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
    return 1;
}

