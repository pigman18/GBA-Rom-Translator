/* MapNamePopup_hook.c — 地名弹窗居中钩（P04，挂 DrawMapNamePopup StringLength 位点 0x0809F67E）。
 *
 * 背景：AXVJ 原生按「字节格」在 10 格字段居中（全部 16px/格），译后地名是内联
 * F9 流，字节≠宽度，>10B 时 10-len 下溢野写（历史 crash 根因，见
 * docs/PATCHES_INVENTORY.md §3.1）。
 *
 * 方案 v6（2026-08-22 GDB 单步实证 + 实测校准收敛）：
 *   1) ROM 补丁严禁占用 r0 —— native `mov r0,sp` 的缓冲区指针必须原样进 C
 *      （v1~v3 补丁用 ldr r0 转跳，C 收到的是跳板自身地址 0x08800145，
 *      把机器码当名字量宽 → 恒 152px，三代全中同一枪；修复：补丁只用 r3 转跳，
 *      跳板 push{r0,lr} 保住 r0）。
 *   2) MenuPrint 的 x/left 参数是**格数**（8px/格），Text_InitWindow 内
 *      win->left = 8*left（pokeruby text.c 实证；v4 像素直传出界 wrap 确认）。
 *      返回居中起点**格数**（四舍五入，残差 ≤4px），跳板注入 r1 = 1 + 返回值。
 *   3) 文字区总宽 = 10 列 × 8px = 80px（v5/v6 实测反推）。
 *
 * 宽度计算 GetStringWidth_PCS 来源 src/text.c（导出工具），本文件只留 MAP 场景
 * 常量与居中换算。入口 r0=sp 缓冲区（只读遍历），返回居中追加**格数**
 * （0 = 维持原生位置）。跳板落点 0x0809F6CE（跳过 movs r1,#1）。
 * 安全阀：宽 0 或 ≥ 文字区 80px → 返回 0 原样放行。
 *
 * 已知边界（记账）：FA~FE 控制码按 0px 跳过（地名表中不出现）；sectionId==0x42
 * 走原生旁路不经过本钩（维持原生行为）；半宽字面量按真实 8px 计入，无偏差。
 */
#include "game.h"

#define MAPNAME_FIELD_PX    80u /* 文字区 10 列 × 8px（textMode=3 半格步进，实测反推） */
#define MAPNAME_BUF_BYTES  20   /* 原生 sub sp,#0x14 */
#define MAPNAME_CELL_PX      8u /* left 参数粒度 = 1 tilemap 列 */

uint32_t MapNamePopup_CalcLeftPx(const uint8_t *buf)
{
    uint32_t width_px = GetStringWidth_PCS(buf, MAPNAME_BUF_BYTES);

    if (width_px == 0 || width_px >= MAPNAME_FIELD_PX)
        return 0;                       /* 空/满宽：原样放行 */
    /* 居中起点换算成「格」（8px）：MenuPrint 的 left 是格数，Text_InitWindow
     * 内 win->left = 8*left。文字区总宽 = 80px（v5/v6 实测反推，见头注）。
     * 四舍五入取格，残差 ≤4px。跳板注入 r1 = 1 + 返回值（基准 = 第 1 格）。 */
    return (((MAPNAME_FIELD_PX - width_px) / 2u) + (MAPNAME_CELL_PX / 2u)) / MAPNAME_CELL_PX;
}
