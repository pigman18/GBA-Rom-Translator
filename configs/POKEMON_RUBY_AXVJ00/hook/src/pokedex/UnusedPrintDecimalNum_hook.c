/* UnusedPrintDecimalNum_hook — 图鉴身高/体重行。
 *
 * origin（与 UnusedPrintMonName 同构）：
 *   1) Menu_PrintText(？？？．？ｍ / ？？？．？ｋｇ)
 *   2) 本函数用前导 PCS 0x00 右对齐叠「d.d」
 * 0x00 只推进不重绘 → 短数字露「？」（同分类名残留问号）。
 *
 * 不改 PrintNextChar：在本钩子里先用 F7 空墨槽铺掉占位宽，再打
 * 「右对齐数字 + 单位」。单位按 top 区分（7=身高ｍ，9=体重ｋｇ）。
 */
#include "game.h"

typedef void (*menu_print_t)(const uint8_t *str, uint32_t left, uint32_t top);

#define OUT_MAX 48u
#define CHAR_0  0xA1u
#define CHAR_PERIOD 0xB8u
#define CHAR_M  0xE1u
#define CHAR_K  0xDFu
#define CHAR_G  0xDBu

/* 身高占位 6 格、体重 7 格；JP 每格 8px。 */
#define HEIGHT_TILES 6u
#define WEIGHT_TILES 7u

static unsigned udiv(unsigned n, unsigned d)
{
    unsigned q = 0;

    if (d == 0u)
        return 0u;
    while (n >= d) {
        n -= d;
        q++;
    }
    return q;
}

static unsigned umod(unsigned n, unsigned d)
{
    if (d == 0u)
        return 0u;
    while (n >= d)
        n -= d;
    return n;
}

static void emit_empty_pad(uint8_t *out, unsigned *i)
{
    if (*i + 4u >= OUT_MAX)
        return;
    /* 空墨槽 247：F7 00 01 F7（与 UnusedPrintMonName 相同） */
    out[(*i)++] = 0xF7;
    out[(*i)++] = 0x00;
    out[(*i)++] = 0x01;
    out[(*i)++] = 0xF7;
}

void UnusedPrintDecimalNum_hook_C(uint32_t value, uint32_t left, uint32_t top)
{
    uint8_t clear[OUT_MAX];
    uint8_t out[OUT_MAX];
    unsigned ci = 0;
    unsigned i = 0;
    unsigned field_tiles;
    unsigned clear_pads;
    unsigned k;
    unsigned d0, d1, d2, d3;
    unsigned body_tiles;
    unsigned pad_tiles;
    int is_weight;
    menu_print_t print = (menu_print_t)(ADDR_MENU_PRINT_TEXT | 1u);

    is_weight = (top == 9u);
    field_tiles = is_weight ? WEIGHT_TILES : HEIGHT_TILES;

    /* 先铺满占位宽（12px/空槽，向上取整盖住 8px×N）。 */
    clear_pads = 0u;
    for (k = 0u; k < field_tiles * CHS_GLYPH_ADVANCE_JP_PX; k += CHS_GLYPH_ADVANCE_PX)
        clear_pads++;
    for (k = 0u; k < clear_pads; k++)
        emit_empty_pad(clear, &ci);
    clear[ci] = 0xFF;
    print(clear, left, top);

    /* 与 origin 相同的十进制拆分：千/百/十.个 */
    d0 = udiv(value, 1000u);
    d1 = udiv(umod(value, 1000u), 100u);
    d2 = udiv(umod(value, 100u), 10u);
    d3 = umod(value, 10u);

    /* 有效数字格：省略前导零后的「d.d」(+单位)。 */
    body_tiles = 3u; /* 至少 十 . 个 */
    if (d0 != 0u)
        body_tiles = 5u;
    else if (d1 != 0u)
        body_tiles = 4u;
    body_tiles += is_weight ? 2u : 1u; /* ｋｇ / ｍ */

    pad_tiles = 0u;
    if (body_tiles < field_tiles)
        pad_tiles = field_tiles - body_tiles;

    for (k = 0u; k < pad_tiles && i + 1u < OUT_MAX; k++)
        out[i++] = 0x00; /* 已清底，0x00 只推进即可 */

    if (d0 != 0u && i + 1u < OUT_MAX)
        out[i++] = (uint8_t)(CHAR_0 + d0);
    if ((d0 != 0u || d1 != 0u) && i + 1u < OUT_MAX)
        out[i++] = (uint8_t)(CHAR_0 + d1);
    if (i + 1u < OUT_MAX)
        out[i++] = (uint8_t)(CHAR_0 + d2);
    if (i + 1u < OUT_MAX)
        out[i++] = CHAR_PERIOD;
    if (i + 1u < OUT_MAX)
        out[i++] = (uint8_t)(CHAR_0 + d3);

    if (is_weight) {
        if (i + 1u < OUT_MAX)
            out[i++] = CHAR_K;
        if (i + 1u < OUT_MAX)
            out[i++] = CHAR_G;
    } else {
        if (i + 1u < OUT_MAX)
            out[i++] = CHAR_M;
    }
    out[i] = 0xFF;
    print(out, left, top);
}
