/* ============================================================================
 * text_scene.c — tm1 窗口布局**配置表**（声明式，只有数据）
 *
 * ⚠ 本文件**只放配置**，不放算法。
 *   所有查表/求值/分区选择在 src/text/text_layout.c。
 *   分层约定（2026-08-29 与用户确认）：改布局动本文件，改落址逻辑动 text_layout.c。
 *
 * 与旧 bak/text_original/text_scene.c 的区别：
 *   旧版是**代码式**启发门控（if 链推断当前是哪个场景，再选一套公式）；
 *   本版是**配置式**——每个窗口把"行基址表/分区规则/容量"作为数据登记，
 *   查询只做一次模板地址精确匹配，不做任何推断。
 *
 * 新增一个 tm1 窗口的步骤：
 *   1. 用 gdb_patcher 采该窗口的 [CFF]/[UTM]，拿到：curY 集合、curX 集合、
 *      每段字数、以及原生实际引用的字形 tile（tile = 1 + PCS*2）。
 *   2. 在"可用区间 = [1,513) 减去引用字形、减去 PTR 槽表"里排布行基址。
 *   3. 在本文件底部加一组 static 数据，并把指针登记进 kTm1Windows[]。
 *   4. 跑 scripts/check_rom_hook.py 与 gen_tm1_slots.py 自检。
 * ==========================================================================*/

#include "text_scene.h"

/* ============================================================================
 * 布局模式切换：改这一行即可。
 *   TM1_MODE_MIX       —— **当前使用**。按 curX 分区，每区独立选策略与字模
 *                          （见 kOptZones：标签列 PTR 16px / 候选列 DYN 12px）
 *   TM1_MODE_PARTITION —— 全窗动态分配，标签 12px + 候选 8px
 *   TM1_MODE_PTR       —— 全窗固定槽，16px 步进
 *   TM1_MODE_GRID      —— 位置式（bak 的做法），连测未过，保留但不再投入
 * ==========================================================================*/
/* 2026-08-29 模式演进：
 *   PARTITION — 12px 标签 + 8px 候选，可用但候选被迫小字（tile 预算所限）。
 *   GRID      — 连测两轮未过（v12 Ｌ/Ｒ 乱码、v13 连数字也乱），不再投入。
 *   PTR       — 全 16px 步进：一字一固定槽，幂等不串，但字右边空 4px 显散。
 *   MIX       — 折中（当前）：**稳的地方用 PTR，要紧凑的地方用 DYN**。
 *               标签列文字固定 → PTR 求稳；候选列要紧凑 → DYN 12px。
 *               关键：两者**共享同一套空闲 tile**，互不重叠即可共存。 */
#define OPTION_MODE   TM1_MODE_MIX

/* ============================================================================
 * 设置（选项）窗口 — 模板 0x081BB874
 *
 * 几何（gdb [CFF] 实测，以打印时的值为准）：
 *   标题 curY=1（curX=4，4 字）       菜单行 curY = 5,7,9,11,13,15,17（curX=4）
 *   候选 curX ∈ {15,18,19,20,22,23}，每行 2~3 个并列候选，各自独立会话
 *
 * 已实测引用的字形 tile（各占 2 格）：
 *   1 33 49 111 119 | 139 | 255 | 323 325 327 329 331 333 335 337 339
 *   345 349 369 397 409 439 447 451
 * ==========================================================================*/

/* ---- 行基址表（**DYN 段专用**：候选列落址 = row_tab[r-1] + 区内 off）----
 *
 * ⚠ 本表**只给动态区用**。标签列走 PTR 固定槽，不吃这里的空间 —— 这正是
 *   混合模式能塞下 12px 候选的原因：把标签挪走后，候选独占下面这几块。
 *
 * 每行 32 tile（候选 A 12 + B 12 + C 8，见 kOptZones）。
 * ⚠ 容量算法：12px 每字 off 推进 4，但**首字只推进 2**（pass2 相位 0 时 +0），
 *   所以 n 字实际最大 off = 4n-2，占 **4n** 个 tile（3 字 → off 到 10，占 12）。
 *
 * ⚠ **r1..r6 全都有中文候选，一行都不能省**（2026-08-29 10.PNG 实证）：
 *     按键模式行 = 普通 / LR / L —— "普通"是中文，要占行区。
 *     之前误判它全是字母、给了"不占行区"，结果"普通"落到
 *     行基址 + 未复位的 win[0x18] 上，**写到了 charblock 外面**。
 *   只有 r7（关闭）真的没有候选项。
 *
 * 选点（整段避开引用字形 33/49/111/139/255/323）：
 *     51 [51,83)                              ⊂ [51,111)
 *    141 [141,173) 173 [173,205) 205 [205,237) ⊂ [141,255)
 *    257 [257,289) 289 [289,321)              ⊂ [257,323) */
