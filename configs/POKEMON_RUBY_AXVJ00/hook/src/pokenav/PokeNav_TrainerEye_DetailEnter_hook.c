/* PokeNav_TrainerEye_DetailEnter_hook — 训练家之眼进详情。
 *
 * origin（AXVJ @ 0x080EBF9C）：清两计数 → 按选中项取说明表指针 →
 * 顺 FF 拆后继串指针写入 blk+0xD110 起。
 *
 * case4：FormatListLine → PrintTitle → (list/left) → 本函数。
 * 右栏：Blank 窗 0x2F + scrub 列表 arena（只 Blank 改表不够：中文列表
 * 字模仍占 VRAM，详情行距空隙会透出名单残墨）→ 重打红条。
 *
 * 左栏：地点 (0,5) 与统计同窗 0x25。origin 进详情完全不碰左栏（反汇编
 * 0x080EBF9C 无 init/blank/scrub/PrintLocation 调用），地点靠列表页旧字模存活。
 * 汉化必须每次按 sel 重打地点：0x080EC2E0 读 blk[0xCEEA+sel*8] 的地点名索引
 * → GetMapNameString → Menu_PrintText(blk+0xD138,0,5)，走同一套 grid 渲染。
 * 重打前清地点带 tile（短名不会覆盖长名尾部），Blank 只清统计区 y9..16。
 */
#include "game.h"
#include "text_grid.h"

typedef void (*menu_blank_t)(uint32_t left, uint32_t top, uint32_t right,
                             uint32_t bottom);
typedef void (*init_win_t)(uint32_t window_id);
typedef void (*u32_fn_t)(uint32_t);

void PokeNav_TrainerEye_PrintTitle_hook_C(uint8_t *str);

#define ADDR_INIT_MENU_WINDOW 0x0806F158u
#define ADDR_MENU_WINDOW_PTR  0x0202E6E8u
/* 地点重打（origin 的 PrintLeftStats 真身，反汇编 0x080EC2E0）：
 *   r1 = ldrh [blk + 0xCEEA + sel*8]   地点名索引（训练家记录 +2）
 *   bl  0x080F6F1C                     GetMapNameString(dest, idx, 0) 查译好的地点名表
 *   拼到 blk+0xD138 → init(0x25) → Menu_PrintText(blk+0xD138, 0, 5)
 * 汉化必须每次进详情/切训练家重打；origin 只靠列表页旧字模存活。 */
#define ADDR_TE_PRINT_LOC_NAME 0x080EC2E0u
/* 注意：0x080EB9C0 PrintLocation 在 PokeNav 全程 flag=blk[0x87CE]=2 → 直接返回空转
 * （RAM 实测 f113/f131/f173 flag 恒 2），绝不能拿它重打地点。 */
/* 左栏窗 0x25 的 tilemap screenblock（GDB 实测 模板@0x081BB7B4 tilemap=0x0600F800）。
 * 地点(0x81..0x8E)/标签/统计 tile 都经它引用；与列表共用 charblock0 的 VRAM tile 池。 */
