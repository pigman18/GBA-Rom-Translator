/* ============================================================================
 * text_scene.h — 窗口落址配置：数据结构 + 查询接口
 *
 * 设计边界（与用户确认）：
 *   ✅ 允许：以**窗口模板地址**为唯一键的静态配置表，一窗一条，数字显式写出。
 *   ❌ 禁止：启发式门控——靠 tileBase 区间 / 光标值 / 模板字段去"猜"当前场景
 *      （bak/text_original/text_scene.c 的 screen_menu_mode2 等属此类，已废弃）。
 *
 * 为什么日版必须有这张表而美版补丁不需要（2026-08-30 对照结论）：
 *   美版 hook 在公共底座 DrawGlyphTiles 内部，linear/GRID 分支（官方
 *   GetCursorTileNum）在 hook 点之前已完成，且美版中文占用官方码位，
 *   官方全流程原生兼容 ⇒ 零配置。
 *   日版引擎没有公共底座（tm0/tm3/tm1/tm2 四个独立函数），且 tm1 窗口
 *   官方只写 tilemap 表项、零像素写（256 字形预渲染 atlas），中文必须
 *   自己找 tile 落位 ⇒ 落位数据是天生的 per-window 数据，只能声明。
 *
 * 分派边界（本次重构的刀口）：
 *   tm0（对话/战斗）官方公式 = 线性，中文直通官方公式，零配置；
 *   只有 tm1（预渲染菜单）与 tm3（GRID 菜单）需要登记；
 *   未登记窗口用**官方字段**（textMode/fontNum/charBase）兜底，绝不猜场景。
 *
 * 接口形状刻意与 bak/text_original/text_scene.h 完全同名同签名：
 *   text_render.c / PrintNextChar_hook.c 因此零改动（除两处标注 2026-08-30）。
 * ==========================================================================*/
#ifndef TEXT_SCENE_H
#define TEXT_SCENE_H

#include "game.h"

/* 分区策略 */
#define TM1_ZONE_PTR  0u   /* 固定槽（查 chs_slots.inc），16px 步进 */
#define TM1_ZONE_DYN  1u   /* 动态分配（行基址+行内偏移），12px 步进 */

/* 一个列分区：curX < cx_hi 命中本区；zone 表按 cx_hi 升序，**末条 0xFF 兜底** */
struct Tm1Zone {
    uint8_t cx_hi;
    uint8_t strategy;   /* TM1_ZONE_PTR / TM1_ZONE_DYN */
    uint8_t font;       /* 字模：0 = 12px 常规，4 = 8px 小字 */
    uint8_t off;        /* DYN：行内 tile 偏移（相对行基址）；PTR 不用 */
    uint8_t span;       /* DYN：容量（tile 数，须 ≥ 该区最大推进量） */
};

/* tile remap 区间：[lo,hi] → alt+(tile-lo)。中文/槽表不得占用的 tile 搬走用 */
struct TileRemap {
    uint16_t lo, hi, alt;
};

/* GRID 窗口的区域规则：官方 grid 公式之上的搬位修正，按条件命中。
 *   x ≥ x_min 且 y ≥ y_min → x+=x_add; y-=y_sub; idx+=band; idx+=origin。
 *   未命中任何规则 → 不修正（origin 仅 charBase==2 时默认 2）。
 * 另有两条**全局**行为（scene_gctn_mode2，对应 bak mode2_apply）：
 *   y ≤ 20 且 y 为偶数 → 不修正（标题/标签行，官方公式本来就在格点上）；
 *   F9 80 短语 op 挂起（chs_pitch_write_op != 0）→ 不修正。 */
struct Mode2Region {
    uint8_t  x_min;
    uint8_t  y_min;
    uint8_t  x_add;
    uint8_t  y_sub;
    uint16_t band;
    uint16_t origin;
};

/* ---- 一窗一条的配置（指定初始化器；用不到的字段别写）--------------------*/
struct WinCfg {
    const char *name;
    uint32_t    tpl;          /* 窗口模板地址 = 唯一键 */

    /* 线性/mode2 总开关。tm0 一律线性（官方公式），与此字段无关；
     * 此字段只裁决 tm1/tm3 的登记窗口。 */
    uint8_t     use_linear;

    /* -- 线性 + tm1 专用：行基址 / PTR+DYN 分区 --------------------------*/
    const uint16_t *row_tab;  /* 行基址表，下标 = 行号-1；0 = 未配 */
    const uint8_t  *row_span_tab;  /* 每行预留 tile 数（0=该行无中文候选）。
                                    * ⚠ 有中文的行填 0 会让 win[0x18] 不复位
                                    *   而越界写（2026-08-29 实证）。 */
    uint8_t     row_tab_n;
    uint8_t     row_y0;       /* 行号：r = (curY - row_y0) >> row_shift */
    uint8_t     row_shift;
    uint16_t    floor;        /* win[0x18] 下限；0 = 不设地板 */

    const struct Tm1Zone *zones;
    uint8_t     zone_n;

    /* -- mode2（GRID）专用：区域搬位规则（按序命中第一条）-----------------*/
    const struct Mode2Region *regions;
    uint8_t     region_n;

    /* -- tile remap（两模式通用）------------------------------------------*/
    const struct TileRemap *remaps;
    uint8_t     remap_n;
};

/* ---- 登记表（数据在 text_scene.c）---------------------------------------*/
extern const struct WinCfg *const kWindows[];
extern const unsigned kWindowN;

/* 按模板地址查表；未登记返回 NULL（调用方走官方字段兜底，不猜场景）。 */
const struct WinCfg *scene_lookup(uint32_t tpl);

/* ---- 与 bak/text_original 同名同签名的 scene 接口（渲染层唯一依赖）------*/
int  PrintNextChar_Origin(TextPrinter *win);   /* entry.s 跳板 → ROM 0x08003300 */
int  scene_is_buffer_printer(TextPrinter *win);
int  scene_delegate_buffer_print(TextPrinter *win);
int  scene_should_use_linear(TextPrinter *win, uint8_t write_op);
void scene_apply_linear_floor(TextPrinter *win);
uint16_t scene_remap_tile(TextPrinter *win, uint16_t tile);
uint16_t scene_gctn_linear(TextPrinter *win, unsigned xOff, unsigned yOff);
void scene_gctn_mode2(TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower);

/* ---- PTR/DYN 的 per-glyph 接入点（text_render.c 于每字开头调用一次）-----
 * note_glyph：做 zone_select（PTR → 绑定该字槽表项；DYN → 记录 off/span）。
 * is_ptr_mode：本字是否 PTR（渲染层据此用 16px 步进）。 */
void scene_note_glyph(TextPrinter *win, uint16_t glyph_id);
uint8_t scene_is_ptr_mode(TextPrinter *win);

#endif /* TEXT_SCENE_H */
