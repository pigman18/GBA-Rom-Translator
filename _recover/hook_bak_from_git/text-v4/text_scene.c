/* ============================================================================
 * text_scene.c — 窗口落址配置（**纯数据文件，一个函数都没有**）
 *
 * 声明式，一窗一条，键 = 窗口模板地址。算法（查表/求值/分区/槽查询/落址）
 * 在 src/text/text_layout.c，接口见 include/text_layout.h。
 *
 * 新增一个 tm1/tm3 窗口的步骤：
 *   1. gdb 采该窗口 curY/curX 集合、每会话字数、引用字形 tile（=1+PCS*2）。
 *      **几何必须以日志为准，勿凭印象。**
 *   2. 排行基址/搬位带，改翻译后重跑 scripts/gen_tm1_slots.py。
 *   3. 本文件加一组 static 数据（指定初始化器）+ 追加进 kWindows[]。
 *   4. 跑 scripts/check_tm1_scene.py 自检。
 * ==========================================================================*/

#include "text_scene.h"

/* ---- 设置（选项）窗口 — 模板 0x081BB874 ----------------------------------
 * 几何（gdb [CFF] 实测）：标题 curY=1；菜单行 curY=5..17（步 2）。
 * 候选 curX：慢@15 普通@19 快@23 ｜ 看@15 不看@23 ｜ 替换@15 打到底@22
 *            ｜ 单声道@15 立体声@22 ｜ 普通@15 LR/L(原生) ｜ 类型/7(原生)。
 * 行基址整段避开引用字形 33/49/111/139/255/323。
 * ⚠ r1..r6 全有中文候选，span 不能给 0（span=0 ⇒ win[0x18] 不复位 ⇒ 越界写，
 *   2026-08-29 实证）。r7(关闭) 无候选。 */
static const uint16_t kOptRows[7] = {
    0x033u,  /*  51  r1 对话速度   慢/普通/快 */
    0x08Du,  /* 141  r2 战斗动画   看/不看 */
    0x0ADu,  /* 173  r3 对战规则   替换/打到底 */
    0x0CDu,  /* 205  r4 声音       单声道/立体声 */
    0x101u,  /* 257  r5 按键模式   普通/LR/L ← "普通"是中文 */
    0x121u,  /* 289  r6 窗口       类型/7 */
    0x121u,  /* 289  r7 关闭       不用（无候选项） */
};

static const uint8_t kOptRowSpans[7] = {
    32u, 32u, 32u, 32u, 32u, 32u, 0u,
};

/* 容量算法：12px n 字最大 off = 4n-2，占 4n tile。
 * 同一行多个候选是独立打印会话，必须按 curX 分区，共用一段会互覆。
 * ⚠ "打到底/立体声"（3 字）在 cx=22：off=22、span=10 才收得进 32-tile 行界。 */
static const struct Tm1Zone kOptZones[] = {
    /* 标签列：固定槽 + 12px 字模 ⇒ 16px 步进。
     * ⚠ 别用 8px 小字库（FontChsSmall）画标签：字形有误（"战"→"対"实测）。 */
    { .cx_hi = 8u,   .strategy = TM1_ZONE_PTR, .font = 0u },
    { .cx_hi = 19u,  .strategy = TM1_ZONE_DYN, .font = 0u, .off = 0u,  .span = 12u },
    { .cx_hi = 22u,  .strategy = TM1_ZONE_DYN, .font = 0u, .off = 12u, .span = 10u },
    { .cx_hi = 0xFFu,.strategy = TM1_ZONE_DYN, .font = 0u, .off = 22u, .span = 10u },
};

static const struct WinCfg kOptWindow = {
    .name         = "OPTION",
    .tpl          = 0x081BB874u,
    .use_linear   = 1u,
    .row_tab      = kOptRows,
    .row_span_tab = kOptRowSpans,
    .row_tab_n    = 7u,
    .row_y0       = 3u,          /* r = (curY-3)>>1 → curY 5..17 ⇒ 行 1..7 */
    .row_shift    = 1u,
    .floor        = 0u,          /* 行内偏移由 zones 复位，不需要地板 */
    .zones        = kOptZones,
    .zone_n       = sizeof(kOptZones) / sizeof(kOptZones[0]),
};

/* ---- 图鉴条目屏 — 模板 0x081BB5BC（GRID：图标/盒子带需搬位）--------------*/
static const struct TileRemap kSummaryRemaps[] = {
    { .lo = CHS_UI_ICON_TILE_LO, .hi = CHS_UI_ICON_TILE_HI, .alt = CHS_UI_ICON_TILE_ALT },
    { .lo = CHS_PSS_B_VRAM_LO,   .hi = CHS_PSS_B_VRAM_HI,   .alt = CHS_PSS_B_VRAM_ALT },
};

