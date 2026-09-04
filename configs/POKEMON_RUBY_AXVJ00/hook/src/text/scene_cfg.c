/* ============================================================================
 * scene_cfg.c — v8 场景配置（纯数据，零方法；2026-09-04）
 *
 * 只放 const 配置表，不含任何函数实现。结构定义见 scene_cfg.h；
 * 查询访问器与渲染实现在 PrintNextChar_hook.c。
 *
 * 本文件两块内容：
 *   ① 字号配置 kV6Scenes（按窗口模板 tpl 分）——决定每个窗口、每个 curX 分区
 *      用多大字号（8/12/16）。v8 起不再维护任何 tile 基址/偏移/行带表。
 *   ② 避让带 kV8AvoidScenes（按硬件签名 DISPCNT+BGxCNT 分）——补顺序分配器
 *      扫 tilemap 活引用漏掉的官方 UI 占用。2026-09-04 新增，当前无消费方。
 *
 * 【格式约定】每个场景是一个独立的命名实例（static const struct V8AvoidScene
 *   kXxxScene），它的 bands 直接内联写在 .bands 里，不引用任何共享数组。
 *   该片段可由 gdb_patcher 的 export-scene 命令整块重新生成/替换。
 *
 * 本文件的避让带部分可由下列命令重新生成（重采日志后不必手抄）：
 *   python src/util/gdb_patcher.py export-scene --out -  \
 *          --reuse-names configs/POKEMON_RUBY_AXVJ00/hook/src/text/scene_cfg.c
 */
#include "scene_cfg.h"

// 设置菜单：curX 分区（16px key / 12px value）
static const struct V6Zone kOptZones[] = {
    { .cx_hi = 8u,    .font_px = 16u },   // 标签列（key）：16px 整格
    { .cx_hi = 0xFFu, .font_px = 12u },   // 候选列（value）：12px 相位共享
};

// 设置菜单（模板 0x081BB874）：左标签列 16px、右候选列 12px（用户拍板 2026-09-04）
static const struct V6SceneRule kOptionScene = {
    .tpl    = 0x081BB874u,
    .zones  = kOptZones,
    .zone_n = 2u,
};

// ---- 场景字号表（一窗一条）----
const struct V6SceneRule kV6Scenes[] = {
    kOptionScene,
};

const unsigned kV6SceneN = (unsigned)(sizeof(kV6Scenes) / sizeof(kV6Scenes[0]));

/* ============================================================================
 * 避让带（14 个场景，每个独立内联 bands，无共享数组）
 * 数据来源：src/util/work/POKEMON_RUBY_AXVJ00/gdb_patcher_log.log 的 27 条
 * [CBAVOID]（去重后 14 个硬件签名）。坐标 = 相对 char_base 的 tile 号 0..1023。
 * 🔴 当前无消费方，实机行为零变化。
 * ==========================================================================*/

// ----------------------------------------------------------------------------
// ① 继续游戏菜单（开场菜单）
//   日志行号 18658 / tpl 0x081BB46C / charBase 2 / font3 / textMode 3
//   DISPCNT=0x3140（mode0，仅 BG0 + OBJ 开）；BG0 cb2/sb30，BG3 cb0/sb28
//   内容 「继续游戏」
//   原始 cb2 = [0x002] [0x25B-0x263] [0x3C0-0x3CF]
//   构成：0x002=光标箭头；0x25B-0x263=菜单项图标章；0x3C0-0x3CF=窗框/边框映射
// ----------------------------------------------------------------------------
// 继续游戏菜单 —— tpl 0x081BB46C / charBase 2 / DISPCNT 0x3140
static const struct V8AvoidScene kContinueMenuScene = {
    .tpl       = 0x081BB46Cu,
    .char_base = 2u,
    .dispcnt   = 0x3140u,
    .bgcnt     = { 0x1F08u, 0x0000u, 0x0000u, 0x1600u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x002u, .hi = 0x002u },
        { .lo = 0x25Bu, .hi = 0x263u },
        { .lo = 0x3C0u, .hi = 0x3CFu },
    },
    .band_n    = 3u,
};

