/* ============================================================================
 * scene_cfg.h — 场景字号配置：结构定义 + 外部实例声明（2026-09-11 重建）
 *
 * 本头只保留**字号决策**所需的最小信息：哪个窗口、curX 分几段、每段用哪档字库。
 * 不含任何 tile 基址/偏移/避让带（那些是 v6/v7 静态选址时代的产物，早已废弃）。
 *
 * 历史：v8 时代本头承载 kV6Scenes 字号表（设置菜单 16/12px、宝可导航 Middle…）。
 * 2026-09-08「两档制」把场景表整体退役（kV6Scenes 空表）；2026-09-11 按用户
 * 要求重建 —— 场景表恢复为「档位」选择器，档位本身收敛为三档（见下）。
 *
 * 结构体沿用 V6 前缀（V6Zone / V6SceneRule），与历史命名保持一致，便于对照
 * git 里 2026-09-04～09-08 的旧表。
 * ==========================================================================*/
#ifndef SCENE_CFG_H
#define SCENE_CFG_H

#include <stdint.h>
#include "game.h"

/* ---- 字号档位（resolve_draw 消费；值 = 该档的**步进像素**，兼作档位标识）----
 *   12 = 1bpp 大库 Big    11×11：步进 12、墨宽 11（历史 12px / 16px 档的归宿）
 *   10 = 1bpp 小库 Small   9×9 ：步进 10、墨宽 9 （历史 8px 档）
 *   13 = 1bpp Middle       9×11：步进 10、墨宽 9 （窄身全高；哨兵值 13 非步进）
 * 13 这个哨兵沿用 v8 时代的 V6_FONT_PX_MIDDLE（当年是 8×12 4bpp Middle），
 * 现在指向 9×11 的 1bpp Middle 库（ADDR_FONT_1BPP_MIDDLE）。 */
#define V6_FONT_PX_BIG      12u
#define V6_FONT_PX_SMALL    10u
#define V6_FONT_PX_MIDDLE   13u

/* 一个列分区：curX < cx_hi 命中本区；末条 0xFF 兜底。
 * curX 取 WIN_CURSOR_X（win+0x1A = 整个字符串的起始列）⇒ 分区是「按串」而非
 * 「按字符」粒度，同一串内字号恒定。 */
struct V6Zone {
    uint8_t cx_hi;    /* curX < cx_hi 命中本区 */
    uint8_t font_px;  /* V6_FONT_PX_BIG / _SMALL / _MIDDLE（历史值 16 并入 BIG） */
};

/* 一窗一条的字号配置。命中优先级：tpl+win 精确匹配 > tpl 通配（win=0） > 未命中 */
struct V6SceneRule {
    uint32_t tpl;            /* win[0x00] 模板地址 = 主键 */
    uint32_t win;            /* 0 = 任意窗口；非 0 = 仅该 win 地址命中
                              *（同一 win 被多模板复用时精确圈定，如领航员） */
    const struct V6Zone *zones;
    uint8_t  zone_n;
};

/* 场景字号表（实例在 scene_cfg.c） */
extern const struct V6SceneRule kV6Scenes[];
extern const unsigned kV6SceneN;

/* ---- 查询访问器（实现见 scene_cfg.c，渲染层 PrintNextChar_hook.c 消费）---- */
/* 命中优先级：tpl+win 精确匹配 > tpl 通配（win=0） > 未命中（返回 0） */
const struct V6SceneRule *v6_scene_lookup(uint32_t tpl, uint32_t win_addr);

/* 查某串的档位：命中分区 → V6_FONT_PX_*；未命中/无规则 → 0（调用方走默认档）。
 * 内部做归一化：历史值 16（整格标签）并入 V6_FONT_PX_BIG。 */
uint8_t v6_scene_font(uint32_t tpl, uint32_t win_addr, uint8_t cx);

#endif /* SCENE_CFG_H */
