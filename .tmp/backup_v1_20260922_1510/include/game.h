/* AXVJ patch ??? ? ?? / Win ?? / ?????
 * PrintNextChar ≈ pokeruby PrintNextChar
 */
#ifndef GAME_H
#define GAME_H

#include <stdint.h>

#define LANGUAGE_JAPANESE          1u
#define CHS_GLYPH_ADVANCE_JP_PX    8u
// <<<GEN_ADDR>>>
/* Auto-generated from game_addrs.asm by scripts/gen_game_h_from_addrs.py.
 * Do not edit by hand. Change the address in game_addrs.asm; `; C:` marker
 * on the equ line sets the ADDR_* macro name. */
#define ADDR_CALL_VIA_R2                   0x081B12DCu
#define ADDR_COPY_GLYPH_1BPP_4BPP          0x08003830u
#define ADDR_COPY_GLYPH_2BPP_4BPP          0x080038A0u
#define ADDR_DEX_TEXT_UNKNOWN_POKE         0x083E9688u
#define ADDR_DRAW_INITIAL_DOWN_ARROW       0x08003F4Cu
#define ADDR_DRAW_INITIAL_DOWN_ARROW_BODY  0x08003DACu
#define ADDR_FD_RESOLVER                   0x080046D4u
#define ADDR_FD_SUBPRINT                   0x08002DB4u
#define ADDR_FONT_1BPP_BIG                 0x09500000u
#define ADDR_FONT_1BPP_MIDDLE              0x09700000u
#define ADDR_FONT_1BPP_SMALL               0x09600000u
#define ADDR_FONT_CHS_MIDDLE               0x09400000u
#define ADDR_FONT_CHS_NORMAL               0x09000000u
#define ADDR_FONT_CHS_SMALL                0x09100000u
#define ADDR_FONT_CHS_SYM                  0x091E0000u
#define ADDR_FONT_FUNC_TABLE               0x081BB3ACu
#define ADDR_FONT_FUNC_TM0_ORIGIN          0x08003568u
#define ADDR_FONT_FUNC_TM2_ORIGIN          0x0800338Cu
#define ADDR_FONT_FUNC_TM3_ORIGIN          0x08003494u
#define ADDR_FONT_SUBTABLE                 0x081BB3BCu
#define ADDR_FONT_TYPE1_MAP                0x081B34A8u
#define ADDR_GAME_BIN                      0x08800000u
#define ADDR_GET_CURSOR_TILEMAP_PTR        0x08003708u
#define ADDR_GET_GLYPH_TILE_PTRS           0x08003730u
#define ADDR_GMENU                         0x03000618u
#define ADDR_INIT_TEXT_PRINTER             0x08002C68u
#define ADDR_INIT_WINDOW_TILE_DATA         0x08002A50u
#define ADDR_MENU_PRINT_TEXT               0x0806F16Cu
#define ADDR_OPT_FG_COLOR                  0x0203FFD1u
#define ADDR_OPT_PALETTE_OVERRIDE          0x0203FFD0u
#define ADDR_PHRASE_OFFSETS                0x08810000u
#define ADDR_PHRASE_TABLE                  0x08820000u
#define ADDR_PLAY_BGM                      0x080724ACu
#define ADDR_PLAY_SE                       0x080724CCu
#define ADDR_PRINT_GLYPH_TM1_ORIGIN        0x0800360Cu
#define ADDR_SLOT_TABLE                    0x09EA0000u
#define ADDR_TEXT_CLEAR_WINDOW             0x08003BA8u
#define ADDR_TILE_PTR_TM3                  0x080034E0u
#define ADDR_UPDATE_TILEMAP                0x080036DCu
#define ADDR_V1_KEY_TAB                    0x0203FE00u
#define ADDR_V1_MAGIC                      0x0203FFC2u
#define ADDR_V1_SIG_CB                     0x0203FFC8u
#define ADDR_V1_SIG_TPL                    0x0203FFC4u
#define ADDR_V1_SLOT_N                     0x0203FFC0u
// <<<GEN_ADDR_END>>>
/* --- 手工追加（非生成区）：v9 队列分配器状态块 0x0203FF4A..0x0203FF55 --- */
#define ADDR_V8Q_MAGIC                     0x0203FF4Au
#define ADDR_V8Q_WIN                       0x0203FF4Cu
#define ADDR_V8Q_HEAD                      0x0203FF50u
#define ADDR_V8Q_CURSOR                    0x0203FF52u
#define ADDR_V8Q_END                       0x0203FF54u
#define ADDR_V8Q_TPL                       0x0203FF58u
/*
 * 短语表（PhraseTable）—— 固定长度字段突破字符数限制的方案。
 * 日版 Gen3 的招式/特性/物种等字段有 stride 限制（6-8 字节），
 * 若用 F9 00 ll tt 侧载一个汉字占 4 字节，8 字节槽最多 2 汉字。
 * 短语表将"文本存储"和"字段引用"解耦：
 *   字段槽（8B）：F9 <op> hi lo FF          → 4 字节引用
 *   PhraseTable：F9 00×N + FE/FB… + FF      → 展开侧载流（含控制符）
 * 查找路径（实现在 src/text_translate.c）：
 *   F9 80/op →
 *   PhraseOffsets[code]（u32 数组 @ 0x08810000）
 *   → PhraseTable + offset（字节流 @ 0x08820000）
 *   → 父串未结束 + 无 FE/FB/FA：内联绘制，INDEX+3 续父串（对齐 GetStringWidth）
 *   → 父串即短语引用+FF：切流，短语 FF = 整句 EOS（地名等）
 * layout: .org 0x08810000 → offsets （u32[code_max], sentinel = total_size）
 *         .org 0x08820000 → streams （PCS bytes ending in FF）
 *
 * 勿在 0x0203FFF0/F7F8 放 PhraseResume（崩/踩图）；0x0203FFD2 起为游戏
 * 数据区（页游标表曾落此处 → 背包/队伍死机根因，已移除）。
 * 改 phrases 只重生 asm + armips，不必重编 game.bin。
 */