// ----------------------------------------------------------------------------
// ② 地图 HUD 全开（走图时四层 BG 全启用）
//   日志行号 18691 / tpl 0x081BB46C / charBase 2 / font3 / textMode 3
//   DISPCNT=0x7F60（mode0，BG0~3 + OBJ 全开，窗口 0/1 开）
//   内容 「119号道路」（地图名 + HUD 同屏）
//   原始 cb2 = [0x002] [0x25B-0x263] [0x3C0][0x3C2][0x3C4][0x3C6]
//   与①同源模板、占用几乎一致，区别只在 HUD 全开时窗框少占几个 tile（0x3C0-0x3C6）
// ----------------------------------------------------------------------------
// 地图 HUD 全开 —— tpl 0x081BB46C / charBase 2 / DISPCNT 0x7F60
static const struct V8AvoidScene kMapHudScene = {
    .tpl       = 0x081BB46Cu,
    .char_base = 2u,
    .dispcnt   = 0x7F60u,
    .bgcnt     = { 0x1F08u, 0x1D00u, 0x1C00u, 0x1E00u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x002u, .hi = 0x002u },
        { .lo = 0x25Bu, .hi = 0x263u },
        { .lo = 0x3C0u, .hi = 0x3C6u },
    },
    .band_n    = 3u,
};

// ----------------------------------------------------------------------------
// ③ 队伍窗 ★修 BUG「HP 条上方 Pokemon 状态图标被中文覆盖」
//   日志行号 19036 / tpl 0x081BB43C / charBase 1 / font4 / textMode 1
//   DISPCNT=0x1F40；BG0 cb1/sb30，BG1 cb0/sb7，BG2 cb2/sb15，BG3 cb0/sb6
//   内容 「バシャーモ」「ラグラージ」
//   原始 cb1 = [0x001-0x0D4][0x0D6-0x0DC][0x0DE-0x0EC][0x0EE-0x11A][0x11C-0x16D]
//   ⚠ 根因对上了：v8 分配器 lo=0x100 落在 [0x0EE-0x11A] 里，中文从 0x100 领号
//     直接压在状态图标上。避让后可用区 = 0x16E..0x3FF
// ----------------------------------------------------------------------------
// 队伍窗（BUG① 状态图标被覆盖）—— tpl 0x081BB43C / charBase 1 / DISPCNT 0x1F40
static const struct V8AvoidScene kPartyScene = {
    .tpl       = 0x081BB43Cu,
    .char_base = 1u,
    .dispcnt   = 0x1F40u,
    .bgcnt     = { 0x1E04u, 0x0700u, 0x0F08u, 0x0600u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x001u, .hi = 0x16Du },
    },
    .band_n    = 1u,
};

// ----------------------------------------------------------------------------
// ④ 宝可梦详情页「属性」页（模板 0x081BB5BC，charBase=2）
//   日志行号 19222 / font3 / textMode 1
//   DISPCNT=0x1F40；BG0 cb2/sb30，BG1 cb0/sb8，BG2 cb0/sb10，BG3 cb0/sb28
//   内容 「属性」
//   原始 cb2 = atlas 主体占满（13 段，合并后 0x003-0x211）+ cb3 图标章
//   本页尾段是 0x3A2-0x3A4（与⑤⑥⑦的 0x380-0x3A5 不同，故独立配置）
//   ⚠ 消费时注意：0x003-0x1FF 是 atlas；若连 atlas 一起避让，中文将被挤到 0x212 后
// ----------------------------------------------------------------------------
// 详情页④「属性」—— tpl 0x081BB5BC / charBase 2 / BG1 sb8 BG2 sb10
static const struct V8AvoidScene kPokeDetailAttrScene = {
    .tpl       = 0x081BB5BCu,
    .char_base = 2u,
    .dispcnt   = 0x1F40u,
    .bgcnt     = { 0x1E08u, 0x0800u, 0x0A00u, 0x1C00u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x003u, .hi = 0x211u },
        { .lo = 0x300u, .hi = 0x327u },
        { .lo = 0x340u, .hi = 0x367u },
        { .lo = 0x3A2u, .hi = 0x3A4u },
    },
    .band_n    = 4u,
};

