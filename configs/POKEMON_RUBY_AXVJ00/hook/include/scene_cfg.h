/* ============================================================================
 * scene_cfg.h — v8 场景字号配置的结构定义 + 外部实例声明（2026-09-04）
 *
 * v8 起彻底简化：不再有「每行 tile 基址表」（row_tab）、不再有「候选分区偏移」
 * （off）、不再有「标题专用带」（title_base）。这些是 v6/v7 静态选址时代的产物，
 * 已被顺序 tile 分配器（tile_alloc.c 的 v8_alloc_tile）取代。
 *
 * 本头现在只保留**字号决策**所需的最小信息：哪个窗口、curX 分几段、每段多大字号。
 * 设置菜单（左标签 16px / 右候选 12px）即由此表达。
 *
 * 结构体命名沿用 V6 前缀（V6Zone / V6SceneRule）以避免与废弃 v4 孤儿头 scene.h
 * 的同名旧结构冲突——本文件是唯一被编译的权威定义。
 * ==========================================================================*/
#ifndef SCENE_CFG_H
#define SCENE_CFG_H

#include <stdint.h>
#include "game.h"

/* 一个列分区：curX < cx_hi 命中本区；末条 0xFF 兜底。只保留字号，无 off/row_tab。 */
struct V6Zone {
    uint8_t  cx_hi;    /* curX < cx_hi 命中本区 */
    uint8_t  font_px;  /* 16 = 标签固定 / 12 = 候选动态 / 8 = 小字 */
};

/* 一窗一条的字号配置（指定初始化器；用不到的字段别写）。 */
struct V6SceneRule {
    uint32_t         tpl;          /* win[0x00] 模板地址 = 唯一键 */
    const struct V6Zone *zones;
    uint8_t          zone_n;
};

/* 场景字号表（实例在 scene_cfg.c） */
extern const struct V6SceneRule kV6Scenes[];
extern const unsigned kV6SceneN;

/* ---- 查询访问器（实现见 PrintNextChar_hook.c；跨文件共享）------------- */
const struct V6SceneRule *v6_scene_lookup(uint32_t tpl);
const struct V6Zone      *v6_scene_zone(const struct V6SceneRule *r, uint8_t cx);
uint8_t  v6_scene_font(const struct V6SceneRule *r, uint8_t cx);

#endif /* SCENE_CFG_H */
