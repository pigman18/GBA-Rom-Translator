/* PokeNav_TrainerEye_DetailEnter_hook — 训练家之眼进详情。
 *
 * origin（AXVJ @ 0x080EBF9C）：清两计数 → 按选中项取说明表指针 →
 * 顺 FF 拆后继串指针写入 blk+0xD110 起。
 *
 * case4：FormatListLine → PrintTitle → (list/left) → 本函数。
 * 右栏：Blank 窗 0x2F 后重打红条（标题串在 blk+0x878C）。
 *
 * 左栏：地点 (1,6) 与统计 (0,5) 同窗 0x25。整窗 Blank 会抹地点。
 * 只 Blank 立绘区 (1,8)–(11,12) 清统计残墨，保留地点行。
 */
#include "game.h"

typedef void (*menu_blank_t)(uint32_t left, uint32_t top, uint32_t right,
                             uint32_t bottom);
typedef void (*init_win_t)(uint32_t window_id);

void PokeNav_TrainerEye_PrintTitle_hook_C(uint8_t *str);

#define ADDR_INIT_MENU_WINDOW 0x0806F158u

#define OFF_CNT_A     0x306u
#define OFF_CNT_B     0xD15Cu
#define OFF_SEL       0x8772u
#define OFF_REG       0xCEECu
#define OFF_STR_SLOTS 0xD110u
#define OFF_LIST_LINE 0x878Cu
#define DESC_TABLE    0x083B8E10u

#define LIST_WIN  0x2Fu
#define LEFT_WIN  0x25u
#define RIGHT_L   13u
#define RIGHT_T   2u
#define RIGHT_R   28u
#define RIGHT_B   15u
/* 立绘区：地点在 (1,6)；从 y=7 起 Blank，清「注册/对战」残墨 */
#define LEFT_L    0u
#define LEFT_T    7u
#define LEFT_R    11u
#define LEFT_B    12u

void PokeNav_TrainerEye_DetailEnter_hook_C(void)
{
    uint8_t *blk;
    int16_t sel;
    uint8_t flag;
    uint8_t *reg;
    uint32_t *slots;
    const uint8_t *p;
    uint32_t i;
    menu_blank_t blank = (menu_blank_t)(ADDR_MENU_BLANK_WINDOW_RECT | 1u);
    init_win_t init = (init_win_t)(ADDR_INIT_MENU_WINDOW | 1u);

    blk = *(uint8_t **)(uintptr_t)ADDR_POKENAV_BLK_PTR;

    init(LIST_WIN);
    blank(RIGHT_L, RIGHT_T, RIGHT_R, RIGHT_B);
    PokeNav_TrainerEye_PrintTitle_hook_C(blk + OFF_LIST_LINE);

    init(LEFT_WIN);
    blank(LEFT_L, LEFT_T, LEFT_R, LEFT_B);

    *(uint16_t *)(void *)(blk + OFF_CNT_A) = 0u;
    *(uint16_t *)(void *)(blk + OFF_CNT_B) = 0u;

    sel = *(int16_t *)(void *)(blk + OFF_SEL);
    reg = blk + OFF_REG + ((uint32_t)sel * 8u);
    flag = reg[0];

    slots = (uint32_t *)(void *)(blk + OFF_STR_SLOTS);
    slots[0] = *(uint32_t *)(uintptr_t)(DESC_TABLE + ((uint32_t)flag * 4u));

    p = (const uint8_t *)(uintptr_t)slots[0];
    for (i = 0u; i < 3u; i++) {
        while (*p != 0xFFu)
            p++;
        p++;
        slots[i + 1u] = (uint32_t)(uintptr_t)p;
    }
}