// ----------------------------------------------------------------------------
// ⑤ 宝可梦详情页「宝可梦能力」页（模板 0x081BB5BC，charBase=2）
//   日志行号 19886 / font3 / textMode 1
//   DISPCNT=0x1F40；BG0 cb2/sb30，BG1 cb0/sb8，BG2 cb0/sb8，BG3 cb0/sb28
//   原始 cb2 atlas 占满 + cb3 图标章，合并后 4 段
// ----------------------------------------------------------------------------
// 详情页⑤「宝可梦能力」—— tpl 0x081BB5BC / charBase 2 / BG1 sb8 BG2 sb8
static const struct V8AvoidScene kPokeDetailAbilityScene = {
    .tpl       = 0x081BB5BCu,
    .char_base = 2u,
    .dispcnt   = 0x1F40u,
    .bgcnt     = { 0x1E08u, 0x0800u, 0x0800u, 0x1C00u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x003u, .hi = 0x211u },
        { .lo = 0x300u, .hi = 0x327u },
        { .lo = 0x340u, .hi = 0x367u },
        { .lo = 0x380u, .hi = 0x3A5u },
    },
    .band_n    = 4u,
};

// ----------------------------------------------------------------------------
// ⑥ 宝可梦详情页「对战技能」页（模板 0x081BB5BC，charBase=2）
//   日志行号 20143 / font3 / textMode 1
//   DISPCNT=0x1F40；BG0 cb2/sb30，BG1 cb0/sb10，BG2 cb0/sb8，BG3 cb0/sb28
//   原始 cb2 atlas 占满 + cb3 图标章，合并后 4 段（与⑤⑥⑦一致）
// ----------------------------------------------------------------------------
// 详情页⑥「对战技能」—— tpl 0x081BB5BC / charBase 2 / BG1 sb10 BG2 sb8
static const struct V8AvoidScene kPokeDetailMoveScene = {
    .tpl       = 0x081BB5BCu,
    .char_base = 2u,
    .dispcnt   = 0x1F40u,
    .bgcnt     = { 0x1E08u, 0x0A00u, 0x0800u, 0x1C00u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x003u, .hi = 0x211u },
        { .lo = 0x300u, .hi = 0x327u },
        { .lo = 0x340u, .hi = 0x367u },
        { .lo = 0x380u, .hi = 0x3A5u },
    },
    .band_n    = 4u,
};

// ----------------------------------------------------------------------------
// ⑦ 宝可梦详情页「华丽大赛技能」页（模板 0x081BB5BC，charBase=2）
//   日志行号 20358 / font3 / textMode 1
//   DISPCNT=0x1F40；BG0 cb2/sb30，BG1 cb0/sb10，BG2 cb0/sb12，BG3 cb0/sb28
//   原始 cb2 atlas 占满 + cb3 图标章，合并后 4 段（与⑤⑥⑦一致）
// ----------------------------------------------------------------------------
// 详情页⑦「华丽大赛技能」—— tpl 0x081BB5BC / charBase 2 / BG1 sb10 BG2 sb12
static const struct V8AvoidScene kPokeDetailContestScene = {
    .tpl       = 0x081BB5BCu,
    .char_base = 2u,
    .dispcnt   = 0x1F40u,
    .bgcnt     = { 0x1E08u, 0x0A00u, 0x0C00u, 0x1C00u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x003u, .hi = 0x211u },
        { .lo = 0x300u, .hi = 0x327u },
        { .lo = 0x340u, .hi = 0x367u },
        { .lo = 0x380u, .hi = 0x3A5u },
    },
    .band_n    = 4u,
};