/* Sym punct bank (9×64B), after Small @ 0x09100000+0xE0000.
 * Font3 layout: upper+lower 8×8 @4bpp-index (0/E/F), NOT 16×16 2bpp.
 * Inject hex = JP PCS (00 space, 37。 3A、 3B， 3C！ 3D？ 3E： …);
 * PrintNextChar draw_chs_pcs: Sym/blank/F900/JP-via-CHS → same DrawGlyph. */
#define SYM_GLYPH_BASE             0x36u
#define SYM_GLYPH_COUNT            9u
/* Legacy single-slot (unused by hook; kept for docs/config). */
/* Pitch slot table: ctrl @ FF80 (16B), slots[8] @ FF90 (64B). */
/* DrawOptionMenuChoice 选中调色板覆盖（避开 FFF0/F7F8）。
 * 🔴 2026-09-22 教训：此前曾误判「8 = 与阴影同色致糊」并改成 2，**属实机配色回归**，
 *    用户实测「原本配色正确，改后连颜色都坏了」⇒ 已回滚为 8。8 是设计值，勿再动。 */
#ifndef OPT_FG_SELECTED
#define OPT_FG_SELECTED     8u
#endif
#ifndef OPT_FG_UNSELECTED
#define OPT_FG_UNSELECTED   0u
#endif

/* ---- pokeruby text.c 对齐的类型（字段名与官方一致）----
 * 官方 DrawGlyphTile_UnshadowedFont/ShadowedFont(struct GlyphTileInfo *)；
 * CHS 路径 colors 未用（重映射走官方 CopyGlyph*To4bpp），保留字段对齐。 */
struct GlyphTileInfo {
    uint8_t textMode;      /* 官方 win->textMode；CHS 路径未用 */
    uint8_t startPixel;    /* (left+cursorX)&7 相位 */
    uint8_t width;         /* 本趟列宽（8 或 4）*/
    uint8_t *src;          /* 32B tile 数据（upper 或 lower）*/
    uint32_t *dest;        /* VRAM tile 目的 */
    uint32_t *colors;      /* 官方 sGlyphBuffer.colors；CHS 未用 */
};

struct GlyphBuffer {
    uint32_t pixelRows[16]; /* 0-7 左 tile，8-15 右 tile（spill）*/
    uint32_t background;
    uint32_t colors[16];
};

/* Hook3 伪 glyph 编码（bit15=右半，bits0-14=gidx）已随 CHS 解压收编至
 * src/chinese_text.c（内部专用）。 */

#define WIN_TEMPLATE        0x00
#define WIN_STATE           0x04
#define WIN_DOWN_ARROW_COUNTER 0x06  /* 等 A 箭头动画计数（原 P05 跳板 strh [r0,#6] 同源） */
/* AXVJ TextPrinter 布局（偏移固定于 ROM；括号内为 pokeruby struct Window 语义名）：
 * +0x0A textMode(FontFuncTable 索引)  +0x0B fontNum  +0x10 text  +0x14 textIndex
 * +0x16 tileDataStartOffset(TILE_BASE)  +0x18 tileDataOffset(TILE_OFFSET)
 * +0x1A cursorX  +0x1B cursorTileX(AXVJ 特有 tile 列游标)  +0x1C cursorY  +0x1D cursorTileY
 * Colors are C/D/E only — do NOT alias fontNum as COLOR_B (that caused
 * dual-path / wrong glyph fetches). */