static const uint16_t kOptRows[7] = {
    0x033u,  /*  51  r1 对话速度   [51,83)   慢/普通/快 */
    0x08Du,  /* 141  r2 战斗动画   [141,173) 看/不看 */
    0x0ADu,  /* 173  r3 对战规则   [173,205) 替换/打到底 */
    0x0CDu,  /* 205  r4 声音       [205,237) 单声道/立体声 */
    0x101u,  /* 257  r5 按键模式   [257,289) 普通/LR/L ← 有中文！ */
    0x121u,  /* 289  r6 窗口       [289,321) 类型/1 */
    0x121u,  /* 289  r7 关闭       不用（无候选项） */
};

/* 每行预留容量。r7 无候选 = 0；**其余 6 行都必须给足**，
 * 给 0 会导致该行的中文不复位 win[0x18] 而写到越界地址。 */
static const uint8_t kOptRowSpans[7] = {
    32u, 32u, 32u, 32u, 32u, 32u, 0u,
};

/* ---- 分区规则表（MIX 模式的核心）---------------------------------------
 * 按 curX 从上往下匹配，**第一条 cx_hi 大于 curX 的区命中**；末条必须 0xFF 兜底。
 *
 *   strategy  TM1_ZONE_PTR = 固定槽，每字独占 2 个 tilemap 列 = 16px 步进
 *             TM1_ZONE_DYN = 动态分配，相邻字共享 tile = 12px 步进
 *   font      0 = 12px 常规字模，4 = 8px 小字
 *   off/span  仅 DYN 用：行内 tile 偏移与容量（落址 = row_tab + off）
 *
 * 候选列为什么要拆成 B/C 三档：同一行的多个候选是**各自独立的打印会话**
 * （curX 分别约 15 / 19 / 22），共用一个子区会互相覆盖（历史 BUG：
 * "快 快通 快"）。所以按 curX 分档，各占一段 off。
 * ------------------------------------------------------------------------*/
static const struct Tm1Zone kOptZones[] = {
    /* ① 标签列（key）curX<8：PTR 固定槽 + **12px 字模** ⇒ 16px 步进。
     *    （字模 12px、格子 16px，右边空 4px —— 这就是"左 16"的观感。
     *      用户指示：优先布局，不必为省 tile 委屈显示。）
     *    ⚠ **不要用 8px 字库画标签**：实测 FontChsSmall 字形有误，
     *      "对战规则"的"战"会显示成日文"対"（2026-08-29 10.PNG 实证）。 */
    { 8u,    TM1_ZONE_PTR, 0u,  0u,  0u },

    /* ② 候选 A（value）curX 8..18：DYN **12px** 紧凑排列。
     *    最长 3 字（单声道）⇒ off 推进到 10，占 12 tile。 */
    { 19u,   TM1_ZONE_DYN, 0u,  0u, 12u },

    /* ③ 候选 B curX 19..21：DYN 12px（最长 3 字：打到底 / 立体声） */
    { 22u,   TM1_ZONE_DYN, 0u, 12u, 12u },

    /* ④ 候选 C curX>=22：DYN 12px。
     *    实测只有"快"（1 字，占 4 tile）和字母"L"（走原生，不吃中文区），
     *    给 8 留 2 字余量。⚠ 若哪天这里出现 3 字候选，要扩到 12 并重排 kOptRows。 */
    { 0xFFu, TM1_ZONE_DYN, 0u, 24u,  8u },
};

/* 候选槽（仅 PARTITION 回退时用；MIX 模式不读本表） */
static const struct Tm1Slot kOptSlots[3] = {
    { 19u,   16u, 6u },
    { 22u,   18u, 4u },
    { 0xFFu, 22u, 6u },
};

/* 不得被中文占用、也不得被镜像槽占用的 tile（各占 2 格）。两类：
 *   ① gdb 实测被引用的字形
 *   ② 已知特殊用途的保留区
 * ⚠ 清单不完整是这类方案的主要风险：漏一个就表现为某个非中文字符变乱码。
 *   发现新的乱码字符 → 反推其 tile（= 1 + PCS*2）→ 加进来 → 重跑自检。 */
