/* ============================================================================
 * chs_canvas.c — v21「窗口私有画布」分配器实现
 *
 * 表落固定 EWRAM 地址（`link/game.ld` 无 .data/.bss，不能放 static 初值）。
 * 地址区 0x0203FF50..0x0203FF8F 原属 v8/v9/v10 的分配器状态（全部废弃），
 * 见 include/game.h 的说明。0x0203FFD0 起是活区，严禁越过。
 *
 * 🔴 本工程是 `-ffreestanding -nostdlib`，**没有 libc** ⇒ 结构体数组整体赋值
 *    会被编译成 `memcpy` 而链接失败。所以表拆成两条**标量数组**，
 *    FIFO 淘汰逐元素赋值。
 *
 * 内存布局（相对 ADDR_V21_CANVAS = 0x0203FF50）：
 *     +0x00  u32 win[6]   窗口实例地址（0 = 空槽）        24 B → 0x0203FF68
 *     +0x18  u16 base[6]  画布基址（相对该窗口 charBase） 12 B → 0x0203FF74
 *     （RR / MAGIC 另址：0x0203FF80 / 0x0203FF82）
 * ==========================================================================*/
#include "chs_canvas.h"

#define CHS_CANVAS_SLOTS  6u
#define CHS_CANVAS_MAGIC  0x21C7u
#define CHS_CANVAS_BASE_OFF  0x18u   /* base[] 相对表头的字节偏移 */

static volatile uint32_t *slot_win(void)
{
    return (volatile uint32_t *)(uintptr_t)ADDR_V21_CANVAS;
}

static volatile uint16_t *slot_base(void)
{
    return (volatile uint16_t *)(uintptr_t)(ADDR_V21_CANVAS + CHS_CANVAS_BASE_OFF);
}

static volatile uint16_t *rr(void)
{
    return (volatile uint16_t *)(uintptr_t)ADDR_V21_CANVAS_RR;
}

static volatile uint16_t *magic(void)
{
    return (volatile uint16_t *)(uintptr_t)ADDR_V21_CANVAS_MAGIC;
}

void chs_canvas_init_once(void)
{
    unsigned i;

    if (*magic() == CHS_CANVAS_MAGIC)
        return;
    *magic() = CHS_CANVAS_MAGIC;
    for (i = 0u; i < CHS_CANVAS_SLOTS; i++) {
        slot_win()[i] = 0u;
        slot_base()[i] = 0u;
    }
    *rr() = 0u;
}

uint16_t chs_canvas_base_for(TextPrinter *win)
{
    uint32_t w = (uint32_t)(uintptr_t)win;
    unsigned i;

    if (w == 0u)
        return CHS_CANVAS_POOL_LO;

    chs_canvas_init_once();

    /* 同一窗口实例恒定复用同一块画布（多次 InitTextPrinter 不换址，
     * 否则屏幕上已有的内容会与新址不符）。 */
    for (i = 0u; i < CHS_CANVAS_SLOTS; i++) {
        if (slot_win()[i] == w)
            return slot_base()[i];
    }

    {
        /* 新实例：按块轮转。块只决定**起点** —— TILE_OFFSET 是纯线性推进、
         * 不设上界，所以「同屏只有 1 个中文窗口」时它会自然用满整池。 */
        uint16_t base = (uint16_t)(CHS_CANVAS_POOL_LO
                                   + (uint16_t)(*rr() % CHS_CANVAS_BLOCKS)
                                     * CHS_CANVAS_BLOCK_SZ);
        (*rr())++;

        for (i = 0u; i < CHS_CANVAS_SLOTS; i++) {
            if (slot_win()[i] == 0u)
                break;
        }
        if (i == CHS_CANVAS_SLOTS) {
            /* 表满：FIFO 淘汰最旧一项。窗口实例地址会被引擎复用，
             * 旧映射留着只会挡住新窗口。 */
            unsigned k;
            for (k = 1u; k < CHS_CANVAS_SLOTS; k++) {
                slot_win()[k - 1u] = slot_win()[k];
                slot_base()[k - 1u] = slot_base()[k];
            }
            i = CHS_CANVAS_SLOTS - 1u;
        }
        slot_win()[i] = w;
        slot_base()[i] = base;
        return base;
    }
}