// ----------------------------------------------------------------------------
// ⑧ 背包（学习装置页）
//   日志行号 20893 / tpl 0x081BB544 / charBase 2 / font3 / textMode 1
//   DISPCNT=0x1740（BG0+BG1+BG2+OBJ）；BG0 cb2/sb30，BG1 cb0/sb1，BG2 cb0/sb3
//   内容 「学习装置」「×02」
//   原始 cb2 = atlas 主体占满（10 段，合并后 0x003-0x208）；cb3 = [0x000-0x008]
//   构成：atlas（cb2 全满）+ cb3 头部 9 tile 图标章 + 0x3C4-0x3C7 数量/光标映射
// ----------------------------------------------------------------------------
// 背包 —— tpl 0x081BB544 / charBase 2 / DISPCNT 0x1740
static const struct V8AvoidScene kBagScene = {
    .tpl       = 0x081BB544u,
    .char_base = 2u,
    .dispcnt   = 0x1740u,
    .bgcnt     = { 0x1F08u, 0x0404u, 0x0C04u, 0x0000u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x003u, .hi = 0x208u },
        { .lo = 0x3C4u, .hi = 0x3C7u },
    },
    .band_n    = 2u,
};

// ----------------------------------------------------------------------------
// ⑨ 地图名弹窗（显示中）
//   日志行号 21250 / tpl 0x081BB49C / charBase 0 / font3 / textMode 1
//   DISPCNT=0x3F40（BG0~3+OBJ 全开）；BG2 cb2/sb29（4bpp）
//   内容 「查看丰缘地区的地图」「118号道路」
//   原始 cb0 全满（0x001-0x1FF）+ cb1 大段，34 段合并后 20 段
//   ⚠ charBase=0 意味着相对号 0..0x3FF 全程紧邻 cb0/cb1，两块几乎占满，
//     可用空隙只剩零星几处 —— 一旦消费本表，该场景中文将无地可放。
//     这是最需要先确认 atlas 是否该避让的场景，消费时优先验证。
// ----------------------------------------------------------------------------
// 地图名弹窗⑨（弹窗显示中）—— tpl 0x081BB49C / charBase 0 / DISPCNT 0x3F40
static const struct V8AvoidScene kMapNamePopScene = {
    .tpl       = 0x081BB49Cu,
    .char_base = 0u,
    .dispcnt   = 0x3F40u,
    .bgcnt     = { 0x1F00u, 0x1B0Cu, 0x1D08u, 0x1C08u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x001u, .hi = 0x2A6u },
        { .lo = 0x2B0u, .hi = 0x2B6u },
        { .lo = 0x2C0u, .hi = 0x2D1u },
        { .lo = 0x2D7u, .hi = 0x301u },
        { .lo = 0x305u, .hi = 0x30Bu },
        { .lo = 0x310u, .hi = 0x311u },
        { .lo = 0x315u, .hi = 0x31Bu },
        { .lo = 0x320u, .hi = 0x321u },
        { .lo = 0x325u, .hi = 0x32Bu },
        { .lo = 0x330u, .hi = 0x331u },
        { .lo = 0x335u, .hi = 0x33Au },
        { .lo = 0x341u, .hi = 0x349u },
        { .lo = 0x350u, .hi = 0x359u },
        { .lo = 0x360u, .hi = 0x367u },
        { .lo = 0x370u, .hi = 0x376u },
        { .lo = 0x380u, .hi = 0x386u },
        { .lo = 0x390u, .hi = 0x396u },
        { .lo = 0x3A0u, .hi = 0x3A6u },
        { .lo = 0x3B0u, .hi = 0x3B6u },
        { .lo = 0x3C0u, .hi = 0x3C1u },
    },
    .band_n    = 20u,
};