static const uint16_t kOptGlyphAvoid[26] = {
    0x001u, 0x021u, 0x031u, 0x06Fu, 0x077u, 0x08Bu, 0x0FFu, /* 1 33 49 111 119 139 255 */
    0x143u, 0x145u, 0x147u, 0x149u, 0x14Bu, 0x14Du, 0x14Fu, /* 323 325 327 329 331 333 335 */
    0x151u, 0x153u, 0x159u, 0x15Du, 0x171u, 0x18Du, 0x199u, /* 337 339 345 349 369 397 409 */
    0x1B7u, 0x1BFu, 0x1C3u,                                  /* 439 447 451 */
    0x1DFu, 0x1E1u,                                          /* ② 479 ▶字形 / 481 菜单光标 */
};

/* GRID 模式参数（OPTION_MODE = TM1_MODE_GRID 时生效），保留供回退。 */
#define OPT_GRID_BASE    0x028u
#define OPT_GRID_STRIDE  23u
#define OPT_GRID_X0      4u
#define OPT_GRID_Y0      1u

#define OPT_PROT_ROW0    0u
#define OPT_PROT_ROW1    17u
#define OPT_PROT_COL0    0u
#define OPT_PROT_COL1    22u

/* 字形镜像表（仅 GRID 模式需要） */
#if OPTION_MODE == TM1_MODE_GRID
static const struct Tm1Mirror kOptMirrors[22] = {
    { 0x031u, 0x1C6u }, { 0x06Fu, 0x1C8u }, { 0x077u, 0x1CAu },
    { 0x08Bu, 0x1CCu }, { 0x0FFu, 0x1CEu }, { 0x143u, 0x1D0u },
    { 0x145u, 0x1D2u }, { 0x147u, 0x1D4u }, { 0x149u, 0x1D6u },
    { 0x14Bu, 0x1D8u }, { 0x14Du, 0x1DAu }, { 0x14Fu, 0x1DCu },
    { 0x151u, 0x1E4u }, { 0x153u, 0x1E6u }, { 0x159u, 0x1E8u },
    { 0x15Du, 0x1EAu }, { 0x171u, 0x1ECu }, { 0x18Du, 0x1EEu },
    { 0x199u, 0x1F0u }, { 0x1B7u, 0x1F2u }, { 0x1BFu, 0x1F4u },
    { 0x1C3u, 0x1F6u },
};
#define OPT_MIRRORS   kOptMirrors
#define OPT_MIRROR_N  22u
#else
#define OPT_MIRRORS   ((const struct Tm1Mirror *)0)
#define OPT_MIRROR_N  0u
#endif

/* 候选列字模（仅 PARTITION 回退时用：容量紧 → 8px） */
#if OPTION_MODE == TM1_MODE_PARTITION
#define OPT_CAND_FONT  4u
#else
#define OPT_CAND_FONT  0u
#endif

/* 字段顺序必须与 text_scene.h 的 struct Tm1WinCfg 一致 */
static const struct Tm1WinCfg kOptWindow = {
    "OPTION",
    0x081BB874u,
    OPTION_MODE,
    kOptRows,   kOptRowSpans, 7u,
    3u, 1u,                 /* row_y0=3, row_shift=1 ⇒ r=(curY-3)>>1 → 5,7,..,17 ⇒ 1..7 */
    0x03u,                  /* title_base：curY<=3 用（MIX 下标题走 PTR，用不到） */
    8u,                     /* col_label_max：curX < 8 = 标签列（PARTITION 回退用） */
    0u,  16u,               /* 标签：off 0，span 16（PARTITION 回退用） */
    kOptSlots,  3u,
    OPT_CAND_FONT,
    OPT_GRID_BASE, OPT_GRID_STRIDE, OPT_GRID_X0, OPT_GRID_Y0,
    OPT_PROT_ROW0, OPT_PROT_ROW1, OPT_PROT_COL0, OPT_PROT_COL1,
    OPT_MIRRORS, OPT_MIRROR_N,
    kOptGlyphAvoid, 26u,
    kOptZones, sizeof(kOptZones) / sizeof(kOptZones[0]),
};

/* ---- 登记表：新增窗口在此追加（算法在 text_layout.c）--------------------*/
const struct Tm1WinCfg *const kTm1Windows[] = {
    &kOptWindow,
};

const unsigned kTm1WindowN = sizeof(kTm1Windows) / sizeof(kTm1Windows[0]);
