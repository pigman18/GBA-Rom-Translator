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
 * 避让带（2026-09-04 gdb 采集，v8 补充）
 *
 * 用途：补 v8_alloc_begin「只扫文本 tilemap 活引用」漏掉的那部分官方占用 ——
 * 关闭按钮、血条上方状态图标、场景映射、其它 BG 层、扫描之后才绘制的 UI 元素，
 * 它们不在本窗口 tilemap 的活引用里，扫描永远看不到。
 *
 * 场景键 = 硬件签名（REG_DISPCNT + REG_BG0~3CNT），与 gdb_patcher --cb-survey
 * 的去重键一一对应。不用 tpl 当键的原因：同一个窗口模板会被多个场景复用
 * （实测 0x081BB5BC 同时出现在详情页 4 个不同硬件配置下），tpl 区分不开。
 *
 * 坐标 = 相对该窗口 charBase 的 tile 号（0..1023），与 v8_alloc_tile 的分配
 * 坐标系一致：相对号 t 落在物理 charBlock (char_base + t/512)。
 * 故一个场景的避让带 = cb[char_base] 原值 ∪ (cb[char_base+1] 原值 + 512)。
 *
 * 区间为【闭区间】[lo, hi]（与日志 [0xAAA-0xBBB] 写法一致），分配器消费时
 * 需自行转成半开。相邻缝隙 ≤2 tile 已合并（保守：多避让几个孤立空 tile，
 * 换取段数与 ROM 占用减半）。
 *
 * 消费方：tile_alloc.c 的 v8_alloc_begin() 在扫完 tilemap 活引用后，调用
 * v8_lookup_avoid() 按硬件签名（DISPCNT+BGxCNT，用 kV8SigBgMask 归一）查本表，
 * 命中即把该场景的 bands 标进位图——补 tilemap 扫不到的 UI 元素（关闭按钮 /
 * 状态图标 / 场景映射 / 其它 BG 层 / 扫描后才绘制的 UI）。签名未命中时按 tpl 兜底。
 * 消费策略（2026-09-04 拍板）：全量避让带一并消费——atlas 段 [0x003,0x1FF] 等也
 * 计入，中文整体挪到 atlas 之上（设置菜单 0x209 起）。14 个场景 bands 上限均 ≤0x3FF，
 * 仍在各自 cb 的相对 0~1023 区间内，不跨到 OBJ 区，内存余量足够。
 * ==========================================================================*/

/* 签名归一掩码：只比对影响 tile 归属的位 —— screenBase[12:8] / 8bpp[7] /
 * charBase[3:2]。priority[1:0] / mosaic[6] / 画面尺寸[15:14] 不参与，
 * 因为 gdb 日志只打印了解码后的 charBase/screenBase/8bpp，其余位未记录。
 * 将来重采时若改成打印原始 16 进制，可把掩码放宽到 0xFFFF。 */
#define kV8SigBgMask 0x1F8Cu

struct V8AvoidBand {
    uint16_t lo;    /* 闭区间起点（相对 char_base 的 tile 号） */
    uint16_t hi;    /* 闭区间终点 */
};

struct V8AvoidScene {
    uint32_t tpl;             /* 该签名下实际打印的窗口模板；仅人工对照，不参与匹配 */
    uint8_t  char_base;       /* 窗口 charBase（tpl[TPL_CHARBASE]）；避让带已按它折算 */
    uint16_t dispcnt;         /* REG_DISPCNT @0x04000000 原始值 */
    uint16_t bgcnt[4];        /* REG_BG0~3CNT @0x04000008/0A/0C/0E，已按 kV8SigBgMask 归一 */
    const struct V8AvoidBand *bands;
    uint8_t  band_n;
};

extern const struct V8AvoidScene kV8AvoidScenes[];
extern const unsigned kV8AvoidSceneN;

#endif /* SCENE_CFG_H */
