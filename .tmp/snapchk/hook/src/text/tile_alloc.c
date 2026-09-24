/* ============================================================================
 * tile_alloc.c — v21：只保留 12px 行相位
 *
 * v8 / v9 / v10 / v11 / v12 的分配器族**整体删除**：
 *   · 活引用位图扫描（v8_bit_* / v8_scan_entries / v8_tile_usable）
 *   · 队列游标（v8_alloc_n / v8_alloc_tile / v8_ui_alloc / v8_queue_cursor）
 *   · ours 账本（v8_ours_* / v8_ours_rebuild）
 *   · 官方资产上界（v8_official_end / v8_official_end_max）
 *   · 保留块掩码 + 会话状态（v10_resv_mask / v8q_*）
 *
 * 为什么能全删（15-0b 逐指令实证）
 * ================================
 *   `InitTextPrinter(win, text, tile_base, x, y)` → `win[0x16] = tile_base`（u16）
 *   `UpdateTilemap` → `strh tile | (win[0x0F] << 12)`（**原样写号，不加 charBase 偏移**）
 *   `InitWindowTileData` 的字形 worker 只对 **textMode == 1** 加载
 *   ⇒ 日版引擎本来就是「**位置定号 + 每窗口一块私有画布**」。
 *
 * v12 的 `v8_official_end(win) ∈ {535, 279}` 是把 `cap = 512`（待加载**字形个数**，
 * 即 progress 循环上界）误读成「号区间长度」造出来的**假**水位 —— 于是我们从一个
 * 不存在的坐标系发号，正好撞进官方 `{0x28, 0x90, 0xBC}` 三族画布，
 * 「每修一次换一种撞法」的根源就在这里。
 *
 * 位置定号下 `tile = TILE_BASE + TILE_OFFSET` 是**算出来的**，
 * 「读回 tilemap 猜这格是不是我们写的」失去存在理由 ⇒ 账本 / 闸门 / 扫描全删。
 *
 * 唯一保留：**行相位**（12px 步进跨列）。
 * ==========================================================================*/
#include "tile_alloc.h"
#include "text.h"

uint16_t v8_phase_get(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    /* 行键必须含 tileY：官方 FE 有时先推 CURSOR_TILE_Y，CURSOR_Y 稍后才变；
     * 只 xor curY 会漏检换行 → 奇数字行末相位 4 延续到下行首字。
     * 行键还必须含 **win 实例**：同场景多个窗口共用同一模板是常态，
     * 只用 tpl 时两个窗口同行打印会得到相同行键 ⇒ 相位不复位 ⇒
     * 第二个窗口首字带上一窗口的相位起步（2026-09-20 实机「右侧面板顶部
     * 出现左侧面板内容」）。win 指针唯一标识窗口实例。 */
    uint16_t row = 0u;

    if (tpl)
        row = (uint16_t)(((uintptr_t)win >> 2) ^ ((uintptr_t)tpl >> 3))
            ^ (uint16_t)((uint16_t)win_u8(win, WIN_CURSOR_Y) << 8)
            ^ (uint16_t)win_u8(win, WIN_CURSOR_TILE_Y);

    /* 行标识失配（换行 / 换窗口）→ 相位归零（新行从头画，杜绝跨窗残留）。 */
    if (*(volatile uint16_t *)ADDR_V8_PHASE_ROW != row) {
        *(volatile uint16_t *)ADDR_V8_PHASE_ROW = row;
        *(volatile uint16_t *)ADDR_V8_PHASE = 0u;
    }
    return *(volatile uint16_t *)ADDR_V8_PHASE;
}

void v8_phase_advance(uint16_t adv)
{
    *(volatile uint16_t *)ADDR_V8_PHASE =
        (uint16_t)(*(volatile uint16_t *)ADDR_V8_PHASE + adv);
}

/* 换行（FA/FB/FE）显式复位行相位 —— 见 tile_alloc.h 声明处的推导。
 * 🔴 只清「行内相位 + 行标识」两件；**不动任何 tile 号状态** ——
 *    v21 的 TILE_OFFSET 由引擎自己线性推进（跨行继续），
 *    正是为了让下一行的 tile 不与上一行重叠。 */
void v8_phase_reset(void)
{
    *(volatile uint16_t *)ADDR_V8_PHASE     = 0u;
    *(volatile uint16_t *)ADDR_V8_PHASE_ROW = 0u;
}
