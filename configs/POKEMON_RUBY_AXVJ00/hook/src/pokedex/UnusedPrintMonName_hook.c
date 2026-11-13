/* UnusedPrintMonName_hook — 图鉴分类名行。
 *
 * origin（GDB 实测）：先打占位「？？？？？ポケモン」，再打右对齐 5 格分类名
 * （`00 00 00 たね`），后缀留在占位串上。
 *
 * 中文占位已折成「？？？？？宝可梦」。对齐美版 ENGLISH：分类名 +「宝可梦」，
 * 再按占位总宽（76px）右对齐。
 *
 * 前导留白：空墨槽 247 = F7 00 01 F7（lead=1→adjust 0；禁止 hi=0，
 * GRID_LEAD_ADJUST(0) 会下溢）。走 grid_draw_chs→grid_load 铺背景。
 * 不用 PCS 0x00（只推进不重绘；改全局 0x00 擦除会削列表共享列）。
 */
#include "game.h"

typedef void (*menu_print_t)(const uint8_t *str, uint32_t left, uint32_t top);

#define OUT_MAX         96u
#define PLACEHOLDER_PX  76

static unsigned append_stream(uint8_t *out, unsigned i,
                              const uint8_t *stream)
{
    while (stream && i + 4u < OUT_MAX) {
        uint8_t b = *stream;

        if (b == 0xFF || b == 0x00)
            break;
        if (b == 0xF7u && stream[1] == 0x00u) {
            if (i + 4u >= OUT_MAX)
                break;
            out[i] = stream[0];
            out[i + 1u] = stream[1];
            out[i + 2u] = stream[2];
            out[i + 3u] = stream[3];
            i += 4u;
            stream += 4;
        } else {
            out[i++] = b;
            stream++;
        }
    }
    return i;
}

static unsigned count_cjk(const uint8_t *stream)
{
    const uint8_t *q = stream;
    unsigned n = 0;

    while (q && *q != 0xFF && *q != 0x00) {
        if (*q == 0xF7u && q[1] == 0x00u) {
            n++;
            q += 4;
        } else {
            q++;
        }
    }
    return n;
}

static const uint8_t k_suffix[] = {
    0xF7, 0x00, 0x01, 0x63,   /* 宝 */
    0xF7, 0x00, 0x07, 0xD7,   /* 可 */
    0xF7, 0x00, 0x09, 0x66,   /* 梦 */
    0xFF
};

void UnusedPrintMonName_hook_C(const uint8_t *name,
                               uint32_t left, uint32_t top)
{
    uint8_t out[OUT_MAX];
    unsigned i = 0;
    unsigned ncat;
    int body_px, pad_px, nsp, k;

    ncat = count_cjk(name);
    body_px = (int)CHS_GLYPH_ADVANCE_PX * (int)(ncat + 3u);
    pad_px = PLACEHOLDER_PX - body_px;
    if (pad_px < 0)
        pad_px = 0;
    /* 12px 步进：ceil(pad/12)，裸机忌软除法。 */
    nsp = 0;
    for (k = 0; k < pad_px; k += 12)
        nsp++;
    for (k = 0; k < nsp && i + 4u < OUT_MAX; k++) {
        /* 空墨槽 247：F7 00 01 F7 */
        out[i++] = 0xF7;
        out[i++] = 0x00;
        out[i++] = 0x01;
        out[i++] = 0xF7;
    }

    i = append_stream(out, i, name);
    i = append_stream(out, i, k_suffix);
    out[i] = 0xFF;

    ((menu_print_t)(ADDR_MENU_PRINT_TEXT | 1u))(out, left, top);
}
