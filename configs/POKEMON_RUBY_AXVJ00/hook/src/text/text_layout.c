/* ============================================================================
 * text_layout.c — tm1 落址**算法**（配置数据全部在 text_scene.c）
 *
 * 分层约定（2026-08-29 与用户确认）：
 *   text_scene.c / .h  —— 只放**声明式配置**：窗口模板地址、行基址表、分区规则
 *                         表、引用字形清单。每个窗口一条，数字显式写出。
 *   本文件             —— 只放**算法**：查表、求值、分区选择、汉字槽查询。
 *   配置与算法分离后，改布局只动 text_scene.c，改落址逻辑只动本文件。
 *
 * 本文件实现的四种模式：
 *   PARTITION —— 全窗动态分配（旧行为，标签 12px / 候选 8px）
 *   GRID      —— 位置式（旧行为，保留但不再投入）
 *   PTR       —— 全窗固定槽，16px 步进（旧行为）
 *   MIX       —— **按 curX 分区，每区独立选策略与字模**（当前使用）
 *
 * 为什么需要 MIX：
 *   PTR 的槽是"一字一固定槽"，幂等但每字独占 2 个 tilemap 列 ⇒ 16px 步进，
 *   字右边空 4px 显得散；DYN 相邻字共享 tile ⇒ 12px 紧凑，但要靠 win[0x18]
 *   做会话复位，状态多了就不如 PTR 稳。
 *   两者结合：文字固定、求稳的一段（标签列）用 PTR；要紧凑的一段（候选列）
 *   用 DYN 12px。
 *
 * ⚠ DYN 段不占"选中态"额外 tile：选中色只是换个前景色**重画一遍**到同一处。
 *   只有 PTR 固定槽才需要"红字镜像槽"（槽内容长期有效，红色版本必须另存）。
 * ==========================================================================*/

#include "game.h"
#include "text.h"
#include "text_scene.h"

/* 汉字固定槽表（PTR 段用）。
 * chs_slots.inc     —— 未选中态（普通色）
 * chs_slots_sel.inc —— 选中态（高亮色）；当前 PTR 段=标签列不吃高亮，表为空。
 * 两张表下标一一对应，由 scripts/gen_tm1_slots.py 生成，勿手改。 */
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
    return 0u;                       /* 未登记 → 调用方回退旧路径 */
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

/* PTR 段取槽：选中态用该汉字的红色镜像槽，未选中用普通槽。
 *
 * ⚠ 选中槽必须 **per-glyph**（按汉字），不能按"组内第几个字"共用一小撮槽：
 *   共用槽不属于任何字，光标一移动，新选中的字写进去，而旧选中行的 tilemap
 *   表项仍指向它们 → 旧行内容被顶掉（2026-08-29 实测的"移动光标文字替换"）。 */
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

    if (cfg->mode == TM1_MODE_GRID) {
        /* 位置式：不划子区、不复位（tile 由行列直接算出） */
        *span = 0u;
        return 0u;
    }
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

uint16_t scene_tm1_grid_num(const struct Tm1WinCfg *cfg, uint8_t cur_x,
                            uint8_t cur_y, uint8_t cur_ty, unsigned map_tx)
{
    int row = (int)(cur_y + cur_ty) - (int)cfg->grid_y0;
    int col = (int)(cur_x + map_tx) - (int)cfg->grid_x0;

    if (row < 0)
        row = 0;
    if (col < 0)
        col = 0;
    if (col >= (int)cfg->grid_stride)
        col = (int)cfg->grid_stride - 1;
    return (uint16_t)(cfg->grid_base
                      + (unsigned)row * cfg->grid_stride
                      + (unsigned)col);
}

uint16_t scene_tm1_mirror_of(const struct Tm1WinCfg *cfg, uint16_t tile)
{
    unsigned i;

    for (i = 0u; i < cfg->mirror_n; i++) {
        uint16_t src = cfg->mirrors[i].src;

        if (tile == src || tile == (uint16_t)(src + 1u))
            return (uint16_t)(cfg->mirrors[i].dst + (tile - src));
    }
    return 0u;
}

uint16_t scene_tm1_mirror_src(const struct Tm1WinCfg *cfg, uint16_t tile)
{
    unsigned i;

    for (i = 0u; i < cfg->mirror_n; i++) {
        if (cfg->mirrors[i].src == tile)
            return cfg->mirrors[i].dst;
    }
    return 0u;
}

/* ---- 分区选择（MIX 模式的核心）------------------------------------------*/

void tm1_zone_select(TextPrinter *win, uint32_t glyph, struct Tm1ZoneSel *out)
{
    const struct Tm1WinCfg *cfg;
    const struct Tm1Zone *z = 0;
    uint8_t cx;
    unsigned i;

    /* 先给一个安全的默认：动态、12px、不复位（等价"未登记窗口"的行为） */
    out->strategy = TM1_ZONE_DYN;
    out->font     = 0u;
    out->ptr_base = 0u;
    out->off      = 0u;
    out->span     = 0u;

    cfg = scene_tm1_lookup((uint32_t)(uintptr_t)win_template(win));
    if (cfg == 0)
        return;                                  /* 未登记窗口 */
    cx = win_u8(win, WIN_CURSOR_X);

    if (cfg->mode != TM1_MODE_MIX) {
        /* ---- 旧模式：整窗统一策略，行为与改造前完全一致 ---- */
        if (cfg->mode == TM1_MODE_PTR) {
            out->strategy = TM1_ZONE_PTR;
            out->ptr_base = chs_ptr_base(win, glyph);
            return;
        }
        /* PARTITION / GRID */
        out->strategy = TM1_ZONE_DYN;
        if (cfg->cand_font != 0u && cx >= cfg->col_label_max)
            out->font = cfg->cand_font;
        if (cfg->mode != TM1_MODE_GRID)
            out->off = scene_tm1_sub_off(cfg, cx, &out->span);
        return;
    }

    /* ---- MIX：按 curX 命中第一条 cx_hi 大于它的区 ---- */
    for (i = 0u; i < cfg->zone_n; i++) {
        if (cx < cfg->zones[i].cx_hi) {
            z = &cfg->zones[i];
            break;
        }
    }
    if (z == 0) {
        if (cfg->zone_n == 0u)
            return;                              /* 没配区表 → 保持默认 */
        z = &cfg->zones[cfg->zone_n - 1u];       /* 兜底最后一条 */
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
