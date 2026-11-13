/* PokeNav_TrainerEye_PrintTitle_hook — DMA 路径红条（EF558）。
 * 详情页实测多走 EF43C 精灵路径（P34b）；本钩覆盖另一入口。
 */
#include "game.h"
#include "text_grid.h"

void PokeNav_TrainerEye_TitleBlit_hook_C(uint8_t *str, uint8_t *dest,
                                         uint32_t c1, uint32_t c2);

#define OFF_DEST       0xD1E4u
#define ADDR_GET_SOME  0x080022ECu
#define VRAM_BASE      0x06010000u
#define DMA3_SAD       0x040000D4u

void PokeNav_TrainerEye_PrintTitle_hook_C(uint8_t *str)
{
    uint8_t *blk;
    uint8_t *dest;
    uint32_t tile;
    typedef uint32_t (*get_fn_t)(uint32_t);
    get_fn_t get_some = (get_fn_t)(ADDR_GET_SOME | 1u);
    volatile uint32_t *dma3 = (volatile uint32_t *)(uintptr_t)DMA3_SAD;

    if (!str)
        return;
    blk = *(uint8_t **)(uintptr_t)ADDR_POKENAV_BLK_PTR;
    dest = blk + OFF_DEST;
    PokeNav_TrainerEye_TitleBlit_hook_C(str, dest, 1u, 1u);

    tile = get_some(0x1Au) & 0xFFFFu;
    if (tile == 0xFFFFu)
        return;
    dma3[0] = (uint32_t)(uintptr_t)dest;
    dma3[1] = (tile << 5) + VRAM_BASE;
    dma3[2] = 0x84000200u;
    (void)dma3[2];
}
