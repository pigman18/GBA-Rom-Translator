/* ============================================================================
 * tile_alloc.c — v7 动态 tile 分配器（运行时读 tilemap → 避让带 → 绕开）
 *
 * 背景（用户定夺 2026-09-04）：v6 的静态选址（scene_cfg.c 行带基址表）只是
 * 「测试能规避撞」的过渡，真正要的是动态算法——读 win 窗口得到避让带，再
 * 算法绕开让中文合理拿到 tile。本文件就是那条动态路径。
 *
 * 三步法（用户定义）：
 *   ① 屏蔽输出（统一屏蔽）——已在 PrintNextChar_Hook + ADDR_V6_BYPASS 开关完成；
 *   ② 读避让带 —— 本文件：扫 tilemap 活引用，收集官方已占 tile 号；
 *   ③ 算法绕开 —— 本文件：确定性遍历空闲带跳过占用领 tile。
 *
 * 三条铁律（缺一不可）：
 *   ① 确定性：固定起点遍历跳过占用，同输入 → 同输出（防 v4 随机取址/重绘漂移坑）。
 *   ② 权威性：避让带来自 tilemap 活引用，不靠猜（漏一个就砸官方字）。
 *   ③ 隔离性：charBase 物理分块天然隔离 OBJ 精灵区，上界用 REG_DISPCNT 截断。
 *
 * 关键输入（AXVJ 实证）：
 *   tilemap 指针 = tpl[TPL_TILEMAP]=+0x10；charBase = tpl[TPL_CHARBASE]=+0x01
 *   （charBlock 号 0~3，v1 draw_glyph.c:355 实证）；tilemap 表项 tile 号 = entry&0x3FF
 *   （低 10 bit，高 4 bit 是 palette）；OBJ 起始 charBlock = (REG_DISPCNT>>4)&3。
 *
 * 三个 v4 坑的解法：
 *   - 重绘幂等 → 确定性遍历（非随机）；
 *   - OBJ 精灵区 → 上界 hi = (obj_cb - charBase)*512 截断（charBase 相对号不落 OBJ 块）；
 *   - 自画污染 → v7_alloc_begin 在打印会话开始时快照位图，本轮只看快照。
 * ==========================================================================*/
#include "tile_alloc.h"

/* 占用位图：128 字节 = 1024 bit = tile 相对号 0~1023。
 * 落 ADDR_V7_ALLOC_STATE（0x0203FEC0，V6_TILE_HW 之后、FF80 之前的空闲带）。
 * bit 布局：位图[0] bit0 = tile 0，位图[0] bit7 = tile 7，位图[1] bit0 = tile 8 … */
#define V7_BITMAP_WORDS  128u   /* 1024 bit / 8 */

static volatile uint8_t *v7_bitmap(void)
{
    return (volatile uint8_t *)ADDR_V7_ALLOC_STATE;
}

/* 位图游标（确定性遍历起点），放位图之后 */
#define V7_CURSOR_ADDR   (ADDR_V7_ALLOC_STATE + V7_BITMAP_WORDS)

static void v7_bit_set(volatile uint8_t *bm, uint16_t tile)
{
    bm[tile >> 3] |= (uint8_t)(1u << (tile & 7u));
}

static int v7_bit_get(const volatile uint8_t *bm, uint16_t tile)
{
    return (bm[tile >> 3] >> (tile & 7u)) & 1u;
}

static void v7_bit_clear_all(volatile uint8_t *bm)
{
    unsigned i;
    for (i = 0; i < V7_BITMAP_WORDS; i++)
        bm[i] = 0u;
}

/* 读 GBA 寄存器（volatile 映射） */
static uint16_t v7_reg_dispcnt(void)
{
    return *(volatile uint16_t *)0x04000000u;
}

