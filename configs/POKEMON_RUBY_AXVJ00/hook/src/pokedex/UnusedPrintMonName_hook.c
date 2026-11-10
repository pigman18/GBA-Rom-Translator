/* UnusedPrintMonName_hook — 图鉴分类名行。
 *
 * ⚠️ 2026-11-04 重写（移除 F980 依赖）
 *
 * 原实现：把「分类名」和「宝可梦」的 PhraseTable 展开流取出来，
 * 拼成一条连续 F9 00 单字流，再调 MenuPrintText 打印。
 * 它依赖 PhraseTable 查表（F980 通道），火红没有等价物，必须去掉。
 *
 * 现在：F980 已移除，图鉴分类名和宝可梦名的文本改为**直接搬运 + 改指针**，
 * 内存里的字符串本身就是 F9 00 单字流。所以这个 hook 不再需要
 * 展开任何短语表 —— 把分类名原样打印，宝可梦名由原版流程负责。
 *
 * 保留下来的唯一职责：把「分类名 + 宝可梦」拼成一条并补齐尾部，
 * 因为原版占位串是固定 76px，分类名变长后会露出残字。
 * 拼装逻辑不变，只是不再查 PhraseTable。
 */
#include "game.h"

typedef void (*menu_print_t)(const uint8_t *str, uint32_t left, uint32_t top);

#define OUT_MAX         96u

/* 把一条 PCS 流展开追加到 out：
 *   F7 00 hi lo     → 原样拷贝 4 字节（**当前编码**）
 *   F9 00 xx xx     → 原样拷贝 4 字节（旧编码，兼容残留）
 *   其它字节         → 原样拷贝（裸 0xF7 不是合法组首，单字节跳过）
 *   遇 0xFF 结束；遇 0x00（日文空格）结束。
 * 返回新的写入位置。
 *
 * ★ 2026-11-10：编码定为 F7 00 hi lo（4B）后，这里必须按 4 字节分组。
 *   只认 F9 的版本会把 0xF7 当成普通单字节搬走，整条流被撕裂 ——
 *   图鉴「分类名 + 宝可梦」行乱码、名字空、上下翻页读到越界地址，
 *   全都源于这一处没跟上。 */
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
        } else if (b == 0xF9u) {
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

/* 统计一条流里的汉字数（F7 00 hi lo 或 F9 00 hi lo 各算 1 字）。 */
static unsigned count_cjk(const uint8_t *stream)
{
    const uint8_t *q = stream;
    unsigned n = 0;

    while (q && *q != 0xFF && *q != 0x00) {
        if (*q == 0xF7u && q[1] == 0x00u) {
            n++;
            q += 4;
        } else if (*q == 0xF9u) {
            n++;
            q += 4;
        } else {
            q++;
        }
    }
    return n;
}

void UnusedPrintMonName_hook_C(const uint8_t *name,
                               uint32_t left, uint32_t top)
{
    const uint8_t *ref = (const uint8_t *)ADDR_DEX_TEXT_UNKNOWN_POKE;
    uint8_t out[OUT_MAX];
    unsigned i = 0;
    unsigned ncat;

    /* 分类名直接就是 F9 00 单字流（F980 已移除，不再有短语引用）。
     * 若上游仍传入 F9 80 形态，跳过这 4 字节引用——但正常路径不会出现。 */
    if (name[0] == 0xF9u && name[1] != 0x00u)
        name += 4;

    /* 占位串 ref 里，问号占位（0xAC）之后就是宝可梦名字节流。 */
    {
        unsigned j = 0;
        while (ref[j] == 0xACu)
            j++;
        if (ref[j] == 0xF9u && ref[j + 1u] != 0x00u)
            j += 4;
        ref += j;
    }

    ncat = count_cjk(name);

    i = append_stream(out, i, name);
    i = append_stream(out, i, ref);

    /* 占位串整体 76px：5问号(40px)+宝可梦(33px@11px步进)。
     * 本串 宝可梦已紧跟分类名，若分类名不足 4 字则盖不满尾部，会露出
     * 占位串宝可梦的残字（梦）。按缺口追加 8px 空格补齐覆盖。
     * 步进随字库走 CHS_GLYPH_ADVANCE_PX，勿写死。 */
    {
        int pad = 40 - (int)CHS_GLYPH_ADVANCE_PX * (int)ncat;
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
