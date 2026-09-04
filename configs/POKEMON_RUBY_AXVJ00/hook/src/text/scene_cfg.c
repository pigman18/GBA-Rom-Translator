/* ============================================================================
 * scene_cfg.c — v8 场景配置（纯数据，零方法；2026-09-04）
 *
 * 只放 const 配置表，不含任何函数实现。结构定义见 scene_cfg.h；
 * 查询访问器与渲染实现在 PrintNextChar_hook.c。
 *
 * 本文件两块内容：
 *   ① 字号配置 kV6Scenes（按窗口模板 tpl 分）
 *   ② 避让带 kV8AvoidScenes（按 tpl 一条；bands 可含多 cb）
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

/* ============================================================================
 * 避让带（按 tpl 合并；同 tpl 多签名取并集）
 * ==========================================================================*/

// 继续游戏菜单 + 地图 HUD（同 tpl，并集取更宽窗框）
static const struct V8AvoidScene kContinueMenuScene = {
    .tpl    = 0x081BB46Cu,
    .bands  = (const struct V8AvoidBand[]) {
        { .char_base = 2u, .lo = 0x002u, .hi = 0x002u },
        { .char_base = 2u, .lo = 0x25Bu, .hi = 0x263u },
        { .char_base = 2u, .lo = 0x3C0u, .hi = 0x3CFu },
    },
    .band_n = 3u,
};

// 队伍窗 ★修 BUG「HP 条上方 Pokemon 状态图标被中文覆盖」
static const struct V8AvoidScene kPartyScene = {
    .tpl    = 0x081BB43Cu,
    .bands  = (const struct V8AvoidBand[]) {
        { .char_base = 1u, .lo = 0x001u, .hi = 0x16Du },
    },
    .band_n = 1u,
};

// 宝可梦详情（属性/能力/技能/华丽大赛 四页并集）
static const struct V8AvoidScene kPokeDetailScene = {
    .tpl    = 0x081BB5BCu,
    .bands  = (const struct V8AvoidBand[]) {
        { .char_base = 2u, .lo = 0x003u, .hi = 0x211u },
        { .char_base = 2u, .lo = 0x300u, .hi = 0x327u },
        { .char_base = 2u, .lo = 0x340u, .hi = 0x367u },
        { .char_base = 2u, .lo = 0x380u, .hi = 0x3A5u },
    },
    .band_n = 4u,
};

// 背包；cb3 头部图标章单独标
static const struct V8AvoidScene kBagScene = {
    .tpl    = 0x081BB544u,
    .bands  = (const struct V8AvoidBand[]) {
        { .char_base = 2u, .lo = 0x003u, .hi = 0x208u },
        { .char_base = 2u, .lo = 0x3C4u, .hi = 0x3C7u },
        { .char_base = 3u, .lo = 0x000u, .hi = 0x008u },
    },
    .band_n = 3u,
};

// 地图名弹窗 + 淡出后场地（并集取更密占用）
static const struct V8AvoidScene kMapScene = {
    .tpl    = 0x081BB49Cu,
    .bands  = (const struct V8AvoidBand[]) {
        { .char_base = 0u, .lo = 0x001u, .hi = 0x2D1u },
        { .char_base = 0u, .lo = 0x2D7u, .hi = 0x301u },
        { .char_base = 0u, .lo = 0x305u, .hi = 0x30Bu },
        { .char_base = 0u, .lo = 0x310u, .hi = 0x311u },
        { .char_base = 0u, .lo = 0x315u, .hi = 0x31Bu },
        { .char_base = 0u, .lo = 0x320u, .hi = 0x321u },
        { .char_base = 0u, .lo = 0x325u, .hi = 0x32Bu },
        { .char_base = 0u, .lo = 0x330u, .hi = 0x331u },
        { .char_base = 0u, .lo = 0x335u, .hi = 0x33Au },
        { .char_base = 0u, .lo = 0x341u, .hi = 0x349u },
        { .char_base = 0u, .lo = 0x350u, .hi = 0x359u },
        { .char_base = 0u, .lo = 0x360u, .hi = 0x367u },
        { .char_base = 0u, .lo = 0x370u, .hi = 0x376u },
        { .char_base = 0u, .lo = 0x380u, .hi = 0x386u },
        { .char_base = 0u, .lo = 0x390u, .hi = 0x396u },
        { .char_base = 0u, .lo = 0x3A0u, .hi = 0x3A6u },
        { .char_base = 0u, .lo = 0x3B0u, .hi = 0x3B6u },
        { .char_base = 0u, .lo = 0x3C0u, .hi = 0x3C1u },
    },
    .band_n = 18u,
};

// 战斗 UI（空白采集与正常态并集相同）
static const struct V8AvoidScene kBattleUiScene = {
    .tpl    = 0x081BB514u,
    .bands  = (const struct V8AvoidBand[]) {
        { .char_base = 3u, .lo = 0x003u, .hi = 0x208u },
        { .char_base = 3u, .lo = 0x210u, .hi = 0x223u },
    },
    .band_n = 2u,
};

// 设置菜单 ★修 BUG「关闭按钮变橙色」
static const struct V8AvoidScene kOptionAvoidScene = {
    .tpl    = 0x081BB874u,
    .bands  = (const struct V8AvoidBand[]) {
        { .char_base = 2u, .lo = 0x001u, .hi = 0x208u },
        { .char_base = 3u, .lo = 0x000u, .hi = 0x008u },
    },
    .band_n = 2u,
};

// 战斗血条 tm2：cb0 窗框/数字 + cb1 HP 贴图
static const struct V8AvoidScene kBattleHpScene = {
    .tpl    = 0x081BB40Cu,
    .bands  = (const struct V8AvoidBand[]) {
        { .char_base = 0u, .lo = 0x001u, .hi = 0x02Au },
        { .char_base = 1u, .lo = 0x001u, .hi = 0x009u },
        { .char_base = 1u, .lo = 0x010u, .hi = 0x05Fu },
    },
    .band_n = 3u,
};

const struct V8AvoidScene kV8AvoidScenes[] = {
    kContinueMenuScene,
    kPartyScene,
    kPokeDetailScene,
    kBagScene,
    kMapScene,
    kBattleUiScene,
    kOptionAvoidScene,
    kBattleHpScene,
};

const unsigned kV8AvoidSceneN =
    (unsigned)(sizeof(kV8AvoidScenes) / sizeof(kV8AvoidScenes[0]));
