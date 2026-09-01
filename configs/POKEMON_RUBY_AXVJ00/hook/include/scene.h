#ifndef SCENE_H
#define SCENE_H

#include <stdint.h>
#include "text.h"       /* TextPrinter / win_* 访问器（落址需要） */

/* ============================================================================
 * scene.h — 场景落址配置结构 + 接口（**v4 逻辑忠实复刻**，2026-09-02）
 *
 * 分层：scene.c = 纯配置（一窗一条，独立注释）；engine.c = 算法；
 *       PrintNextChar_hook.c = 渲染消费。新增窗口只改 scene.c。
 *
 * ⚠ 本次为「复刻 v4、不自创分配器」回移：
 *   - 标签列 = PTR 固定槽（per-glyph 槽表 chs_slots，脚本生成）；
 *   - 候选列 = DYN 动态（zone.off/span + win[0x18] 游标 + 行断点续接）；
 *   - GRID 窗 = 官方 mode2 公式 + regions 搬位；
 *   - 未登记 tm1 窗 = tile_alloc 行位分段（图鉴）。
 *   v6 自创的高水位/自动行分配器已移除（其行内多会话互覆即"替换BUG"）。
 * ==========================================================================*/

/* 分区策略（v4 同名） */
#define V6_ZONE_PTR  0u   /* 固定槽（查槽表），16px 步进 */
#define V6_ZONE_DYN  1u   /* 动态分配（行基址+off 游标），12px 步进 */

/* 一个列分区：curX < cx_hi 命中本区；zone 表按 cx_hi 升序，末条 0xFF 兜底 */
struct V6Zone {
    uint8_t cx_hi;
    uint8_t strategy;   /* V6_ZONE_PTR / V6_ZONE_DYN */
    uint8_t font;       /* 字模：0 = 12px 常规，4 = 8px 小字（仅元数据） */
    uint8_t off;        /* DYN：行内 tile 偏移（相对行基址）；PTR 不用 */
    uint8_t span;       /* DYN：容量（tile 数）；span=0 ⇒ 该区不复位 win[0x18] */
};

/* PTR 固定槽表项：glyph（F9 汉字索引）→ slot（4 连 tile 基址） */
struct V6GlyphSlot {
    uint16_t glyph;
    uint16_t slot;
};

/* tile remap 区间：[lo,hi] → alt+(tile-lo)（闭区间） */
struct V6Remap {
    uint16_t lo, hi, alt;
};

/* GRID 窗区域规则：x ≥ x_min 且 y ≥ y_min → x+=x_add; y-=y_sub;
 * idx+=band; idx+=origin。未命中 → 不修正（origin 仅 charBase==2 默认 2）。
 * 全局规则：y ≤ 20 且偶数（标题行）不修正；F9 op 挂起（write_op!=0）不修正。 */
struct V6Region {
    uint8_t  x_min;
    uint8_t  y_min;
    uint8_t  x_add;
    uint8_t  y_sub;
    uint16_t band;
    uint16_t origin;
};

/* 一窗一条的配置（指定初始化器；用不到的字段别写） */
struct V6SceneRule {
    uint32_t    tpl;            /* win地址（win[0x00] 模板 = 唯一键） */
    const char *name;

    /* 线性/GRID 总开关：tm0 一律线性与此无关；只裁决 tm1/tm3 登记窗 */
    uint8_t     use_grid;       /* 1 = GRID(mode2 公式)，0 = 线性 */

    /* -- 线性 + tm1：行基址 / 行容量 / PTR+DYN 分区 ----------------------*/
    const uint16_t *row_tab;    /* 行基址表，下标 = 行号-1；0 = 未配 */
    const uint8_t  *row_span_tab; /* 每行预留 tile 数（0=该行无中文候选。
                                   * ⚠ 有中文的行填 0 ⇒ win[0x18] 不复位 ⇒ 越界写） */
    uint8_t     row_n;
    uint8_t     row_y0;         /* r = (curY - row_y0) >> row_shift */
    uint8_t     row_shift;
    uint16_t    floor;          /* win[0x18] 下限；0 = 不设地板 */

    const struct V6Zone *zones;
    uint8_t     zone_n;

    /* -- PTR 槽表（strategy=PTR 的 zone 查这里；per-glyph，脚本生成）-----*/
    const struct V6GlyphSlot *slots;      /* 未选中态 */
    uint8_t     slot_n;
    const struct V6GlyphSlot *slots_sel;  /* 选中态（红）；空表=1 条哨兵 */
    uint8_t     slot_sel_n;

    /* -- GRID 专用：区域搬位规则（按序命中第一条）------------------------*/
    const struct V6Region *regions;
    uint8_t     region_n;

    /* -- tile remap（两模式通用）------------------------------------------*/
    const struct V6Remap *remaps;
    uint8_t     remap_n;
};

/* 场景规则表（实例在 scene.c） */
extern const struct V6SceneRule kV6Scenes[];
extern const uint16_t kV6SceneN;

/* ---- 场景接口（engine.c 提供；v4 text_layout.h 同名同签名）-------------- */
const struct V6SceneRule *v6_scene_lookup(uint32_t tpl);
void v6_scene_note_glyph(TextPrinter *win, uint16_t glyph_id);
uint8_t v6_scene_is_ptr_mode(TextPrinter *win);
int  v6_scene_is_buffer_printer(TextPrinter *win);
int  scene_should_use_linear(TextPrinter *win, uint8_t write_op);
void scene_apply_linear_floor(TextPrinter *win);
uint16_t scene_remap_tile(TextPrinter *win, uint16_t tile);
uint16_t scene_gctn_linear(TextPrinter *win, unsigned xOff, unsigned yOff);
void scene_gctn_mode2(TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower);

/* tm1 未登记窗口的中文行 tile 分配（图鉴；v4 tile_alloc.c 复刻） */
void tile_alloc_tm1_row(TextPrinter *win);

/* pitch 槽 write_op 记账（F9 短语 op；GRID mode2 全局门控消费） */
uint8_t chs_pitch_write_op(TextPrinter *win);
void chs_pitch_set_write_op(TextPrinter *win, uint8_t op);

#endif /* SCENE_H */
