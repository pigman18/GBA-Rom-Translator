/* ============================================================================
 * text_scene.c — tm1 窗口布局**配置表**（声明式，只有数据）
 *
 * ⚠ 本文件只放配置；查表/求值/分区选择在 text_layout.c。
 *   改布局动本文件，改落址逻辑动 text_layout.c（2026-08-29 与用户确认）。
 *
 * 新增一个 tm1 窗口的步骤：
 *   1. gdb_patcher 采该窗口 [CFF]/[UTM]：curY/curX 集合、每会话字数、
 *      引用字形 tile（= 1 + PCS*2）。**几何必须以日志为准，勿凭印象**
 *      （"打到底在 cx=22 不是 19..21"这个 BUG 就是凭印象写配置踩的）。
 *   2. 排 DYN 行基址（避开引用字形），重跑 scripts/gen_tm1_slots.py 生成槽表。
 *   3. 本文件加一组 static 数据（指定初始化器）+ 登记进 kTm1Windows[]。
 *   4. 跑 scripts/check_tm1_scene.py（查：越行界 / 越区窗口 / 会话足迹重叠）。
 * ==========================================================================*/

#include "text_scene.h"

/* ============================================================================
 * 设置（选项）窗口 — 模板 0x081BB874
 *
 * 几何（gdb [CFF] 实测，以打印时的值为准）：
 *   标题 curY=1（cx=4）   菜单行 curY = 5,7,9,11,13,15,17（cx=4）
 *   候选 curX：慢@15 普通@19 快@23 ｜ 看@15 不看@23 ｜ 替换@15 打到底@22
 *              ｜ 单声道@15 立体声@22 ｜ 普通@15 LR@20·L@23(原生) ｜ 类型@15 7@18(原生)
 * ==========================================================================*/

/* ---- 行基址表（**DYN 候选列专用**；标签列走 PTR 固定槽，不吃这里）--------
 * 选点整段避开引用字形 33/49/111/139/255/323：
 *   51 [51,83) ⊂ [51,111)；141/173/205 ⊂ [141,255)；257/289 ⊂ [257,323)
 * ⚠ r1..r6 全都有中文候选，一行都不能给 span=0 —— span=0 会让该行中文
 *   不复位 win[0x18] 而写到越界地址（2026-08-29 实证）。只有 r7(关闭)无候选。 */
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

/* ---- 分区规则表：按 curX 命中第一条 cx_hi 大于它的区，末条 0xFF 兜底 -------
 * 容量算法：12px n 字最大 off = 4n-2，占 4n tile（3 字 → 10 tile）。
 * 同一行的多个候选是各自独立的打印会话，必须按 curX 分区，共用一段会互覆。
 * ⚠ **打到底 / 立体声（3 字）在 ④ 档 cx=22**：off 必须 ≤ 22，足迹 [22,32)
 *   才收得进 32-tile 行界。off=24 时尾部两格压进下一行候选区 ——
 *   表现为行尾残留"单"、单声道首字随重绘变碎片（2026-08-29 实测 BUG）。 */
static const struct Tm1Zone kOptZones[] = {
    /* 标签列：固定槽 + 12px 字模 ⇒ 16px 步进。
     * ⚠ 不要用 8px 小字库（FontChsSmall）画标签：字形有误（"战"→"対"实测）。 */
    { .cx_hi = 8u,   .strategy = TM1_ZONE_PTR, .font = 0u },
    { .cx_hi = 19u,  .strategy = TM1_ZONE_DYN, .font = 0u, .off = 0u,  .span = 12u }, /* 候选A @15 最长"单声道" */
    { .cx_hi = 22u,  .strategy = TM1_ZONE_DYN, .font = 0u, .off = 12u, .span = 10u }, /* 候选B @19 "普通" */
    { .cx_hi = 0xFFu,.strategy = TM1_ZONE_DYN, .font = 0u, .off = 22u, .span = 10u }, /* 候选C @22 打到底/立体声 */
};

/* ---- 不得被中文/槽表占用的 tile（各占 2 格）------------------------------
 * ① gdb 实测被本窗口引用的字形  ② 已知特殊保留区（▶ 字形 / 菜单光标）
 * ⚠ 清单不完整是主要风险：发现新的乱码字符 → 反推 tile（= 1 + PCS*2）
 *   → 加进来 → 重跑 scripts/check_tm1_scene.py 与 gen_tm1_slots.py。 */
static const uint16_t kOptGlyphAvoid[26] = {
    0x001u, 0x021u, 0x031u, 0x06Fu, 0x077u, 0x08Bu, 0x0FFu, /* 1 33 49 111 119 139 255 */
    0x143u, 0x145u, 0x147u, 0x149u, 0x14Bu, 0x14Du, 0x14Fu, /* 323 325 327 329 331 333 335 */
    0x151u, 0x153u, 0x159u, 0x15Du, 0x171u, 0x18Du, 0x199u, /* 337 339 345 349 369 397 409 */
    0x1B7u, 0x1BFu, 0x1C3u,                                  /* 439 447 451 */
    0x1DFu, 0x1E1u,                                          /* ② 479 ▶字形 / 481 菜单光标 */
};

/* ---- 窗口配置（必须用指定初始化器；zone_n/glyph_avoid_n 用 sizeof 防脱节）*/
static const struct Tm1WinCfg kOptWindow = {
    .name          = "OPTION",
    .tpl           = 0x081BB874u,
    .row_tab       = kOptRows,
    .row_span_tab  = kOptRowSpans,
    .row_tab_n     = 7u,
    .row_y0        = 3u,   /* r = (curY-3)>>1 → curY 5..17 ⇒ 行 1..7 */
    .row_shift     = 1u,
    .zones         = kOptZones,
    .zone_n        = sizeof(kOptZones) / sizeof(kOptZones[0]),
    .glyph_avoid   = kOptGlyphAvoid,
    .glyph_avoid_n = sizeof(kOptGlyphAvoid) / sizeof(kOptGlyphAvoid[0]),
};

/* ---- 登记表：新增窗口在此追加（算法在 text_layout.c）--------------------*/
const struct Tm1WinCfg *const kTm1Windows[] = {
    &kOptWindow,
};

const unsigned kTm1WindowN = sizeof(kTm1Windows) / sizeof(kTm1Windows[0]);
