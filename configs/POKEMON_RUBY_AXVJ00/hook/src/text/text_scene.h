/* ============================================================================
 * text_scene.h — tm1 窗口布局的**声明式配置表**
 *
 * 设计边界（2026-08-29 与用户确认）：
 *   ✅ 允许：以**窗口模板地址**为唯一键的静态配置表，一窗一条，数字显式写出。
 *   ❌ 禁止：启发式门控——靠 tileBase 区间 / 光标值 / 模板字段去"猜"当前场景
 *      （旧 bak/text_original/text_scene.c 的 screen_menu_mode2 / screen_shop_bag
 *      / screen_party_footer 属此类，会误判且难验证）。
 *
 * 为什么必须是 per-window 配置（而不是一套通用公式）：
 *   tm1 每个窗口的预渲染字库都铺满 tile [1,513)（tile = startOffset + glyph*2）。
 *   "哪些 tile 是空的"取决于**该窗口实际引用了哪些字形** —— 这是天生的
 *   per-window 数据，不存在场景无关的通用解。
 *
 * 本文件只放**数据结构与查询接口**；具体数值一律在 text_scene.c 的表里。
 * 未登记的模板 → scene_tm1_lookup 返回 NULL，调用方回退线性式，**不猜场景**。
 * ==========================================================================*/
#ifndef TEXT_SCENE_H
#define TEXT_SCENE_H

#include "game.h"
#include "text.h"

/* ---- 候选列槽（值列）----------------------------------------------------
 * cx_hi：curX < cx_hi 命中本槽；**最后一条必须填 0xFF 兜底**。
 * off  ：行内 tile 偏移（相对行基址）。
 * span ：容量。会话复位判据是 `off < start || off >= start+span`，
 *        所以 span 必须 ≥ 该槽最大字数所需的推进量（12px 每字 4，8px 每字 2）。
 * ------------------------------------------------------------------------*/
struct Tm1Slot {
    uint8_t cx_hi;
    uint8_t off;
    uint8_t span;
};

/* ---- tm1 窗口布局配置 ---------------------------------------------------*/
struct Tm1WinCfg {
    const char     *name;           /* 仅用于调试/日志，运行时不影响落址 */
    uint32_t        tpl;            /* 窗口模板地址 = 唯一键 */

    /* 行基址 */
    const uint16_t *row_tab;        /* 菜单行基址表，下标 = 行号-1 */
    const uint8_t  *row_span_tab;   /* 每行**预留**的 tile 数（与 row_tab 等长）。
                                     * 必须显式给：末行常无候选列，只需标签那点容量；
                                     * 若一律按满跨度预留，会撞到后面的引用字形。 */
    uint8_t         row_tab_n;      /* 行数 */
    uint8_t         row_y0;         /* 行号推导：r = (curY - row_y0) >> row_shift */
    uint8_t         row_shift;
    uint16_t        title_base;     /* curY <= row_y0 时用它（标题/无候选列的行） */

    /* 列分区 */
    uint8_t         col_label_max;  /* curX < 此值 = 标签列（12px），否则候选列（8px） */
    uint8_t         lbl_off;        /* 标签子区起点 */
    uint8_t         lbl_span;       /* 标签子区容量 */
    const struct Tm1Slot *slots;    /* 候选槽表 */
    uint8_t         slot_n;

    /* 该窗口**已实测被引用的字形 tile**（各占 2 格）。运行时不读；
     * 供离线自检脚本核对"中文区有没有踩到引用字形"。
     * ⚠ 集合可能不完整，改翻译后应重新采集。 */
    const uint16_t *glyph_avoid;
    uint8_t         glyph_avoid_n;
};

/* 按模板地址查表；未登记返回 NULL（调用方回退默认，禁止猜场景）。 */
const struct Tm1WinCfg *scene_tm1_lookup(uint32_t tpl);

/* 由配置求行基址：curY <= row_y0 → title_base；否则 row_tab[r-1]，r clamp 到 [1,n]。 */
uint16_t scene_tm1_row_base(const struct Tm1WinCfg *cfg, uint8_t cur_y);

/* 由配置求行内子区起点，容量写入 *span。 */
uint16_t scene_tm1_sub_off(const struct Tm1WinCfg *cfg, uint8_t cur_x, uint16_t *span);

#endif /* TEXT_SCENE_H */
