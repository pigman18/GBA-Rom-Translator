/* =====================================================================================
 * text_vfw12.c — VFW12 渲染（可变宽 12px 档）
 *
 * 策略：12px 档汉字的步进不再固定 12，而是按**字模墨迹宽度**派生
 * （最右非零列 +2 含 1px 间隙，钳制 [8,12]）——口/日 窄、酬/疆 满，
 * 右缘节奏自然，行容量 +5~10%。绘制本体零新增：宽度算完后整托
 * render_inplace12（原生寻址原地写，含全部 scene 门控与 pitch 状态）。
 *
 * 适用范围：仅 12px 档（w>=12）收窄；JP/SYM/空白（8px 档）原样。
 * 已知边界：GetStringWidth（地名弹窗居中）仍按固定 12 累加——居中
 * 偏差数 px，实验期接受。
 * ===================================================================================== */
#include "game.h"
#include "text_render.h"

/* 4bpp tile 内 (x,y) 处 nibble 非零 = 有墨/阴影（x<8） */
static unsigned ink_at(const uint8_t *tile, unsigned x, unsigned y)
{
    uint8_t b = tile[y * 4u + (x >> 1)];
    return (x & 1u) ? (b & 0x0Fu) : (b >> 4);
}

/* 12px 档墨迹宽度派生（自右向左扫列 0-11 × 行 0-11） */
static unsigned vfw_width12(const uint8_t *tl, const uint8_t *bl,
                            const uint8_t *tr, const uint8_t *br)
{
    int c;
    unsigned x, y;

    for (c = 11; c >= 0; c--) {
        for (y = 0; y < 12; y++) {
            const uint8_t *left = (y < 8) ? tl : bl;
            const uint8_t *right = (y < 8) ? tr : br;
            unsigned yy = (y < 8) ? y : y - 8u;
            if (c < 8) {
                if (ink_at(left, (unsigned)c, yy))
                    goto found;
            } else {
                if (ink_at(right, (unsigned)(c - 8), yy))
                    goto found;
            }
        }
    }
    return 8u;                       /* 全空：下限 */
found:
    x = (unsigned)c + 2u;            /* 墨迹末列 + 1px 间隙 */
    if (x < 8u)
        x = 8u;
    if (x > 12u)
        x = 12u;
    return x;
}

void render_vfw12(TextPrinter *win, const struct ChsGlyphTiles *t, unsigned w)
{
    if (w >= 12u) {
        unsigned vfw = vfw_width12(t->tl, t->bl, t->tr, t->br);
        w = vfw;
    }
    render_inplace12(win, t, w);
}
