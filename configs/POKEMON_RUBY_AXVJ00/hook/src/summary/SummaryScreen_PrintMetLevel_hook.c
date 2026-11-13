/* SummaryScreen_PrintMetLevel_hook — 能力页训练家备忘「LvNのとき」。
 *
 * origin（AXVJ @ 0x0809CFA0）：
 *   1) 按性格名字节长算 tile X（假定 8px/格）
 *   2) PrintColoredInt(LvN)
 *   3) Menu_PrintText(のとき) 再右偏 2/3/4 格
 *
 * 中文「时」走 F7（12px），且旧译「那时」更宽；按 JP 格偏移会飞出窗外
 * 或被数字墨迹盖住。不改 PrintNextChar：在本钩子清占位宽后一次打印
 * 「Lv」+ 十进制 +「时」。
 */
#include "game.h"

typedef void (*menu_print_t)(const uint8_t *str, uint32_t left, uint32_t top);
typedef uint32_t (*get_mon_data_t)(void *mon, uint32_t field);

#define OUT_MAX        48u
#define CHAR_L         0xC6u
#define CHAR_V         0xEAu
#define CHAR_0         0xA1u
#define MON_DATA_MET_LEVEL 0x24u
/* 「时」= charmap 0x0BED → F7 00 0B ED */
#define CHS_SHI_HI     0x0Bu
#define CHS_SHI_LO     0xEDu
/* 清扫宽度：够盖住「Lv255时」在 8px 格算法下的右偏 */
#define FIELD_TILES    10u

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
    out[(*i)++] = 0xF7;
    out[(*i)++] = 0x00;
    out[(*i)++] = 0x01;
    out[(*i)++] = 0xF7;
}

void SummaryScreen_PrintMetLevel_hook_C(void *mon, uint32_t a, uint32_t b,
                                        uint32_t left, uint32_t top)
{
    uint8_t clear[OUT_MAX];
    uint8_t out[OUT_MAX];
    unsigned ci = 0;
    unsigned i = 0;
    unsigned clear_pads;
    unsigned k;
    unsigned level;
    unsigned x0;
    unsigned tens;
    unsigned ones;
    unsigned hundreds;
    menu_print_t print = (menu_print_t)(ADDR_MENU_PRINT_TEXT | 1u);
    get_mon_data_t get_mon = (get_mon_data_t)(0x08039F24u | 1u);

    a &= 0xFFu;
    b &= 0xFFu;
    left &= 0xFFu;
    top &= 0xFFu;

    /* origin：left+(a+b-1)，a/b 按 JP 1 字节≈1 格。
     * 中文 F7 每字 4 字节，调用方仍按字节累加会把 X 撑出右缘。
     * 改为备忘行右缘对齐（约 17 格），再按「LvN时」体宽回退。 */
    {
        unsigned body_tiles = 2u + 1u + 2u; /* Lv + 至少1位 + 时(12px≈2格) */
        unsigned level_tmp;
        unsigned right = (left + 17u) & 0xFFu;

        (void)a;
        (void)b;
        level_tmp = get_mon(mon, MON_DATA_MET_LEVEL) & 0xFFu;
        if (level_tmp == 0u)
            level_tmp = 5u;
        if (level_tmp >= 100u)
            body_tiles = 2u + 3u + 2u;
        else if (level_tmp >= 10u)
            body_tiles = 2u + 2u + 2u;
        if (right >= body_tiles)
            x0 = (right - body_tiles) & 0xFFu;
        else
            x0 = left;
    }

    clear_pads = 0u;
    for (k = 0u; k < FIELD_TILES * CHS_GLYPH_ADVANCE_JP_PX; k += CHS_GLYPH_ADVANCE_PX)
        clear_pads++;
    for (k = 0u; k < clear_pads; k++)
        emit_empty_pad(clear, &ci);
    clear[ci] = 0xFF;
    print(clear, x0, top);

    level = get_mon(mon, MON_DATA_MET_LEVEL) & 0xFFu;
    if (level == 0u)
        level = 5u;

    out[i++] = CHAR_L;
    out[i++] = CHAR_V;

    hundreds = udiv(level, 100u);
    tens = udiv(umod(level, 100u), 10u);
    ones = umod(level, 10u);
    if (hundreds != 0u)
        out[i++] = (uint8_t)(CHAR_0 + hundreds);
    if (hundreds != 0u || tens != 0u)
        out[i++] = (uint8_t)(CHAR_0 + tens);
    out[i++] = (uint8_t)(CHAR_0 + ones);

    /* 时 */
    out[i++] = 0xF7;
    out[i++] = 0x00;
    out[i++] = CHS_SHI_HI;
    out[i++] = CHS_SHI_LO;
    out[i] = 0xFF;

    print(out, x0, top);
}
