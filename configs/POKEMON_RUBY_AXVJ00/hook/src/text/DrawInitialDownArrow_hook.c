/* DrawInitialDownArrow_hook.c — FA/FB 等 A 箭头前置同步（B04 双▼修复）。
 *
 * 地址订钉：main.asm `.org DrawInitialDownArrow` → entry.s WaitArrow_Prepare
 * （先调本函数同步 CHS 游标，再进原版主体 0x08003DAD）。
 *
 * FA/FB 不经 PrintNextChar（PCC 控制跳表 → DrawInitialDownArrow）。原版箭头
 * blit VRAM 于 TILE_BASE+TILE_OFFSET、UpdateTilemap 于 CURSOR_X+TILE_X；
 * 12px 线性步进滞后一列 → ▼ 覆盖墨水 VRAM 且盖在视觉行尾 → 双▼。
 */
#include "game.h"

void WaitArrow_Prepare_C(TextPrinter *win)
{
    volatile struct ChineseTileState *st;
    uint16_t cols;
    uint16_t off;
    uint8_t want;
    uint8_t cur_tx;

    if (!win)
        return;
    st = chs_bind_pitch_slot(win, 0);
    if (!st->chs_px)
        return;

    cols = (uint16_t)((st->chs_px + 7u) >> 3);
    want = (uint8_t)(st->base_tx + cols);
    cur_tx = win_u8(win, WIN_CURSOR_TILE_X);

    /*
     * \n{\p}: FE already moved to the next line (TILE_X==0). Keep that
     * cursor — do NOT stamp at previous-line end (双▼: static at 梦 + animated
     * corner). Only refresh TILE_OFFSET so arrow ink misses glyph VRAM.
     *
     * Same-line \p (shop): TILE_X still at ink end → sync to want.
     */
    if (cur_tx == 0u && want > 0u) {
        off = win_u16(win, WIN_TILE_OFFSET);
        if (st->chs_px & 7u)
            win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
        Chinese_PitchReset(win);
        return;
    }

    /* want is TILE_X space — never subtract CURSOR_X (shop mid-line ♥). */
    win_set_u8(win, WIN_CURSOR_TILE_X, want);

    off = win_u16(win, WIN_TILE_OFFSET);
    if (st->chs_px & 7u)
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));

    Chinese_PitchReset(win);
}