/* OBJ 起始 charBlock：DISPCNT bits[5:4]（DISPCNT_OBJ_CHAR_BASE_MASK=0x0030）。 */
static uint8_t v7_obj_charblock(void)
{
    return (uint8_t)((v7_reg_dispcnt() >> 4) & 3u);
}

/* 分配上界（charBase 相对号）：避免落入 OBJ 精灵 charBlock。
 * 若 OBJ charBlock > 当前 charBase，则相对号 t 落 OBJ 当且仅当 charBase+t/512 == obj_cb
 * ⇒ 上界 hi = (obj_cb - charBase)*512；否则 hi = 1024（4 个 charBlock 全覆盖）。 */
static uint16_t v7_alloc_hi(uint8_t char_base)
{
    uint8_t obj_cb = v7_obj_charblock();
    if (obj_cb > char_base)
        return (uint16_t)((unsigned)(obj_cb - char_base) * 512u);
    return 1024u;
}

/* ============================================================================
 * v7_alloc_begin：打印会话开始时快照占用位图。
 * 扫当前窗口 tilemap（BG screenBase 32×32 = 1024 表项）的活引用，每个非零
 * 表项的低 10 bit = 官方已占 tile 相对号，标位。
 * 之后本轮所有中文查这张快照——不看自己刚写入的表项 ⇒ 防自画污染。
 * ==========================================================================*/
void v7_alloc_begin(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint16_t *tilemap;
    volatile uint8_t *bm = v7_bitmap();
    unsigned i;

    if (!tpl)
        return;
    tilemap = (uint16_t *)(uintptr_t)win_u32(tpl, TPL_TILEMAP);
    if (!tilemap)
        return;

    v7_bit_clear_all(bm);

    /* 扫整个 tilemap（32×32 = 1024 表项）。tilemap 表项存 charBase 相对号，
     * 高 4 bit 是 palette（官方 UpdateTilemap 写 palette=win[0x0F]<<12），
     * 故 & 0x3FF 取低 10 bit 的 tile 号。 */
    for (i = 0; i < 1024u; i++) {
        uint16_t t = tilemap[i] & 0x3FFu;
        if (t != 0u)
            v7_bit_set(bm, t);
    }
}

/* ============================================================================
 * v7_alloc_tile：领连续 2 tile（t 与 t+1）。
 * 确定性：从上次游标起遍历 [lo, hi)，跳过占用位图，取首个连续 2 空闲。
 * 无空闲 → 回卷到 lo 重扫一次，再没有 → 返回 0（调用方放弃，宁缺不砸 UI）。
 * ==========================================================================*/
uint16_t v7_alloc_tile(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint8_t char_base;
    volatile uint8_t *bm = v7_bitmap();
    uint16_t hi, lo, t;
    uint16_t start;

    if (!tpl)
        return 0u;
    char_base = tpl[TPL_CHARBASE];
    hi = v7_alloc_hi(char_base);
    lo = 0x100u;                  /* 空闲带起点：避开官方 atlas [0,0x100) */
    if (lo >= hi)
        return 0u;

    start = *(volatile uint16_t *)V7_CURSOR_ADDR;
    if (start < lo || start >= hi)
        start = lo;

    /* 第一遍：从上次游标起 */
    for (t = start; t + 1u < hi; t += 2u) {
        if (!v7_bit_get(bm, t) && !v7_bit_get(bm, (uint16_t)(t + 1u))) {
            *(volatile uint16_t *)V7_CURSOR_ADDR = (uint16_t)(t + 2u);
            return t;
        }
    }
    /* 第二遍：回卷到 lo 重扫 */
    for (t = lo; t + 1u < hi; t += 2u) {
        if (!v7_bit_get(bm, t) && !v7_bit_get(bm, (uint16_t)(t + 1u))) {
            *(volatile uint16_t *)V7_CURSOR_ADDR = (uint16_t)(t + 2u);
            return t;
        }
    }
    return 0u;                    /* 彻底无空闲：放弃，宁缺不砸 UI */
}