static const struct WinCfg kSummaryWindow = {
    .name       = "SUMMARY",
    .tpl        = CHS_SUMMARY_TEMPLATE,
    .use_linear = 0u,              /* GRID */
    .remaps     = kSummaryRemaps,
    .remap_n    = sizeof(kSummaryRemaps) / sizeof(kSummaryRemaps[0]),
};

/* ============================================================================
 * gdb 采集登记（2026-08-30，来源 work/gdb_patcher_log.log）
 * 场景归属以 [InitTextPrinter] 日志的打印内容为准，不是猜的。
 * ==========================================================================*/

/* ---- 开始菜单 / 主菜单 — 模板 0x081BB46C（tm3 GRID，fn3）------------------
 * 日志实证：'ずかん/宝可梦/背包/领航员/保存/设置/退出/►'（开始菜单 8 项，
 * 左列 x=0..）+ '\CC010E继续游戏'（主菜单续档窗，右侧 x≥21：冒险时间/图鉴数）。
 * bak 的 mode2 menu 分支（CHS_MODE2_MENU_BAND=0x17A / ORIGIN_MENU=0x20 /
 * CHS_PARTY_MENU_LEFT=20 / TOP=13）只对本窗 x≥20 的深列生效 → 配置为 region。 */
static const struct Mode2Region kStartMenuRegions[] = {
    { .x_min = 20u, .y_min = 13u, .x_add = 1u, .y_sub = 13u,
      .band = CHS_MODE2_MENU_BAND, .origin = CHS_MODE2_ORIGIN_MENU },
};

static const struct WinCfg kStartMenuWindow = {
    .name       = "START_MENU",    /* 开始菜单 + 主菜单续档窗（同一模板） */
    .tpl        = 0x081BB46Cu,
    .use_linear = 0u,              /* GRID */
    .regions    = kStartMenuRegions,
    .region_n   = sizeof(kStartMenuRegions) / sizeof(kStartMenuRegions[0]),
};

/* ---- 对战菜单/选项窗 — 模板 0x081BB484（tm1 GRID，fn3）--------------------
 * 日志实证：'请选择/要做什么/查看能力/排序/携带物品/攀瀑/潜水'，候选列
 * x=0..1 与 21..22（右列），奇数行 curY=7..17。无搬位（官方公式+origin2）。 */
static const struct WinCfg kChoiceMenuWindow = {
    .name       = "CHOICE_MENU",   /* 对战/队伍的操作选项窗 */
    .tpl        = 0x081BB484u,
    .use_linear = 0u,              /* GRID，无搬位 */
};

/* ---- 战斗对话窗 — 模板 0x081BB3F4（tm0，fn3）------------------------------
 * 日志实证：'野生的…跳出来了/ゆけっ！/怎么办/战斗 背包'，TILE_BASE 0x90/0x190
 * （高区，自带安全距离）→ floor 必须为 0（bak 对 battle 直接跳过 floor；
 * 未登记 fallback 的 floor=4 会把战斗对话首字推右 4 tile）。 */
static const struct WinCfg kBattleDialogWindow = {
    .name       = "BATTLE_DIALOG",
    .tpl        = 0x081BB3F4u,
    .use_linear = 1u,              /* tm0 本就线性；登记为的是 floor=0 */
    .floor      = 0u,
};

/* ---- 队伍名单窗 — 模板 0x081BB43C（tm1，fn4 8px 小字）---------------------
 * 日志实证：'ＭＥＷ/ＥＸＰＬＯ/ジグザグマ/ラグラージ'，charBase=1、
 * tileData=0x06004000 独立区 → 线性直写安全，无需地板。 */
static const struct WinCfg kPartyNameWindow = {
    .name       = "PARTY_NAME",
    .tpl        = 0x081BB43Cu,
    .use_linear = 1u,              /* fn4 小字，charBase=1 独立 tile 区 */
    .floor      = 0u,
};

static const struct WinCfg kNamingConfirmWindow = {
    .name       = "NAMING_CONFIRM",
    .tpl        = 0x081BB694u,
    .use_linear = 0u,              /* GRID，默认路径（'你的名字是'） */
};

const struct WinCfg *const kWindows[] = {
    &kOptWindow,
    &kSummaryWindow,
    &kStartMenuWindow,
    &kChoiceMenuWindow,
    &kBattleDialogWindow,
    &kPartyNameWindow,
    &kNamingConfirmWindow,
};

const unsigned kWindowN = sizeof(kWindows) / sizeof(kWindows[0]);
