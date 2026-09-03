/* ============================================================================
 * InitTextPrinter_hook.c — InitTextPrinter 块边界相位复位 hook
 * （从 PrintNextChar_hook.c 独立出来，2026-09-04 拆分）
 *
 * 职责：hook 被劫持的 ROM 函数 InitTextPrinter（@0x08002C68），在文本块
 * 边界复位 12px 渲染的相位（struct ChsPhase）。不渲染任何字形、不碰 VRAM。
 *
 * 依赖：chs_phase_key_from（本文件）、v6_scene_lookup / v6_same_zone
 *   （PrintNextChar_hook.c 提供的查询访问器，声明见 scene_cfg.h）。
 *
 * =====================================================================
 * §块边界相位复位（2026-09-02 半透明空格 BUG）
 * ── 根因 ────────────────────────────────────────────────────────
 *  ChsPhase 是全局 8×8 槽表，靠行指纹 key 区分，但**没有文本块生命周期**——
 *  块结束/窗口重建后旧 px 赖在表里。主菜单「新游戏」每次进入 curX/tpl/TILE_BASE
 *  相同 ⇒ key 命中同一 slot、px 停在上一轮非零值(phase=4) ⇒ 第一字左 4px 既没
 *  画字也没补底色，露出 tile 脏数据 = 半透明空格。
 *  旧 `tx==0` 判据是**事后间接信号**（依赖 PrintNextChar 首字时 cursorTileX 恰
 *  为 0），在窗口复用/未重走 InitTextPrinter 的场景下不可靠 ⇒ 用户定夺必须
 *  **hook InitTextPrinter**：块边界是文本生命周期最权威的直接证据。
 * ── 续接保留 ────────────────────────────────────────────────────
 *  类型7「类型」(curX=15) →「8」(curX=18) 是两个独立文本块（两次 InitTextPrinter），
 *  但属同一候选值的顺序衔接，须续接 px（否则「8」落回行首覆盖「类」）。
 *  判据：scene 规则命中 + 新 curX 严格变大 + 同 zone（off 相同）⇒ 续接；
 *  否则（重进同一块 / 换行 / 换 zone / 非 scene 窗口）⇒ 复位 px。
 *  非 scene 窗口（主菜单等）恒复位——它们没有「同行后继块」场景，复位即消空格。
 * ===================================================================== */
#include "text.h"
#include "scene_cfg.h"

/* 用 InitTextPrinter 的参数直接构造「新块」行指纹 key（不读 win 字段——
 * hook 时 win[0x16]/[0x1C]/[0x1D] 还是旧值，本体尚未写入）。
 * 新块 CURSOR_TILE_Y 必然被 InitTextPrinter 归零 ⇒ 该项恒 0。 */
static uint16_t chs_phase_key_from(uint8_t *tpl, uint16_t tile_base, uint8_t cur_y)
{
    uint16_t w = tpl ? (uint16_t)(((uintptr_t)tpl >> 2) & 0xFFFFu) : 0;

    return (uint16_t)((tile_base
                       ^ ((uint16_t)cur_y << 8)
                       ^ w) | 0x8000u);
}

static void chs_init_phase(TextPrinter *win, uint16_t tile_base,
                           uint8_t cur_x, uint8_t cur_y)
{
    uint8_t *tpl = win_template(win);
    uint16_t key = chs_phase_key_from(tpl, tile_base, cur_y);
    volatile struct ChsPhase *tab = (volatile struct ChsPhase *)ADDR_CHS_PHASE;
    volatile struct ChsPhase *s = 0;
    const struct V6SceneRule *rule =
        v6_scene_lookup((uint32_t)(uintptr_t)tpl);
    unsigned i;

    for (i = 0; i < CHS_PHASE_COUNT; i++) {
        if (tab[i].key == key) {
            s = &tab[i];
            break;
        }
    }
    if (!s) {
        for (i = 0; i < CHS_PHASE_COUNT; i++) {
            if (tab[i].key == 0u) {
                s = &tab[i];
                break;
            }
        }
        if (!s)
            s = &tab[0];
        s->key = key;
        s->px  = 0;
        s->tx0 = 0;
        s->last_cx = cur_x;
        s->cur_tile = 0;
        return;                       /* 新分配：恒复位 */
    }

    /* 命中既有槽：同行后继块续接，否则复位 */
    if (rule && cur_x > s->last_cx && v6_same_zone(rule, cur_x, s->last_cx)) {
        s->tx0 = 0u;                  /* 续接：仅重锚块内游标锚点，px 保留 */
        s->last_cx = cur_x;
    } else {
        s->px  = 0u;
        s->tx0 = 0u;
        s->cur_tile = 0u;
        s->last_cx = cur_x;
    }
}

/* InitTextPrinter 入口钩（entry.s 跳板已重放前 8B、保 r0-r3、重排参数）。
 * 参数：win / tile_base(r2) / cur_x(r3) / cur_y(第5参数，栈)。只读不改 win。 */
void InitTextPrinter_hook_C(TextPrinter *win, uint16_t tile_base,
                            uint8_t cur_x, uint8_t cur_y)
{
    chs_init_phase(win, tile_base, cur_x, cur_y);
}
