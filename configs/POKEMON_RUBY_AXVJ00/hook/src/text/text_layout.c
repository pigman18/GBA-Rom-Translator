/* ============================================================================
 * text_layout.c — tm1 落址**算法**（配置数据全部在 text_scene.c）
 *
 * 分层约定（2026-08-29 与用户确认）：
 *   text_scene.c / .h —— 只放**声明式配置**：窗口模板地址、行基址表、分区规则
 *                        表、引用字形清单。每个窗口一条，数字显式写出。
 *   本文件            —— 只放**算法**：查表、求值、分区选择、汉字槽查询。
 *
 * 布局只有一种（PTR 区 + DYN 区，按 curX 分区）：
 *   PTR（固定槽）：一字一固定槽，幂等——重绘必然落在同一处。
 *     ⚠ 选中槽必须 **per-glyph**（按汉字），不能按"组内第几个字"共用一小撮槽：
 *       共用槽不属于任何字，光标一移动，新选中的字写进去，而旧选中行的 tilemap
 *       表项仍指向它们 → 旧行内容被顶掉（2026-08-29 实测的"移动光标文字替换"）。
 *   DYN（动态分配）：落址 = 行基址 + 行内偏移(win[0x18])，靠 zone 的 off/span
 *     做会话复位（chs_blit 消费），相邻字共享 tile ⇒ 12px 步进。
 *
 * 未登记窗口：scene_tm1_lookup 返回 NULL → tm1_zone_select 保持默认
 * （DYN/off0/span0），chs_tile_num 回退 win[0x16] 线性式。不猜场景。
 * ==========================================================================*/

#include "game.h"
#include "text.h"
#include "text_scene.h"

/* 汉字固定槽表（PTR 区用）。
 * chs_slots.inc     —— 未选中态（普通色）
 * chs_slots_sel.inc —— 选中态（高亮色）；当前 PTR 区=标签列不吃高亮，表为空。
 * 两张表下标一一对应，由 scripts/gen_tm1_slots.py 生成，勿手改。
 * ⚠ 改翻译（增删汉字）后必须重新生成，否则新汉字查不到槽 → 回退动态路径。 */
#include "chs_slots.inc"
#include "chs_slots_sel.inc"

/* ---- 汉字 → 固定槽 ------------------------------------------------------*/

static uint16_t chs_slot_of(uint32_t glyph)
{
    uint16_t g = (uint16_t)(glyph & 0xFFFFu);
    unsigned i;

    for (i = 0u; i < sizeof(kOptChsSlots) / sizeof(kOptChsSlots[0]); i++) {
        if (kOptChsSlots[i].glyph == g)
            return kOptChsSlots[i].slot;
    }
    return 0u;                       /* 未登记 → 调用方回退动态路径 */
}

static uint16_t chs_sel_slot_of(uint32_t glyph)
{
    uint16_t g = (uint16_t)(glyph & 0xFFFFu);
    unsigned i;

    for (i = 0u; i < sizeof(kOptChsSelSlots) / sizeof(kOptChsSelSlots[0]); i++) {
        if (kOptChsSelSlots[i].glyph == g)
            return kOptChsSelSlots[i].slot;
    }
    return 0u;                       /* 未登记 → 退回普通槽 */
}

/* PTR 区取槽：选中态用该汉字的红色镜像槽，未选中用普通槽。 */
static uint16_t chs_ptr_base(TextPrinter *win, uint32_t glyph)
{
    uint8_t fg_ov = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;

    if (fg_ov == (uint8_t)OPT_FG_SELECTED) {
        uint16_t sel = chs_sel_slot_of(glyph);

        if (sel != 0u)
            return sel;
        /* 未登记汉字：退回普通槽。只会被染成选中色，不会替换别的字 */
    }
    (void)win;
    return chs_slot_of(glyph);
}

/* ---- 配置查表（数据在 text_scene.c）-------------------------------------*/

const struct Tm1WinCfg *scene_tm1_lookup(uint32_t tpl)
{
    unsigned i;

    for (i = 0u; i < kTm1WindowN; i++) {
        if (kTm1Windows[i]->tpl == tpl)
            return kTm1Windows[i];
    }
    return 0;               /* 未登记 → NULL，调用方回退默认，禁止猜场景 */
}

/* 行基址：r = (curY - row_y0) >> row_shift，clamp 到 [1, row_tab_n]。
 * curY <= row_y0 的会话（标题/标签）在当前配置下走 PTR，不会到这里；
 * 防御起见 clamp 到第 1 行（不做场景猜测）。 */
uint16_t scene_tm1_row_base(const struct Tm1WinCfg *cfg, uint8_t cur_y)
{
    unsigned r;

    if (cur_y <= cfg->row_y0) {
        r = 1u;
    } else {
        r = (unsigned)(cur_y - cfg->row_y0) >> cfg->row_shift;
        if (r < 1u)
            r = 1u;
        if (r > cfg->row_tab_n)
            r = cfg->row_tab_n;
    }
    return cfg->row_tab[r - 1u];
}

/* ---- 分区选择（chs_blit 的落址入口）-------------------------------------*/

void tm1_zone_select(TextPrinter *win, uint32_t glyph, struct Tm1ZoneSel *out)
{
    const struct Tm1WinCfg *cfg;
    const struct Tm1Zone *z = 0;
    uint8_t cx;
    unsigned i;

    /* 先给一个安全的默认：动态、12px、不复位（= 未登记窗口的行为） */
    out->strategy = TM1_ZONE_DYN;
    out->font     = 0u;
    out->ptr_base = 0u;
    out->off      = 0u;
    out->span     = 0u;

    cfg = scene_tm1_lookup((uint32_t)(uintptr_t)win_template(win));
    if (cfg == 0)
        return;                                  /* 未登记窗口 */
    cx = win_u8(win, WIN_CURSOR_X);

    /* MIX：按 curX 命中第一条 cx_hi 大于它的区；末条 0xFF 兜底 */
    for (i = 0u; i < cfg->zone_n; i++) {
        if (cx < cfg->zones[i].cx_hi) {
            z = &cfg->zones[i];
            break;
        }
    }
    if (z == 0) {
        if (cfg->zone_n == 0u)
            return;                              /* 没配区表 → 保持默认 */
        z = &cfg->zones[cfg->zone_n - 1u];
    }

    out->strategy = z->strategy;
    out->font     = z->font;

    if (z->strategy == TM1_ZONE_PTR) {
        out->ptr_base = chs_ptr_base(win, glyph);
        out->off      = 0u;
        out->span     = 0u;
    } else {
        out->ptr_base = 0u;
        out->off      = (uint16_t)z->off;
        out->span     = (uint16_t)z->span;
    }
}
