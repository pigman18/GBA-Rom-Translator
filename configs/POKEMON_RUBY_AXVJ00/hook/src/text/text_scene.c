/* ============================================================================
 * text_scene.c — tm1 窗口布局配置表（声明式）+ 查表/求值
 *
 * 与旧 bak/text_original/text_scene.c 的区别：
 *   旧版是**代码式**启发门控（if 链推断当前是哪个场景，再选一套公式）；
 *   本版是**配置式**——每个窗口把"行基址表/列分区/容量"作为数据登记，
 *   查询只做一次模板地址精确匹配，不做任何推断。
 *
 * 新增一个 tm1 窗口的步骤：
 *   1. 用 gdb_patcher 采该窗口的 [CFF]/[UTM]，拿到：curY 集合、curX 集合、
 *      每段字数、以及原生实际引用的字形 tile（tile = 1 + PCS*2）。
 *   2. 在"可用区间 = [1,513) 减去引用字形 tile"里排布行基址。
 *      注意区间常被切成碎块，**单块装不下就用 row_tab 逐行给基址**。
 *   3. 在本文件底部加一组 static 数据，并把指针登记进 kTm1Windows[]。
 *   4. 跑离线自检（脚本比对 row_tab 与 glyph_avoid 是否相交）。
 * ==========================================================================*/

#include "text_scene.h"

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
 * → 连续空档只有 [3,33)=30 / [51,111)=60 / [141,255)=114 / [257,323)=66，
 *   单块装不下 7 行，故逐行给基址（不能用"起点+步长"）。
 * ==========================================================================*/

/* 行基址表。每行跨 28 tile：标签 16 + 候选 A 6 + B 4 + C 6。
 * ⚠ B(off18) 与 A(off16) 尾部重叠，合法性来自"这两槽不同时吃满"：
 *   B 只在 r1(普通 4tile)/r6(慢 2tile) 用到，这两行 A 分别只用 2 / 0 tile；
 *   A 用到 4/6 tile 的 r3(替换)/r4(立体声) 都不用 B。**改翻译后必须重核。** */
static const uint16_t kOptRows[7] = {
    0x08Du,  /* 141  r1 对话速度   [141,169) */
    0x0A9u,  /* 169  r2 战斗动画   [169,197) */
    0x0C5u,  /* 197  r3 对战规则   [197,225) */
    0x0E1u,  /* 225  r4 声音       [225,253) */
    0x101u,  /* 257  r5 按键模式   [257,285)   ← 跳过 255（引用字形） */
    0x11Du,  /* 285  r6 窗口       [285,313) */
    0x139u,  /* 313  r7 关闭       [313,321) 仅标签 8 tile，无候选 */
};

/* 候选槽。cx_hi 判定：curX<19 → A；<22 → B；其余 → C（0xFF 兜底）。 */
static const struct Tm1Slot kOptSlots[3] = {
    { 19u,   16u, 6u },   /* A：8px 3 字（立体声/单声道） */
    { 22u,   18u, 4u },   /* B：8px 2 字（普通） */
    { 0xFFu, 22u, 6u },   /* C：8px 3 字（打到底/立体声） */
};

/* 每行预留容量。前 6 行 = 标签16 + A6 + B4 + C6 = 28；
 * 末行（关闭）无候选列，只用到标签 6 tile，预留 8 即可 —— 若也按 28 预留，
 * [313,341) 会压到引用字形 323..340（scripts/check_tm1_scene.py 可检出）。 */
static const uint8_t kOptRowSpans[7] = {
    28u, 28u, 28u, 28u, 28u, 28u, 8u,
};

static const uint16_t kOptGlyphAvoid[24] = {
    0x001u, 0x021u, 0x031u, 0x06Fu, 0x077u, 0x08Bu, 0x0FFu, /* 1 33 49 111 119 139 255 */
    0x143u, 0x145u, 0x147u, 0x149u, 0x14Bu, 0x14Du, 0x14Fu, /* 323 325 327 329 331 333 335 */
    0x151u, 0x153u, 0x159u, 0x15Du, 0x171u, 0x18Du, 0x199u, /* 337 339 345 349 369 397 409 */
    0x1B7u, 0x1BFu, 0x1C3u,                                  /* 439 447 451 */
};

static const struct Tm1WinCfg kOptWindow = {
    "OPTION",
    0x081BB874u,
    kOptRows,   kOptRowSpans, 7u,
    3u, 1u,                 /* r = (curY - 3) >> 1  → 5,7,..,17 ⇒ 1..7 */
    0x03u,                  /* title_base：curY<=3 用 [3,19) */
    8u,                     /* curX < 8 = 标签列（12px） */
    0u,  16u,               /* 标签：off 0，span 16（4 字 × 12px） */
    kOptSlots,  3u,
    kOptGlyphAvoid, 24u,
};

/* ---- 登记表：新增窗口在此追加 ---- */
static const struct Tm1WinCfg *const kTm1Windows[] = {
    &kOptWindow,
};

const struct Tm1WinCfg *scene_tm1_lookup(uint32_t tpl)
{
    unsigned i;

    for (i = 0u; i < sizeof(kTm1Windows) / sizeof(kTm1Windows[0]); i++) {
        if (kTm1Windows[i]->tpl == tpl)
            return kTm1Windows[i];
    }
    return 0;               /* 未登记 → NULL，调用方回退默认，禁止猜场景 */
}

uint16_t scene_tm1_row_base(const struct Tm1WinCfg *cfg, uint8_t cur_y)
{
    unsigned r;

    if (cur_y <= cfg->row_y0)
        return cfg->title_base;
    r = (unsigned)(cur_y - cfg->row_y0) >> cfg->row_shift;
    if (r < 1u)
        r = 1u;
    if (r > cfg->row_tab_n)
        r = cfg->row_tab_n;
    return cfg->row_tab[r - 1u];
}

uint16_t scene_tm1_sub_off(const struct Tm1WinCfg *cfg, uint8_t cur_x, uint16_t *span)
{
    unsigned i;

    if (cur_x < cfg->col_label_max) {
        *span = (uint16_t)cfg->lbl_span;
        return (uint16_t)cfg->lbl_off;
    }
    for (i = 0u; i < cfg->slot_n; i++) {
        if (cur_x < cfg->slots[i].cx_hi) {
            *span = (uint16_t)cfg->slots[i].span;
            return (uint16_t)cfg->slots[i].off;
        }
    }
    /* 末条 cx_hi 应为 0xFF 兜底；保险起见回落最后一个槽 */
    *span = (uint16_t)cfg->slots[cfg->slot_n - 1u].span;
    return (uint16_t)cfg->slots[cfg->slot_n - 1u].off;
}