#define WIN_TEXTMODE        0x0A
#define WIN_FONTNUM         0x0A  /* legacy alias = textMode */
#define WIN_FONTNUM_REAL    0x0B
#define WIN_DELAY           0x09  /* FC 08 Pause 的节拍计数（sub_8003110 反汇编定案） */
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
/* WindowTemplate（win_template 指向）：+0x0C tileData +0x10 tilemap（NULL=缓冲直绘） */
#define TPL_CHARBASE       0x01  /* charBaseBlock：charBlock 号 0~3（v1 draw_glyph.c:355 实证 tpl[1]） */
#define TPL_TILE_DATA       0x0C
#define TPL_TILEMAP         0x10
/* JP RenderTextHandleBold (0x08002CC0): dest buffer ptr (FontFunc[2] blit). */
#define WIN_TILE_DATA       0x20

/* =====================================================================
 * v1 8px 渲染层常量（2026-09-22）
 *
 * 引擎落砖是纯函数「tile = TILE_BASE + 2*char」——tm0 处理器 @0x08003568 与
 * FontSubTable[0/3/7] @0x08003584 逐指令核过：TILE_OFFSET（win[0x18]，单位 tile）
 * 与 cursorTileX（win[0x1B]，单位 tile 列）都是整列游标，**引擎不维护任何像素相位**。
 * 中文侧不复用这两段游标：汉字砖号由「字 → 槽」粘性表给定（chs_render.c）。
 *
 * 汉字字模容器 = 128B（4 个 8x8 4bpp 砖 TL/BL/TR/BR，实际只用左半 TL+BL）；
 * 上砖 = src[0:32)（行 0..7）、下砖 = src[32:64)（行 8..15），一次 64B 直拷。
 * ===================================================================== */
/* F9 汉字的**渲染步进** = 8px = 一个 map 格。text_translater.c 的
 * phrase_width_px / GetStringWidth 用它算流宽；与 ADDR_FONT_CHS_MIDDLE
 * （Middle 墨迹 8 宽）严格一致。旧值 12 已随 12px 渲染层一并退役。 */
#define CHS_GLYPH_ADVANCE_PX 8
#define CHS_CELL_BYTES       128
#define CHS_FONT_GLYPH_MAX      7168
#define CHS_ESCAPE              0xF9
#define CHS_PHRASE_DEFAULT      0x80
#define PCS_CTRL_BASE           0xFAu   /* FA~FE 控制码基（text_translater.c 共用） */

/* ---- 已随「v8~v38 分配器族 / 场景分档表」整体删除，勿复活 ----------------
 * 删掉的是**机制**，不是参数：它们描述的是"每帧重新决定砖号"的世界观
 * （段表 / 行相位 / 避让带 / 30 列网格 / Mode2 分带 / 商店·队伍·PSS 专用带 /
 * UI 图标与 ▶ 的 tile 重映射 / 战斗多 TILE_BASE 强制线性 / GMENU_* 布局）。
 * v1 没有这些概念：只有一个池 + 一张粘性表。相关常量已全部移除——
 * 若在旧文档/旧 commit 里看到 CHS_TILE_POOL_END / CHS_MODE2_* / CHS_SHOP_* /
 * CHS_PARTY_* / CHS_PSS_* / CHS_UI_ICON_* / CHS_MENU_CURSOR_* / CHS_WRITE_* /
 * CHS_BATTLE_* / GMENU_* / FONT_NORMAL_* 等名字，一律视为已判死。 */

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

/* 32B（1 个 4bpp tile）拷贝。v4 时是 text_render.c 的导出函数；
 * v5 起为公共内联工具（F9 层 GetGlyph 与新渲染层共用）。 */
