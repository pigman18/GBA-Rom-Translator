/* PokeNav_TrainerEye_ListRedraw_hook — 列表每行重画前清残墨。
 *
 * 算法（对照 origin + tip P30）：
 *   ListRedraw(index, y) 每次只印一行（调用方 0..7 循环满页）。
 *   日文 0x00 空格 = tilemap→空白字模，短盖长；网格引擎对 0x00「只推进
 *   不改表」→ 换行/退详情后旧汉字/详情红仍挂在未改写的格上。
 *
 *   禁止改全局 0x00 语义。本钩场景内：
 *   - 平常：只 Blank 本行 tilemap (13,y)–(28,y+1)（不 scrub VRAM band，
 *     避免误伤；短清长靠 Blank 改表）
 *   - 详情退回（NEED_BLANK）：Blank 整右栏 + 一次 scrub 列表 arena
 *     + 强制重印左栏（地点/标签/数字）。左栏与详情窗共 charblock 0，
 *     进详情后字模被毁、tilemap 半残，只清右栏不够。
 *
 * 左栏 origin：Init(0x25)；地点 0x080EB9C0；标签 0x080EBA40(0)；
 * 统计 0x080EC2E0(blk[0x8772])。
 */
#include "game.h"
#include "text_grid.h"

typedef void (*menu_blank_t)(uint32_t left, uint32_t top, uint32_t right,
                             uint32_t bottom);
typedef void (*init_win_t)(uint32_t window_id);
typedef void (*void_fn_t)(void);
typedef void (*u32_fn_t)(uint32_t);

#define ADDR_INIT_MENU_WINDOW 0x0806F158u
/* Menu_BlankWindowRect 字面量；sym gMenuWindowPtr@0x0202E9C8 在 AXVJ 不可用 */
#define ADDR_MENU_WINDOW_PTR  0x0202E6E8u

#define ADDR_TE_PRINT_LOCATION     0x080EB9C0u
#define ADDR_TE_PRINT_LEFT_LABELS  0x080EBA40u
#define ADDR_TE_PRINT_LEFT_STATS   0x080EC2E0u
#define OFF_TE_SEL_BYTE            0x8772u

#define LIST_WIN 0x2Fu
#define LEFT_WIN 0x25u
#define RIGHT_L  12u
#define RIGHT_T  2u
#define RIGHT_R  28u
#define RIGHT_B  15u
/* 与 DetailEnter 同：地点占 y=6–7，统计从 y=9 */
#define LEFT_L   0u
#define LEFT_T   9u
#define LEFT_R   11u
#define LEFT_B   16u

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

/* GBA VRAM 禁止 byte 写。scrub [start, end) tile。 */
static void scrub_tiles(uint32_t base, unsigned start, unsigned end)
{
    unsigned n, i;

    if (base == 0u || start >= end)
        return;
    if (end > GRID_TILE_LIMIT)
        end = GRID_TILE_LIMIT;
    for (n = start; n < end; n++) {
        volatile uint32_t *p =
            (volatile uint32_t *)(uintptr_t)(base + 32u * n);
        for (i = 0u; i < 8u; i++)
            p[i] = 0u;
    }
}

static void scrub_list_arena(void)
{
    TextPrinter *win = *(TextPrinter **)(uintptr_t)ADDR_MENU_WINDOW_PTR;
    uint16_t tb;
    uint32_t base = list_tile_base(win, &tb);

    scrub_tiles(base, (unsigned)tb + 2u, GRID_TILE_LIMIT);
}

/* 详情退回：左栏字模可能已被详情写坏，强制走 origin 三件套重印。 */
static void restore_left_panel(void)
{
    uint8_t *blk;
    menu_blank_t blank = (menu_blank_t)(ADDR_MENU_BLANK_WINDOW_RECT | 1u);
    init_win_t init = (init_win_t)(ADDR_INIT_MENU_WINDOW | 1u);
    void_fn_t print_loc = (void_fn_t)(ADDR_TE_PRINT_LOCATION | 1u);
    u32_fn_t print_labels = (u32_fn_t)(ADDR_TE_PRINT_LEFT_LABELS | 1u);
    u32_fn_t print_stats = (u32_fn_t)(ADDR_TE_PRINT_LEFT_STATS | 1u);

    blk = *(uint8_t **)(uintptr_t)ADDR_POKENAV_BLK_PTR;
    if (!blk)
        return;

    init(LEFT_WIN);
    blank(LEFT_L, LEFT_T, LEFT_R, LEFT_B);
    print_loc();
    print_labels(0u);
    print_stats((uint32_t)blk[OFF_TE_SEL_BYTE]);
}

void PokeNav_TrainerEye_ListBlank_C(uint32_t index, uint32_t y)
{
    uint8_t *flag = (uint8_t *)(uintptr_t)ADDR_TE_LIST_NEED_BLANK;
    menu_blank_t blank = (menu_blank_t)(ADDR_MENU_BLANK_WINDOW_RECT | 1u);
    init_win_t init = (init_win_t)(ADDR_INIT_MENU_WINDOW | 1u);

    (void)index;
    y &= 0xffffu;

    init(LIST_WIN);

    if (*flag != 0u) {
        *flag = 0u;
        blank(RIGHT_L, RIGHT_T, RIGHT_R, RIGHT_B);
        scrub_list_arena();
        restore_left_panel();
        init(LIST_WIN);
    }

    /* 每行只 Blank tilemap：短清长；滚动不再 scrub band */
    if (y <= RIGHT_B) {
        uint32_t y1 = y + 1u;
        if (y1 > RIGHT_B)
            y1 = RIGHT_B;
        if (y >= RIGHT_T)
            blank(RIGHT_L, y, RIGHT_R, y1);
    }
}
