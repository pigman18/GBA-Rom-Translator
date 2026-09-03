/* ============================================================================
 * InitTextPrinter_hook.c — InitTextPrinter 块边界 hook（2026-09-04 v8 简化）
 *
 * 职责：hook 被劫持的 ROM 函数 InitTextPrinter（@0x08002C68），在文本块边界
 * 做两件事：
 *   ① 快照 tilemap 活引用位图（避让带基线）；
 *   ② 复位分配游标与相位状态。
 * 不渲染任何字形、不碰 VRAM。
 *
 * v8 起：删除了 v6 那套「全局 8 槽 ChsPhase + 行指纹 key + curX 变大续接」的
 * 复杂相位复位逻辑。相位改成 tile_alloc.c 里的「按行隔离单变量」（v8_phase_get
 * 内部按 tpl^curY 行标识自动归零），块边界只需统一调用 v8_alloc_begin 重建
 * 避让带位图 + 复位游标/相位即可。
 *
 * 「类型」→「8」跨块续接：不再依赖本文件的续接判断。因为相位按「行」隔离
 * （tpl^curY），两个块若同属一行（tpl 与 curY 均相同），行标识匹配 → 相位自然
 * 续接；换行/换窗口 → 行标识失配 → 自动归零。比旧启发式更简洁也更可靠。
 * ============================================================================ */
#include "text.h"
#include "scene_cfg.h"
#include "tile_alloc.h"

/* InitTextPrinter 入口钩（entry.s 跳板已重放前 8B、保 r0-r3、重排参数）。
 * 参数：win / tile_base(r2) / cur_x(r3) / cur_y(第5参数，栈)。只读不改 win。
 * v8：统一重建避让带位图 + 复位游标/相位（三者同生命周期，窗口切换自然从头来）。 */
void InitTextPrinter_hook_C(TextPrinter *win, uint16_t tile_base,
                            uint8_t cur_x, uint8_t cur_y)
{
    (void)tile_base;
    (void)cur_x;
    (void)cur_y;
    /* 块边界快照 tilemap 活引用位图 + 复位游标/相位：
     * 本轮动态分配（v8_alloc_tile）查这张快照，不看自己刚写入的表项 ⇒
     * 防自画污染 + 避让官方字。相位与游标一起复位，窗口切换不残留。 */
    v8_alloc_begin(win);
}