// ----------------------------------------------------------------------------
// ⑩ 地图场景（弹窗淡出后，BG2 转 8bpp）
//   日志行号 21274 / tpl 0x081BB49C / charBase 0 / font3 / textMode 1
//   DISPCNT=0x0200（BG0 关、OBJ 关、仅 BG1 开）；BG2 cb2/sb28（8bpp）
//   原始 cb0 全满 + cb1 大段，34 段合并后 18 段（比⑨少 2 段头部空隙被填）
// ----------------------------------------------------------------------------
// 地图场景⑩（弹窗淡出后，BG2 转 8bpp）—— tpl 0x081BB49C / charBase 0
static const struct V8AvoidScene kMapFieldScene = {
    .tpl       = 0x081BB49Cu,
    .char_base = 0u,
    .dispcnt   = 0x0200u,
    .bgcnt     = { 0x1F00u, 0x1B0Cu, 0x1C88u, 0x1C08u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x001u, .hi = 0x2D1u },
        { .lo = 0x2D7u, .hi = 0x301u },
        { .lo = 0x305u, .hi = 0x30Bu },
        { .lo = 0x310u, .hi = 0x311u },
        { .lo = 0x315u, .hi = 0x31Bu },
        { .lo = 0x320u, .hi = 0x321u },
        { .lo = 0x325u, .hi = 0x32Bu },
        { .lo = 0x330u, .hi = 0x331u },
        { .lo = 0x335u, .hi = 0x33Au },
        { .lo = 0x341u, .hi = 0x349u },
        { .lo = 0x350u, .hi = 0x359u },
        { .lo = 0x360u, .hi = 0x367u },
        { .lo = 0x370u, .hi = 0x376u },
        { .lo = 0x380u, .hi = 0x386u },
        { .lo = 0x390u, .hi = 0x396u },
        { .lo = 0x3A0u, .hi = 0x3A6u },
        { .lo = 0x3B0u, .hi = 0x3B6u },
        { .lo = 0x3C0u, .hi = 0x3C1u },
    },
    .band_n    = 18u,
};

// ----------------------------------------------------------------------------
// ⑪⑫ 战斗 UI（模板 0x081BB514，charBase=3）⚠ 高危
//   ⑪ 日志行号 21594「ユ…」「00000」  DISPCNT=0x0000（采集瞬间显示尚未开启）
//   ⑫ 日志行号 21650「17」「05」       DISPCNT=0x1F40
//   两条 BG0~3 完全一致（BG0 cb3/sb23，BG1 cb0/sb8，BG2 cb0/sb9，BG3 cb0/sb10）
//   合并后 2 段：0x003-0x208（cb3 atlas 全段 + cb4 头部）、0x210-0x223
//   ⚠⚠ 本批唯一踩进 OBJ 区的场景：charBase=3 ⇒ 相对号 0x200-0x3FF 落在物理
//     charBlock 4，而 cb4/cb5 是 OBJ 精灵专属 VRAM（0x06010000 起）。日志里 cb4
//     确有占用：0x210-0x213 / 0x216-0x21B / 0x21E-0x223。
//   ⚠⚠ 配套 BUG（已于 2026-09-04 修复）：tile_alloc.c 旧 v8_obj_charblock() 误读
//     DISPCNT bits[5:4] 当 OBJ charBlock，但 GBA 的 DISPCNT 根本没有「OBJ charBlock」
//     字段。OBJ tile 数据固定占 VRAM 0x06010000 起 = charBlock 4/5 恒为 OBJ。已改为
//     hi = (4 - char_base)*512 clamp 1024：char_base=3 ⇒ 512（正确拦住相对 512+ = OBJ 区）。
// ----------------------------------------------------------------------------
// 战斗 UI⑪（采集瞬间显示未开，DISPCNT=0x0000）—— tpl 0x081BB514 / charBase 3
static const struct V8AvoidScene kBattleUiBlankScene = {
    .tpl       = 0x081BB514u,
    .char_base = 3u,
    .dispcnt   = 0x0000u,
    .bgcnt     = { 0x170Cu, 0x0800u, 0x0900u, 0x0A00u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x003u, .hi = 0x208u },
        { .lo = 0x210u, .hi = 0x223u },
    },
    .band_n    = 2u,
};

