/* ============================================================================
 * scene_cfg.c — v8 场景配置（纯数据，零方法；2026-09-04）
 *
 * 只放 const 配置表，不含任何函数实现。结构定义见 scene_cfg.h；
 * 查询访问器与渲染实现在 PrintNextChar_hook.c。
 *
 * 本文件两块内容：
 *   ① 字号配置 kV6Scenes（按窗口模板 tpl 分）
 *
 * 【格式约定】全部内联复合字面量；band_n / zone_n 写死数字。
 * DISPCNT/BGxCNT 不入库。可由 gdb_patcher export-scene 重生成：
 *   python src/util/gdb_patcher.py export-scene --out -  \
 *          --reuse-names configs/POKEMON_RUBY_AXVJ00/hook/src/text/scene_cfg.c
 */
#include "scene_cfg.h"

/* ============================================================================
 * 字号配置
 * ==========================================================================*/

// 设置菜单（模板 0x081BB874）：左标签列 16px、右候选列 12px（用户拍板 2026-09-04）
static const struct V6SceneRule kOptionScene = {
    .tpl    = 0x081BB874u,
    .zones  = (const struct V6Zone[]) {
        { .cx_hi = 8u,    .font_px = 16u },   // 标签列（key）：16px 整格
        { .cx_hi = 0xFFu, .font_px = 12u },   // 候选列（value）：12px 相位共享
    },
    .zone_n = 2u,
};

const struct V6SceneRule kV6Scenes[] = {
    kOptionScene,
};

const unsigned kV6SceneN = (unsigned)(sizeof(kV6Scenes) / sizeof(kV6Scenes[0]));

/* 避让带/线性表已废弃（2026-09-07）：静态 kV8AvoidScenes 与 kV8LinearScenes
 * 由 tile_alloc.c 动态三层探测（活引用 + VRAM 非空 + ours 段表）全面取代。
 */
