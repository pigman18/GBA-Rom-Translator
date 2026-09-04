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

/* ============================================================================
 * 避让带（2026-09-04 gdb 采集；结构简化）
 *
 * 用途：补 v8_alloc_begin「只扫文本 tilemap 活引用」漏掉的官方占用，写入位图。
 * 真正领号仍是顺序扫整段 CB：碰到占用就跳到段末继续，直到上界——不靠哨兵。
 *
 * 配置面：tpl + bands[]（每段自带 char_base）+ band_n（手写段数，与内联数组一致）。
 * 消费时 (band.char_base - 窗.charBase)*512 折成窗口相对号再标位。
 *
 * 不入库、运行时再取：窗 charBase ← tpl；DISPCNT/BGxCNT ← 寄存器（匹配仅 tpl）。
 * ==========================================================================*/

struct V8AvoidBand {
    uint8_t  char_base; /* 本段相对哪块物理 charBlock（0~3） */
    uint16_t lo;        /* 闭区间起点（相对本 char_base） */
    uint16_t hi;        /* 闭区间终点 */
};

struct V8AvoidScene {
    uint32_t tpl;                    /* 窗口模板地址 = 匹配键 */
    const struct V8AvoidBand *bands; /* 内联复合字面量 */
    uint8_t  band_n;                 /* 段数（与 bands 条数一致的字面量） */
};

extern const struct V8AvoidScene kV8AvoidScenes[];
extern const unsigned kV8AvoidSceneN;

#endif /* SCENE_CFG_H */