// 战斗 UI⑫（正常态）—— tpl 0x081BB514 / charBase 3 / DISPCNT 0x1F40
static const struct V8AvoidScene kBattleUiScene = {
    .tpl       = 0x081BB514u,
    .char_base = 3u,
    .dispcnt   = 0x1F40u,
    .bgcnt     = { 0x170Cu, 0x0800u, 0x0900u, 0x0A00u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x003u, .hi = 0x208u },
        { .lo = 0x210u, .hi = 0x223u },
    },
    .band_n    = 2u,
};

// ----------------------------------------------------------------------------
// ⑬ 设置菜单 ★修 BUG「关闭按钮变橙色」
//   日志行号 23854 / tpl 0x081BB874 / charBase 2 / font3 / textMode 1
//   签名 DISPCNT=0x7140，仅 BG0 启用（cb2/sb15）；BG1/2/3 全关
//   原始 cb2 = [0x001-0x1FF]（整块占满）；cb3 = [0x000-0x008]
//   ⚠ 最大决策点：cb2 全满是官方预渲染 atlas。若连 atlas 一起避让，中文将被整体
//     挤到 0x209 之后（物理 charBlock3 = 0x0600C000 起）；当前 v8 的 lo=0x100 是在
//     atlas 内部开的洞，之所以看着没坏只因被踩的是已不显示的日文字形。消费策略
//     未拍板前，本表仅作数据留存。
// ----------------------------------------------------------------------------
// 设置菜单（BUG② 关闭按钮变橙色）—— tpl 0x081BB874 / charBase 2 / DISPCNT 0x7140
static const struct V8AvoidScene kOptionAvoidScene = {
    .tpl       = 0x081BB874u,
    .char_base = 2u,
    .dispcnt   = 0x7140u,
    .bgcnt     = { 0x0F08u, 0x0000u, 0x0000u, 0x1E00u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x001u, .hi = 0x208u },
    },
    .band_n    = 1u,
};

// ----------------------------------------------------------------------------
// ⑭ 战斗血条（tm2，8px 小字 / 数字带）
//   日志行号 24566 / tpl 0x081BB40C / charBase 0 / font4 / textMode 2
//   DISPCNT=0xBF40（BG0~3+OBJ 全开）
//   内容 「\CC0101\CC020236」（等级 + HP 数字的控制码串）
//   原始 cb0 = [0x001-0x02A] 等 6 段；cb1 = [0x201-0x209][0x210-0x25F] 等
//   构成：0x001-0x02A=血条窗框+LV/HP 数字映射；0x201-0x209/0x210-0x25F=cb1 HP 贴图
// ----------------------------------------------------------------------------
// 战斗血条 tm2 —— tpl 0x081BB40C / charBase 0 / DISPCNT 0xBF40
static const struct V8AvoidScene kBattleHpScene = {
    .tpl       = 0x081BB40Cu,
    .char_base = 0u,
    .dispcnt   = 0xBF40u,
    .bgcnt     = { 0x1800u, 0x1C04u, 0x1E04u, 0x1A08u },
    .bands     = (const struct V8AvoidBand[]) {
        { .lo = 0x001u, .hi = 0x02Au },
        { .lo = 0x201u, .hi = 0x209u },
        { .lo = 0x210u, .hi = 0x25Fu },
    },
    .band_n    = 3u,
};

const struct V8AvoidScene kV8AvoidScenes[] = {
    kContinueMenuScene,
    kMapHudScene,
    kPartyScene,
    kPokeDetailAttrScene,
    kPokeDetailAbilityScene,
    kPokeDetailMoveScene,
    kPokeDetailContestScene,
    kBagScene,
    kMapNamePopScene,
    kMapFieldScene,
    kBattleUiBlankScene,
    kBattleUiScene,
    kOptionAvoidScene,
    kBattleHpScene,
};

const unsigned kV8AvoidSceneN =
    (unsigned)(sizeof(kV8AvoidScenes) / sizeof(kV8AvoidScenes[0]));
