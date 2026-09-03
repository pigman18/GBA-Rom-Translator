/* ============================================================================
 * scene_cfg.h — v6 场景落址配置的结构定义 + 外部实例声明（2026-09-04 拆分）
 *
 * 分层（用户拍板「配置与实现分离」）：
 *   scene_cfg.c                 纯配置数据（一窗一条，只放 const 表，零方法）
 *   InitTextPrinter_hook.c      块边界相位复位 hook（InitTextPrinter 函数钩）
 *   PrintNextChar_hook.c        渲染层 + 查询访问器 + PrintNextChar 主 hook
 *
 * 本头只放「结构定义」与「跨文件共享的 extern」，不含任何函数实现。
 * 结构体命名沿用 v6（V6Zone / V6SceneRule），与废弃的 v4 孤儿头 scene.h
 * （同名旧结构）互不引用、互不冲突——本文件是唯一被编译的权威定义。
 *
 * ⚠ 配置语义（2026-09-01 定案，tile 号独立高水位 + 按行固定基址）：
 *   - 键 = 窗口模板地址（tpl = win[0x00]）；
 *   - curX 分区决定字号（16 = key 标签固定 / 12 = value 候选动态）；
 *   - 每行固定 tile 基址（row_tab），tile = 行基址 + 行内偏移(px>>3)*2；
 *   - 未命中回退全局高水位 v6_alloc_tile()（见 PrintNextChar_hook.c）。
 * ==========================================================================*/
#ifndef SCENE_CFG_H
#define SCENE_CFG_H

#include <stdint.h>
#include "game.h"

/* 一个列分区：curX < cx_hi 命中本区；末条 0xFF 兜底 */
struct V6Zone {
    uint8_t          cx_hi;    /* curX < cx_hi 命中本区 */
    uint8_t          font_px;  /* 16 = key 固定 / 12 = value 动态 */
    uint8_t          off;      /* 行内 tile 偏移起点（独立打印会话分区） */
    const uint16_t  *row_tab;  /* zone 级行基址表（NULL = 用主表 row_tab） */
};

/* 一窗一条的配置（指定初始化器；用不到的字段别写） */
struct V6SceneRule {
    uint32_t         tpl;          /* win[0x00] 模板地址 = 唯一键 */
    uint8_t          row_y0;       /* 行 0 的 curY */
    uint8_t          row_shift;    /* r = (curY - y0) >> shift */
    const uint16_t  *row_tab;      /* 每行 tile 基址（[1..row_n]） */
    uint8_t          row_n;
    uint16_t         title_base;   /* 标题行（curY <= row_y0）专用 tile 基址；0 = 无标题 */
    const struct V6Zone *zones;
    uint8_t          zone_n;
};

/* 场景规则表（实例在 scene_cfg.c） */
extern const struct V6SceneRule kV6Scenes[];
extern const unsigned kV6SceneN;

/* ---- 查询访问器（实现见 PrintNextChar_hook.c；跨文件共享）------------- */
const struct V6SceneRule *v6_scene_lookup(uint32_t tpl);
const struct V6Zone      *v6_scene_zone(const struct V6SceneRule *r, uint8_t cx);
uint8_t  v6_scene_font(const struct V6SceneRule *r, uint8_t cx);
int      v6_same_zone(const struct V6SceneRule *r, uint8_t cx_a, uint8_t cx_b);
uint16_t v6_scene_row_base(const struct V6SceneRule *r, const struct V6Zone *z,
                           uint8_t cy);

#endif /* SCENE_CFG_H */