static inline void copy_tile32(void *dst_vram, const void *src)
{
    const uint32_t *s = (const uint32_t *)src;
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

/* UpdateTilemap：不劫 ROM。中文打印层直调 Origin=完整原生 @0x080036DC。
 * UI 走原路径，互不经过重排表。 */
void UpdateTilemap_Origin(TextPrinter *win, uint16_t upper, uint16_t lower);

/* pokeruby GetCursorTilemapPointer：r0=win → &tilemap 当前格（UTM 内部也调它） */
static inline uint16_t *GetCursorTilemapPointer_Origin(TextPrinter *win)
{
    typedef uint16_t *(*fn_t)(TextPrinter *w);
    return ((fn_t)(ADDR_GET_CURSOR_TILEMAP_PTR | 1u))(win);
}

/* 原生 UpdateTilemap 会推进 win[0x1A]（窗左缘，Init 后恒定）。
 * 中文多列提交须保存/恢复，否则表项格漂移。 */
static inline void UpdateTilemap_PreserveCursorX(
    TextPrinter *win, uint16_t upper, uint16_t lower)
{
    uint8_t saved_cx = win_u8(win, WIN_CURSOR_X);

    UpdateTilemap_Origin(win, upper, lower);
    win_set_u8(win, WIN_CURSOR_X, saved_cx);
}

/* 原生 tm1 等宽打印（PCS 专用分发）：FontSubTable[fontNum](win, glyph) 写
 * 预渲染字体 tile 表项（font0/3 = base+2*glyph；font1/4 = base+FontType1Map）
 * + [win+0x1B](cursorTileX)+=1。零像素绘制、零池分配。 */
static inline void PrintGlyph_TextMode1_Origin(TextPrinter *win, uint32_t glyph)
{
    typedef void (*fn_t)(void *, uint32_t);
    ((fn_t)(ADDR_PRINT_GLYPH_TM1_ORIGIN | 1u))(win, glyph);
}
static inline void CopyGlyph2bppTo4bpp_Origin(
    const void *src, void *dst, uint32_t c, uint32_t e, uint32_t d)
{
    ((chs_fn5)(ADDR_COPY_GLYPH_2BPP_4BPP | 1u))(src, dst, c, e, d);
}

typedef void (*chs_fn4)(const void *src, void *dst, uint32_t a, uint32_t b);

static inline void CopyGlyph1bppTo4bpp_Origin(
    const void *src, void *dst, uint32_t fg, uint32_t bg)
{
    ((chs_fn4)(ADDR_COPY_GLYPH_1BPP_4BPP | 1u))(src, dst, fg, bg);
}


/* Hook3（P02）已于 2026-08-24 移除：CHS 字模取址收归 src/chinese_text.c
 * DecompressGlyph_Chinese；原生 GetGlyphTilePointers@0x08003730 不再订址，
 * 由 GetGlyphTilePointers_Origin 直调原版。 */

/* 地名弹窗居中（src/map_name_popup/MapNamePopup_hook.c；P04 挂 0x0809F67E）：按本引擎真实步进
 * （空白/字面量 8px、汉字 12px）算居中起点。MenuPrint 的 left 是**格数**
 * （8px/格，Text_InitWindow 内 win->left = 8*left）；返回居中追加格数
 * （四舍五入，残差 ≤4px），0=维持原生位置。只读缓冲区，不改写。
 * ROM 补丁严禁占 r0（native mov r0,sp 的缓冲区指针必须原样进 C）。 */
uint32_t MapNamePopup_CalcLeftPx(const uint8_t *buf);
/* 文本流像素宽度（来源 src/text_translate.c；纯工具无 hook）：遍历到
 * 0xFF 或 max_bytes，字面量/空白 8px、F9 00 内联汉字 12px、F9 80 短语查表逐字
 * 累加、FA~FE 控制码 0px。供地名弹窗等需要真实渲染宽度的场景复用。 */
uint32_t GetStringWidth(const uint8_t *buf, uint32_t max_bytes);
/* （原 P24 InitWindowTileData 分区器钩子已于 2026-08-25 随页游标表移除：
 *  页表落 0x0203FFD2 游戏数据区，为背包/队伍死机根因。） */

/* 场景布局门控已移除：落址按 win[0x0A](textMode) 分派，见 src/text/FontFunc_hook.c */

/*
 * AXVJ GetGlyphTilePointers @ 0x08003730 is 4-arg (JP ROM; language baked
 * into sFonts[fontNum]):
 *   void GetGlyphTilePointers(u8 fontNum, u16 glyph, u8 **upper, u8 **lower);
 * pokeruby US has an extra language arg — do NOT pass LANGUAGE_JAPANESE here
 * or r1 becomes glyph=1 and r2 is treated as a pointer → blank text.
 */
static inline void GetGlyphTilePointers_Origin(
    uint8_t font_num, uint16_t glyph,
    uint8_t **upper, uint8_t **lower)
{
    typedef void (*fn_t)(uint32_t, uint32_t, uint8_t **, uint8_t **);
    ((fn_t)(ADDR_GET_GLYPH_TILE_PTRS | 1u))(
        font_num, glyph, upper, lower);
}

/* Fonts 0/1/2/6 = 1bpp (8B/tile); 3/4/5 = shadowed 4bpp-index (32B/tile). */
static inline int FontIsShadowed(uint8_t font_num)
{
    return font_num >= 3u && font_num <= 5u;
}

#endif /* GAME_H */
