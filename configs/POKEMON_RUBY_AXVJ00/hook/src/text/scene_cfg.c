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
    .win    = 0u,
    .zones  = (const struct V6Zone[]) {
        { .cx_hi = 8u,    .font_px = 16u },   // 标签列（key）：16px 整格
        { .cx_hi = 0xFFu, .font_px = 12u },   // 候选列（value）：12px 相位共享
    },
    .zone_n = 2u,
};

// 宝可导航窗（win 0x0202E658，模板 0x081BB49C）：起始列==4（描述/标签）16px，
// 其余起始列 Middle 8x12（用户拍板 2026-09-07）。
// 同模板的地图名弹窗 win 地址不同 → 不命中本条，维持默认 12px。
static const struct V6SceneRule kPokeNavScene = {
    .tpl    = 0x081BB49Cu,
    .win    = 0x0202E658u,
    .zones  = (const struct V6Zone[]) {
        { .cx_hi = 4u,    .font_px = V6_FONT_PX_MIDDLE },  // 起始列 0~3：Middle
        { .cx_hi = 5u,    .font_px = 16u },                // 起始列==4：16px 整格
        { .cx_hi = 0xFFu, .font_px = V6_FONT_PX_MIDDLE },  // 起始列 5+：Middle
    },
    .zone_n = 3u,
};

// 地图信息粉框（模板 0x081BB7E4，r3=13 居中，如「119号道路」）：
// 整模板 Middle 8x12。游戏按 8px/字算居中起点，12px 回退字形画出去溢出窄框
// 造成重叠踩踏花屏（2026-09-07 实机截图确认，gdb 日志 r3={13}）。
static const struct V6SceneRule kMapInfoScene = {
    .tpl    = 0x081BB7E4u,
    .win    = 0u,
    .zones  = (const struct V6Zone[]) {
        { .cx_hi = 0xFFu, .font_px = V6_FONT_PX_MIDDLE },  // 全部：Middle
    },
    .zone_n = 1u,
};

// 训练家信息窗（模板 0x081BB7B4，UISURVEY 疑似训练家）：
// 整模板 Middle 8x12（2026-09-07 实机观察走 12px 非预期，用户要求瘦体）。
static const struct V6SceneRule kTrainerInfoScene = {
    .tpl    = 0x081BB7B4u,
    .win    = 0u,
    .zones  = (const struct V6Zone[]) {
        { .cx_hi = 0xFFu, .font_px = V6_FONT_PX_MIDDLE },  // 全部：Middle
    },
    .zone_n = 1u,
};

const struct V6SceneRule kV6Scenes[] = {
    kOptionScene,
    kPokeNavScene,
    kMapInfoScene,
    kTrainerInfoScene,
};

const unsigned kV6SceneN = (unsigned)(sizeof(kV6Scenes) / sizeof(kV6Scenes[0]));

/* 避让带/线性表已废弃（2026-09-07）：静态 kV8AvoidScenes 与 kV8LinearScenes
 * 由 tile_alloc.c 动态三层探测（活引用 + VRAM 非空 + ours 段表）全面取代。
 */
