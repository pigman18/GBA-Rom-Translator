/* PokeNav_TrainerEye_DetailEnter_hook — 训练家之眼进详情。
 *
 * origin（AXVJ @ 0x080EBF9C）：清两计数 → 按选中项取说明表指针 →
 * 顺 FF 拆后继串指针写入 blk+0xD110 起。
 *
 * case4：FormatListLine → PrintTitle → (list/left) → 本函数。
 * 右栏：Blank 窗 0x2F + scrub 列表 arena（只 Blank 改表不够：中文列表
 * 字模仍占 VRAM，详情行距空隙会透出名单残墨）→ 重打红条。
 *
 * 左栏：地点 (1,6) 与统计同窗 0x25。Blank (0,7)–(11,16) 保地点。
 */
#include "game.h"
#include "text_grid.h"

typedef void (*menu_blank_t)(uint32_t left, uint32_t top, uint32_t right,
                             uint32_t bottom);
typedef void (*init_win_t)(uint32_t window_id);
typedef void (*void_fn_t)(void);

void PokeNav_TrainerEye_PrintTitle_hook_C(uint8_t *str);

#define ADDR_INIT_MENU_WINDOW 0x0806F158u
#define ADDR_MENU_WINDOW_PTR  0x0202E6E8u
#define ADDR_TE_PRINT_LOCATION 0x080EB9C0u

#define OFF_CNT_A     0x306u
#define OFF_CNT_B     0xD15Cu
#define OFF_SEL       0x8772u
#define OFF_REG       0xCEECu
#define OFF_STR_SLOTS 0xD110u
#define OFF_LIST_LINE 0x878Cu
#define DESC_TABLE    0x083B8E10u

#define LIST_WIN  0x2Fu
#define LEFT_WIN  0x25u
/* 含 gutter x=12：列表名常顶到 13，残墨会落在 12 */
#define RIGHT_L   12u
#define RIGHT_T   2u
#define RIGHT_R   28u
#define RIGHT_B   15u
/* 地点 Menu_PrintText(…,1,6) 占 tile 行 6–7（16px）；从 9 起清统计 */
#define LEFT_L    0u
#define LEFT_T    9u
#define LEFT_R    11u
#define LEFT_B    16u

static uint32_t list_tile_base(TextPrinter *win, uint16_t *tb_out)
{
    const uint8_t *tpl;
    uint32_t base;

    if (!win)
        return 0u;
    tpl = win_template(win);
    if (!tpl)
        return 0u;
    if (win_u8(win, WIN_TEXTMODE) == 2u
        || win_u32(tpl, TPL_TILEMAP) == 0u)
        base = win_u32(win, WIN_TILE_DATA);
    else
        base = win_u32(tpl, TPL_TILE_DATA);
    if (tb_out)
        *tb_out = win_u16(win, WIN_TILE_BASE);
    return base;
}

static void scrub_list_arena(void)
{
    TextPrinter *win = *(TextPrinter **)(uintptr_t)ADDR_MENU_WINDOW_PTR;
    uint16_t tb;
    uint32_t base = list_tile_base(win, &tb);
    unsigned n, i, start, end;

    if (base == 0u)
        return;
    start = (unsigned)tb + 2u;
    end = GRID_TILE_LIMIT;
    for (n = start; n < end; n++) {
        volatile uint32_t *p =
            (volatile uint32_t *)(uintptr_t)(base + 32u * n);
        for (i = 0u; i < 8u; i++)
            p[i] = 0u;
    }
}

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
    scrub_list_arena();
    PokeNav_TrainerEye_PrintTitle_hook_C(blk + OFF_LIST_LINE);

    init(LEFT_WIN);
    blank(LEFT_L, LEFT_T, LEFT_R, LEFT_B);
    /* 进详情 origin 不重打地点，靠旧字模存活；中文共块后字模易毁 → 补打 */
    ((void_fn_t)(ADDR_TE_PRINT_LOCATION | 1u))();

    /* 退回列表时 ListRedraw 见此标志再 Blank 右栏 + 左栏重印 */
    *(uint8_t *)(uintptr_t)ADDR_TE_LIST_NEED_BLANK = 1u;

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
