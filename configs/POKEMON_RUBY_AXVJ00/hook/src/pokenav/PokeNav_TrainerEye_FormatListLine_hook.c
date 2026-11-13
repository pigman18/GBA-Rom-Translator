/* PokeNav_TrainerEye_FormatListLine_hook — 训练家之眼列表行拼接。
 *
 * origin（AXVJ @ 0x080F228C）：
 *   dest[0]=0x00;
 *   StringCopyPad(class, fill=0x00, width=10);
 *   StringCopyPad(name,  fill=0x00, width=5);   // 汉化盘已改指针+width=0x15
 *
 * 日文 1B≈1 格：短职业靠尾部 0x00 垫出与名字的列缝。
 * F7 一字 4B：长职业耗尽 width=10 后不再垫 →「香氛姐姐弥生」粘连。
 *
 * 本钩：完整拷职业后按 GetStringWidth 垫到 CLASS_COL_PX（1+10 格=88px），
 * 再拷名。缓冲仍写调用方 dest（blk+0x878C 起至下一字段约 64B 可用）。
 */
#include "game.h"

typedef void (*string_fill_t)(uint8_t *dest, uint32_t fill, uint32_t n);

/* 原函数字面量池（入口被钩后池仍在；译管线改表基址） */
#define LIT_REG_OFF      0x080F22DCu
#define LIT_TRAINERS     0x080F22E0u
#define LIT_COUNT_OFF    0x080F22E4u
#define LIT_CLASSES      0x080F22E8u

#define CLASS_STRIDE     0x2Cu
#define TRAINER_STRIDE   0x20u
#define CLASS_COL_PX     88u   /* 前导空格 8px + 10 格 ×8 */
#define LINE_MAX         60u
#define EMPTY_SPACES     0x20u /* 原 0x11；加长以免短清长残 */

static unsigned copy_pcs(uint8_t *dst, unsigned di, const uint8_t *src,
                         unsigned cap)
{
    unsigned n;

    if (!src)
        return di;
    for (n = 0u; n < 48u && di + 1u < cap; n++) {
        uint8_t c = src[n];

        if (c == 0xFFu)
            break;
        if (c == 0xF7u && n + 3u < 48u && src[n + 1u] == 0x00u &&
            di + 4u < cap) {
            dst[di++] = 0xF7;
            dst[di++] = 0x00;
            dst[di++] = src[n + 2u];
            dst[di++] = src[n + 3u];
            n += 3u;
        } else {
            dst[di++] = c;
        }
    }
    return di;
}

void PokeNav_TrainerEye_FormatListLine_hook_C(uint8_t *dest, uint32_t index)
{
    uint8_t *blk;
    uint16_t count;
    uint16_t trainer_id;
    uint8_t *reg;
    uint8_t *trainer;
    const uint8_t *class_str;
    const uint8_t *name_str;
    uint8_t *class_base;
    uint8_t *trainer_base;
    unsigned di;
    string_fill_t fill = (string_fill_t)(ADDR_STRING_FILL | 1u);

    index &= 0xffffu;
    if (!dest)
        return;

    blk = *(uint8_t **)(uintptr_t)ADDR_POKENAV_BLK_PTR;
    count = *(uint16_t *)(void *)(blk + *(uint32_t *)(uintptr_t)LIT_COUNT_OFF);
    if (index >= count) {
        fill(dest, 0u, EMPTY_SPACES);
        return;
    }

    reg = blk + *(uint32_t *)(uintptr_t)LIT_REG_OFF + (index * 8u);
    trainer_id = *(uint16_t *)(void *)reg;
    trainer_base =
        (uint8_t *)(uintptr_t)(*(uint32_t *)(uintptr_t)LIT_TRAINERS);
    trainer = trainer_base + ((uint32_t)trainer_id * TRAINER_STRIDE);
    class_base =
        (uint8_t *)(uintptr_t)(*(uint32_t *)(uintptr_t)LIT_CLASSES);
    class_str = class_base + ((uint32_t)trainer[1] * CLASS_STRIDE);
    name_str = *(const uint8_t *const *)(void *)(trainer + 4);

    di = 0u;
    dest[di++] = 0x00; /* 前导空格 */
    dest[di] = 0xFF;
    di = copy_pcs(dest, di, class_str, LINE_MAX);
    dest[di] = 0xFF;

    while (GetStringWidth(dest, LINE_MAX) < CLASS_COL_PX &&
           di + 2u < LINE_MAX) {
        dest[di++] = 0x00;
        dest[di] = 0xFF;
    }

    di = copy_pcs(dest, di, name_str, LINE_MAX);
    if (di < LINE_MAX)
        dest[di] = 0xFF;
    else
        dest[LINE_MAX - 1u] = 0xFF;
}
