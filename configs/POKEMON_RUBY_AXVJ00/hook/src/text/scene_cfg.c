/* ============================================================================
 * scene_cfg.c — 避让带「静态登记」通道（v9 需求 3）
 *
 * 静态 = **固有算法 / 硬件布局常量**，不是「观察到的界面」。
 * （2026-09-10 用户裁定：旧 kVAvoidScenes 那类「已有 UI 场景表」不利用——
 *   它只记录已存在的界面，操作选项后才出现的 UI 没登记，所以早废了。）
 *
 * 本文件提供两样东西：
 *   ① s_scene_bands[]  —— 静态 tilemap 带（VRAM 屏幕块的硬件占用，全局下标）
 *   ② chs_scene_reserved_len() —— 每窗自留区的固有公式（图集 cap + 两个框）
 * 两者都经统一的 chs_band_add() 灌入运行带表，与 hook 动态登记**同一条管线**。
 * ==========================================================================*/
#include "tile_alloc.h"

/* ---------------------------------------------------------------------------
 * ① 静态 tilemap 带（全局下标）
 *
 * 来源 = GBA 硬件布局，不是场景观察：VRAM 0x06000000 起，每 0x800 字节一个
 * screenblock；一个 screenblock = 32×32 表项 = 2048B = **64 个 tile 的位置**。
 * 本作实际用到的 4 段（各窗 2×2 或 1×1 表）：
 *     sb0      @ 0x00000  全局 [   0,   64)
 *     sb14/15  @ 0x07000  全局 [ 896, 1024)
 *     sb23/24  @ 0x0B800  全局 [1472, 1600)
 *     sb30/31  @ 0x0F000  全局 [1920, 2048)
 * 这些位置放的是 tilemap 表项数据，**不是**字符图形 → 永不作为 glyph 目标。
 * （分配器 v8_alloc_begin 另有「按 DISPCNT/BGxCNT 动态保留当帧 screenblock」的
 *   一层；本表是不依赖当帧寄存器状态的兜底声明。）
 * ------------------------------------------------------------------------- */
static const ChsBandDecl s_scene_bands[] = {
    {    0u,  64u },
    {  896u, 128u },
    { 1472u, 128u },
    { 1920u, 128u },
};

#define S_SCENE_BAND_N  (sizeof(s_scene_bands) / sizeof(s_scene_bands[0]))

void chs_scene_bands_apply(void)
{
    unsigned i;

    for (i = 0; i < S_SCENE_BAND_N; i++)
        (void)chs_band_add(s_scene_bands[i].start, s_scene_bands[i].len);
}

/* ---------------------------------------------------------------------------
 * ② 固有算法：tm1 窗自留区长度
 *
 * 反汇编实证（源 ROM roms/origin/POKEMON_RUBY_AXVJ00.gba）：
 *   0x08002950 InitWindowTileData
 *     0x08002950  push {lr}
 *     0x0800299C  ldr r0,[r3,#0]      ; r0 = win[0] = 模板
 *     0x0800299E  ldrb r0,[r0,#8]     ; tpl[8] = fontNum
 *     0x080029A0  cmp r0,#5 / bhi → 返 0
 *     0x080029B0  跳表（fontNum 索引）:
 *                 [0]=512 [1]=256 [2]=256 [3]=512 [4]=256 [5]=256
 *   返 512 的分支：0x080029CC  movs r0,#128 / lsls r0,#2
 *   返 256 的分支：0x080029D2  movs r0,#128 / lsls r0,#1
 *   0x0800296C  ldrb r0,[r1,#9]      ; tpl[9] = textMode（本文件不据它分支）
 *
 *   自留区（相对号，起址恒 startOffset=1）：
 *     图集 [1, 1+cap) + 标准框 9（[cap,cap+9)）+ 对话框框 14（[cap+9,cap+23)）
 *     ⇒ [1, cap+23) ⇒ 长度 = cap + 22
 *   实测帧基址恒等于图集返回值（17/17），所以框不需要单独 hook。
 * ------------------------------------------------------------------------- */
uint16_t chs_scene_reserved_len(uint8_t font_num)
{
    uint16_t cap;

    if (font_num > 5u)                 /* 跳表越界 ⇒ 引擎返 0（不铺图集） */
        return 0u;
    cap = (font_num == 0u || font_num == 3u) ? 512u : 256u;
    return (uint16_t)(cap + 22u);      /* = (1 + cap + 9 + 14) - 1 */
}
