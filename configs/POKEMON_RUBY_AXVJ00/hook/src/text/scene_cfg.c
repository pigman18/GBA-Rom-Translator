/* ============================================================================
 * scene_cfg.c — v8 场景字号配置（纯数据，零方法；2026-09-04）
 *
 * 只放 const 字号配置表，不含任何函数实现。结构定义见 scene_cfg.h；
 * 查询访问器与渲染实现在 PrintNextChar_hook.c。
 *
 * v8 起：tile 号统一走顺序分配器（tile_alloc.c），本文件只决定「每个窗口、
 * 每个 curX 分区用多大字号」，不再维护任何 tile 基址/偏移/行带表。
 *
 * 设置菜单（模板 0x081BB874）：左标签列 16px、右候选列 12px（用户拍板 2026-09-04）。
 * 分区只需 curX 阈值：curX < 8 → 标签 16px；否则 → 候选 12px。
 *
 * 旧静态行带表（kOptLabelRowBase / kOptRowBase）与 off 分区已随 v8 删除，
 * 不再需要——顺序分配器运行时读 tilemap 避让带自动选空闲区。
 */
#include "scene_cfg.h"

/* ---- 设置菜单：curX 分区（16px key / 12px value）---- */
static const struct V6Zone kOptZones[] = {
    { .cx_hi = 8u,    .font_px = 16u },   /* 标签列（key）：16px 整格 */
    { .cx_hi = 0xFFu, .font_px = 12u },   /* 候选列（value）：12px 相位共享 */
};

/* ---- 场景字号表（一窗一条）---- */
const struct V6SceneRule kV6Scenes[] = {
    { .tpl = 0x081BB874u, .zones = kOptZones, .zone_n = 2u },
};

const unsigned kV6SceneN = (unsigned)(sizeof(kV6Scenes) / sizeof(kV6Scenes[0]));
