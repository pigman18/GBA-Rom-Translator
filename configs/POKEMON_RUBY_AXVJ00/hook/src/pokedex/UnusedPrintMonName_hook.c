/* UnusedPrintMonName_hook — 图鉴分类名行。
 *
 * 不再打印 F9 80 短语引用（连续短语之间会多出空隙），而是把
 * 「分类名」和「宝可梦」的 PhraseTable 展开流都取出来，拼成一条
 * 连续的 F9 00 单字侧载流打印。每个汉字 12px 紧密推进，无空格，
 * 也不走短语重定向的状态机。
 */
#include "game.h"

#define ADDR_MENU_PRINT_TEXT        0x0806F16Cu
#define ADDR_DEX_TEXT_UNKNOWN_POKE  0x083E9688u  /* ac*5 f9 80 03 fa ff */

typedef void (*menu_print_t)(const uint8_t *str, uint32_t left, uint32_t top);

#define NAME_MAX_BYTES  16u
#define OUT_MAX         64u

static const uint8_t *phrase_stream_lookup(uint16_t code)
{
    const uint32_t *offsets = (const uint32_t *)ADDR_PHRASE_OFFSETS;
    const uint8_t *table = (const uint8_t *)ADDR_PHRASE_TABLE;
    uint32_t off = offsets[code];

    if (off >= 0x01000000u)
        return 0;
    return table + off;
}

/* 把一条 PCS 流展开追加到 out：
 *   F9 00 xx xx     → 原样拷贝 4 字节
 *   其它字节         → 原样拷贝
 *   遇 0xFF 结束；遇 0x00（日文空格）结束。
 * 返回是否追加了内容。 */
static unsigned append_stream(uint8_t *out, unsigned i,
                              const uint8_t *stream)
{
    while (stream && i + 4u < OUT_MAX) {
        uint8_t b = *stream;

        if (b == 0xFF || b == 0x00)
            break;
        if (b == 0xF9u) {
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

void UnusedPrintMonName_hook_C(const uint8_t *name,
                               uint32_t left, uint32_t top)
{
    const uint8_t *cat_stream = 0;
    const uint8_t *poke_stream = 0;
    const uint8_t *ref = (const uint8_t *)ADDR_DEX_TEXT_UNKNOWN_POKE;
    uint8_t out[OUT_MAX];
    unsigned i = 0;
    unsigned ncat = 0;

    /* 分类名：优先当作 F9 80 短语引用展开；否则当作原文字节流。 */
    if (name[0] == 0xF9u && name[1] == 0x80u) {
        uint16_t code = (uint16_t)((name[2] << 8) | name[3]);
        cat_stream = phrase_stream_lookup(code);
    } else {
        cat_stream = name;
    }

    /* 宝可梦：ref 问号之后的 F9 80 03 fa。 */
    {
        unsigned j = 0;
        while (ref[j] == 0xACu)
            j++;
        if (ref[j] == 0xF9u && ref[j + 1u] == 0x80u) {
            uint16_t code = (uint16_t)((ref[j + 2u] << 8) | ref[j + 3u]);
            poke_stream = phrase_stream_lookup(code);
        } else {
            poke_stream = ref + j;
        }
    }

    /* 统计分类名汉字数（每 F9 00 = 1 字）用于补尾空格。 */
    {
        const uint8_t *q = cat_stream;
        ncat = 0;
        while (q && *q != 0xFF && *q != 0x00) {
            if (*q == 0xF9u) {
                ncat++;
                q += 4;
            } else {
                q++;
            }
        }
    }

    i = append_stream(out, i, cat_stream);
    i = append_stream(out, i, poke_stream);

    /* 占位串整体 76px：5问号(40px)+宝可梦(36px)。
     * 本串 宝可梦已紧跟分类名，若分类名不足 4 字则盖不满尾部，会露出
     * 占位串宝可梦的残字（梦）。按缺口追加 8px 空格补齐覆盖。*/
    {
        int pad = 40 - 12 * ncat;
        unsigned nsp, k2;
        if (pad < 0)
            pad = 0;
        nsp = (unsigned)((pad + 7) / 8);
        for (k2 = 0; k2 < nsp && i + 1u < OUT_MAX; k2++)
            out[i++] = 0x00;
    }
    out[i] = 0xFF;

    ((menu_print_t)(ADDR_MENU_PRINT_TEXT | 1u))(out, left, top);
}