#define ADDR_LEFT_TILEMAP     0x0600F800u

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
    /* 左栏窗 0x25 tilemap（32×32=1024 项，bit0-9=tile 号）。
     * live 位图：512 bit 覆盖 GRID_TILE_LIMIT(0x1F0) 全部 tile。 */
    volatile uint16_t *tm = (volatile uint16_t *)(uintptr_t)ADDR_LEFT_TILEMAP;
    uint32_t live[16];
    uint16_t tb;
    uint32_t base = list_tile_base(win, &tb);
    unsigned n, i, start, end;

    if (base == 0u)
        return;

    /* BUG-A：origin 进详情完全不碰左栏，地点/标签/统计靠列表页旧字模存活
     * （反汇编 0x080EBF9C 全文无 init/blank/scrub/PrintLocation 调用）。
     * 汉化共块后 scrub 全池会把左栏地点 0x81..0x8E 一起清成空白。
     * 修法：扫左栏 tilemap 收集当前 live-ref tile，scrub 时跳过。
     * 右栏已 blank 改表 → 旧列表残墨不在 live 集，照旧清。 */
    for (i = 0u; i < 16u; i++)
        live[i] = 0u;
    for (n = 0u; n < 1024u; n++) {
        unsigned t = (unsigned)(tm[n] & 0x03FFu);
        if (t < GRID_TILE_LIMIT)
            live[t >> 5u] |= 1u << (t & 31u);
    }

    start = (unsigned)tb + 2u;
    end = GRID_TILE_LIMIT;
    for (n = start; n < end; n++) {
        if ((live[n >> 5u] & (1u << (n & 31u))) != 0u)
            continue;  /* 左栏仍在显示，保住旧字模（地点） */
        volatile uint32_t *p =
            (volatile uint32_t *)(uintptr_t)(base + 32u * n);
        for (i = 0u; i < 8u; i++)
            p[i] = 0u;
    }
}

/* 地点名长短随训练家变化（118号道路 / 未白镇 / 宝可梦联盟…）。
 * grid 渲染对 0x00 只推进不改表，短名不会覆盖长名尾部 → 先清地点带
 * (y5-6, x1..11) 引用的 tile 内容，再由重打填新字。x=0 是窗边框，不动。 */
static void clear_location_tiles(uint32_t base)
{
    volatile uint16_t *tm = (volatile uint16_t *)(uintptr_t)ADDR_LEFT_TILEMAP;
    unsigned y, x, i;

    if (base == 0u || base < 0x06000000u || base >= 0x06018000u)
        return;
    for (y = 5u; y <= 6u; y++) {
        for (x = 1u; x <= 11u; x++) {
            unsigned t = (unsigned)(tm[y * 32u + x] & 0x03FFu);
            volatile uint32_t *p;

            if (t == 0u || t >= GRID_TILE_LIMIT)
                continue;
            p = (volatile uint32_t *)(uintptr_t)(base + 32u * t);
            for (i = 0u; i < 8u; i++)
                p[i] = 0u;
        }
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
    u32_fn_t print_loc_name = (u32_fn_t)(ADDR_TE_PRINT_LOC_NAME | 1u);

    blk = *(uint8_t **)(uintptr_t)ADDR_POKENAV_BLK_PTR;
    /* 先取 sel：地点重打按它索引 blk+0xCEEA+sel*8 的地点名索引 */
    sel = *(int16_t *)(void *)(blk + OFF_SEL);

    init(LIST_WIN);
    blank(RIGHT_L, RIGHT_T, RIGHT_R, RIGHT_B);
    scrub_list_arena();
    PokeNav_TrainerEye_PrintTitle_hook_C(blk + OFF_LIST_LINE);

    init(LEFT_WIN);
    blank(LEFT_L, LEFT_T, LEFT_R, LEFT_B);
    /* 左栏地点接入自定义渲染重打。origin 进详情不重打（PrintLocation flag=2
     * 空转、靠列表页旧字模存活），汉化共块后旧字模会被毁/切训练家时不会更新，
     * 故每次进详情都按当前 sel 重新生成中文地点串并打印（走 Menu_PrintText
     * → PrintNextChar grid，即与右栏同一套自定义渲染）。 */
    {
        TextPrinter *lw = *(TextPrinter **)(uintptr_t)ADDR_MENU_WINDOW_PTR;
        uint16_t ltb;
        uint32_t lbase = list_tile_base(lw, &ltb);

        clear_location_tiles(lbase);
    }
    print_loc_name((uint32_t)(uint8_t)sel);

    /* 退回列表时 ListRedraw 见此标志再 Blank 右栏 + 左栏重印 */
    *(uint8_t *)(uintptr_t)ADDR_TE_LIST_NEED_BLANK = 1u;

    *(uint16_t *)(void *)(blk + OFF_CNT_A) = 0u;
    *(uint16_t *)(void *)(blk + OFF_CNT_B) = 0u;

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
