/* ============================================================================
 * tile_alloc.c — tm1 未登记窗口的中文行 tile 分配器（2026-08-29，独立文件）
 *
 * 根因（docs/逆向_20260829_官方文本引擎tile机制与图鉴碰撞根因.md）：
 *   官方 tm1 每字符只写 tilemap 引用（tileBase+char*2），字形 tile 在窗口创建时
 *   由 InitWindowTileData 静态预渲染（256 字形×2 tile），**官方没有动态 tile 分配**。
 *   win[0x18]（tileOff）是 mode0 专用草稿游标，tm1 从不推进；而 AddTextPrinter
 *   初始化（0x08002CA4）每行都清 0。我们的中文字形经 chs_tile_num 落址
 *   tile = win[0x16] + win[0x18] → 图鉴列表每行都画进 tile 1..7 → 行间互覆
 *   （全列表显示最后画的一行名字，滚动时随重绘顺序漂移）。
 *
 * 方案：**按行位置确定性分段**，不维护游标、不占 RAM：
 *   - 行 slot = (curY_total >> 1) % slot_n（官方每行 y=row*2+1，半 tile 行对齐）
 *   - 段基址 = base_tile + slot*slot_span（落在该场景确认空闲的 tile 区间）
 *   - win[0x18] = 段基址 - win[0x16]（使 chs_tile_num 的 win[0x16]+win[0x18]
 *     恰落在段内；chs_off_add 只在行内推进，行结束由官方清 0）
 *   - 重绘幂等：同一屏幕位置永远映射同一 slot，重印覆盖同一段。
 *
 * 行首判定：win[0x18]==0（官方每行清 0 且 mode1 从不推进 → 0 = 未分配标记）。
 *
 * 安全性：配置表只登记已验证场景；未登记窗口直接返回，行为与旧版完全一致。
 *   图鉴列表（模板 0x081BB784）空闲区间验证：
 *     - InitWindowTileData 预渲染占 tile 1..512（0x06008020..0x0600C01F）；
 *     - 初始 tilemap（ROM 0x0837BD90 LZ77→screenblock28）实测表项最大引用 tile 254；
 *     - 官方 mode1 只写 tileBase+char*2 ≤ 512 → tile 513..1023 全程无引用。
 *     - 16 slot × 24 tile = 384 ≤ 511（单行 ≤6 汉字 × 4 tile）。
 * ==========================================================================*/

#include "tile_alloc.h"

/* 图鉴列表窗口模板（ROM 原生数据，bin 不改写它；gdb CFF 日志实证 win[0x00] 取此值） */
#define ADDR_TPL_DEX_LIST  0x081BB784u

struct TileAllocCfg
{
    uint32_t tpl;          /* 窗口模板地址（win[0x00]） */
    uint16_t base_tile;    /* 分配段首 tile（tilemap 10bit 索引空间） */
    uint16_t slot_span;    /* 每 slot 宽（tile 数，≥ 单行最大字形数×4） */
    uint8_t  slot_n;       /* slot 数（行位置取模） */
};

static const struct TileAllocCfg kAllocWindows[] = {
    /* 图鉴列表：base 513，16 slot × 24 tile = 384，末 tile 896 < 1024 */
    { .tpl = ADDR_TPL_DEX_LIST, .base_tile = 513u, .slot_span = 24u, .slot_n = 16u },
};

void tile_alloc_tm1_row(TextPrinter *win)
{
    const struct TileAllocCfg *cfg = 0;
    uint32_t tpl = (uint32_t)(uintptr_t)win_template(win);
    unsigned i;

    if (win_u16(win, WIN_TILE_OFFSET) != 0u)
        return;                              /* 行内已分配（0 = 新行标记） */

    for (i = 0u; i < sizeof(kAllocWindows) / sizeof(kAllocWindows[0]); i++) {
        if (kAllocWindows[i].tpl == tpl) {
            cfg = &kAllocWindows[i];
            break;
        }
    }
    if (cfg == 0)
        return;                              /* 未登记场景：保持旧行为，禁止猜 */

    {
        unsigned y_total = (unsigned)win_u8(win, WIN_CURSOR_Y)
                         + win_u8(win, WIN_CURSOR_TILE_Y);
        unsigned slot   = (y_total >> 1) % cfg->slot_n;
        uint16_t base   = (uint16_t)(cfg->base_tile + slot * cfg->slot_span);

        win_set_u16(win, WIN_TILE_OFFSET,
                    (uint16_t)(base - win_u16(win, WIN_TILE_BASE)));
    }
}
