/* SummaryScreen_PrintTrainerMemo_hook — 能力页训练家备忘。
 *
 * origin（AXVJ @ 0x0809D03C）：
 *   PrintColored(性格名) → 着色缓冲字节数−6 当 tile → 「な」+「せいかく」
 *   → PrintMetLevel(a,b) → Menu_PrintText(地点で であった)
 *
 * 日版无原生 GetStringWidth；F7 按字节当格会把「名」与「性格」撑开。
 * 本钩整函数接管（单缓冲拼接；Lv X 用 GetStringWidth，不再按字节推格）：
 *   性格温顺。Lv5时
 *   在101号道路遇到。
 * （Lv 与性格同行，避免整句塞进第二行超窗撞「取消」）
 */
#include "game.h"

typedef void (*menu_print_t)(const uint8_t *str, uint32_t left, uint32_t top);
typedef uint32_t (*fn1_t)(void *mon);
typedef uint32_t (*fn2_t)(void *mon, uint32_t field);
typedef void (*copy_loc_t)(uint8_t *dst, uint32_t loc);

#define OUT_MAX               96u
#define NAME_MAX              48u
#define CHAR_L                0xC6u
#define CHAR_V                0xEAu
#define CHAR_0                0xA1u
#define CHAR_PERIOD           0x37u
#define MON_DATA_MET_LOCATION 0x23u
#define MON_DATA_MET_LEVEL    0x24u
#define MON_DATA_MET_GAME     0x25u
#define ADDR_GET_NATURE       0x0803C7DCu
#define ADDR_GET_MON_DATA     0x08039F24u
#define ADDR_OT_MATCH_OWNER   0x0809CE54u
#define ADDR_COPY_LOCATION    0x080F6FC0u
#define ADDR_NATURE_NAMES     0x083971E8u
#define ADDR_GSTRING_VAR1     0x020231F0u

#define CHS_XING_HI  0x0Eu
#define CHS_XING_LO  0x5Fu
#define CHS_GE_HI    0x04u
#define CHS_GE_LO    0x5Bu
#define CHS_SHI_HI   0x0Bu
#define CHS_SHI_LO   0xEDu
#define CHS_ZAI_HI   0x0Fu
#define CHS_ZAI_LO   0xE6u
#define CHS_YU_HI    0x0Fu
#define CHS_YU_LO    0xA4u
#define CHS_DAO_HI   0x03u
#define CHS_DAO_LO   0x04u

static void emit_f7(uint8_t *out, unsigned *i, uint8_t hi, uint8_t lo)
{
    if (*i + 4u >= OUT_MAX)
        return;
    out[(*i)++] = 0xF7;
    out[(*i)++] = 0x00;
    out[(*i)++] = hi;
    out[(*i)++] = lo;
}

/* 下标扫描 + 硬上限，避免优化器把「读到 FF」循环证成永真死循环 */
static void emit_pcs(uint8_t *out, unsigned *i, const uint8_t *src)
{
    unsigned n;

    if (!src)
        return;
    for (n = 0u; n < NAME_MAX && *i + 1u < OUT_MAX; n++) {
        uint8_t c = src[n];

        if (c == 0xFFu)
            return;
        if (c == 0xF7u && n + 3u < NAME_MAX && src[n + 1u] == 0x00u &&
            *i + 4u < OUT_MAX) {
            out[(*i)++] = 0xF7;
            out[(*i)++] = 0x00;
            out[(*i)++] = src[n + 2u];
            out[(*i)++] = src[n + 3u];
            n += 3u;
        } else {
            out[(*i)++] = c;
        }
    }
}

static unsigned udiv(unsigned n, unsigned d)
{
    unsigned q = 0u;

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

static void finish(uint8_t *out, unsigned *i)
{
    if (*i < OUT_MAX)
        out[*i] = 0xFF;
    else
        out[OUT_MAX - 1u] = 0xFF;
}

/*
 * 中文 PrintNextChar：FC01=前景 C（备忘 BG0 用 pal15）。
 *   C=1 → (72,72,72) 正文；C=2 → (248,0,0) 高亮（对齐 origin 亮红像素）。
 * 同串中途改 C 会因 12px 相位把邻字右半染花 → 标签/高亮分次 Menu_PrintText。
 */
#define FG_BODY  0x01u
#define FG_HI    0x02u

static void emit_fg(uint8_t *out, unsigned *i, uint8_t color)
{
    if (*i + 3u >= OUT_MAX)
        return;
    out[(*i)++] = 0xFC;
    out[(*i)++] = 0x01;
    out[(*i)++] = color;
}

/* plain 必须以 FF 结尾；max 必须传**该缓冲自己的容量**，不能一律传 OUT_MAX。
 *
 * ★ 2026-11-17 实测定案（特性说明「在 101号道路 遇到。」缺尾巴）：
 *   原来一律 GetStringWidth(plain, OUT_MAX=96)。而 print_met_line_loc()
 *   里的 zai 是 `uint8_t zai[8]`，只装 F7 00 0F E6 FF 共 5 字节。
 *   传 96 会让 GetStringWidth 越过 zai 继续读相邻栈变量，宽度算成 3 格
 *   （应为 2 格）⇒ 后面两段 x 全部右移 ⇒ 末尾「遇到。」被挤出右边界。
 *   GDB 实测该行 Menu_PrintText 三次调用 left=11/14/17，
 *   差值 3/3 而不是正确的 2/2。 */
static uint32_t str_tiles_n(const uint8_t *plain, uint32_t max)
{
    uint32_t px = GetStringWidth(plain, max);

    return (px + CHS_GLYPH_ADVANCE_JP_PX - 1u) / CHS_GLYPH_ADVANCE_JP_PX;
}

static void print_colored(menu_print_t print, const uint8_t *body, uint8_t color,
                          uint32_t left, uint32_t top)
{
    uint8_t buf[OUT_MAX];
    unsigned i = 0u;
    unsigned k;

    emit_fg(buf, &i, color);
    for (k = 0u; body[k] != 0xFFu && i + 1u < OUT_MAX; k++)
        buf[i++] = body[k];
    finish(buf, &i);
    print(buf, left, top);
}

/* 返回「性格{名}。」墨水格数，供同行 Lv 紧跟 */
static uint32_t print_nature_line(menu_print_t print, void *mon, uint32_t left,
                                  uint32_t top)
{
    uint8_t label[16];
    uint8_t namebuf[OUT_MAX];
    uint8_t period[4];
    uint8_t plain[OUT_MAX];
    unsigned li = 0u;
    unsigned ni = 0u;
    unsigned pi = 0u;
    uint32_t nature;
    uint32_t x;
    const uint32_t *table;
    const uint8_t *name;
    fn1_t get_nature = (fn1_t)(ADDR_GET_NATURE | 1u);

    nature = get_nature(mon) & 0xFFu;
    table = (const uint32_t *)ADDR_NATURE_NAMES;
    name = (const uint8_t *)table[nature];

    emit_f7(label, &li, CHS_XING_HI, CHS_XING_LO);
    emit_f7(label, &li, CHS_GE_HI, CHS_GE_LO);
    finish(label, &li);

    emit_pcs(namebuf, &ni, name);
    finish(namebuf, &ni);

    period[0] = CHAR_PERIOD;
    period[1] = 0xFF;

    /* 测宽：性格+名+。 */
    emit_f7(plain, &pi, CHS_XING_HI, CHS_XING_LO);
    emit_f7(plain, &pi, CHS_GE_HI, CHS_GE_LO);
    emit_pcs(plain, &pi, name);
    if (pi < OUT_MAX)
        plain[pi++] = CHAR_PERIOD;
    finish(plain, &pi);

    /* 分次：性格(正文) → 名(高亮) → 。(正文)，避免同串改色染邻列 */
    print_colored(print, label, FG_BODY, left, top);
    x = (left + str_tiles_n(label, sizeof label)) & 0xFFu;
    print_colored(print, namebuf, FG_HI, x, top);
    x = (x + str_tiles_n(namebuf, sizeof namebuf)) & 0xFFu;
    print_colored(print, period, FG_BODY, x, top);

    return str_tiles_n(plain, sizeof plain);
}

static const uint8_t k_trade_met[] = {
    0xF7, 0x00, 0x0D, 0x10, 0xF7, 0x00, 0x04, 0xC5,
    0xF7, 0x00, 0x08, 0x7F, 0xF7, 0x00, 0x07, 0x25,
    0xF7, 0x00, 0x07, 0x0D, 0xF7, 0x00, 0x05, 0x48,
    0xF7, 0x00, 0x0F, 0xA4, 0xF7, 0x00, 0x05, 0xE6,
    0xF7, 0x00, 0x08, 0x9E, 0xFF
};

static const uint8_t k_fateful[] = {
    0xF7, 0x00, 0x09, 0x94, 0xF7, 0x00, 0x10, 0xA1,
    0xF7, 0x00, 0x10, 0xD1, 0xF7, 0x00, 0x03, 0x4D,
    0xF7, 0x00, 0x03, 0x0B, 0xF7, 0x00, 0x0E, 0x0D,
    0xF7, 0x00, 0x0F, 0xA4, 0xFF
};

static void trim_gstring_var1(void)
{
    uint8_t *s = (uint8_t *)ADDR_GSTRING_VAR1;
    unsigned n = 0u;
    unsigned end;
    unsigned start = 0u;

    while (n < NAME_MAX && s[n] != 0xFFu)
        n++;
    while (start < n && (s[start] == 0x00u || s[start] == 0x7Fu))
        start++;
    end = n;
    /* GetMapName 常用 0x00 左右填固定宽；去掉后再拼「在…遇到。」 */
    while (end > start && (s[end - 1u] == 0x00u || s[end - 1u] == 0x7Fu))
        end--;
    if (start > 0u && start < end) {
        unsigned k;
        for (k = 0u; k < end - start; k++)
            s[k] = s[start + k];
        end -= start;
    } else if (start >= end) {
        end = 0u;
    }
    s[end] = 0xFF;
}

/* 行1：紧跟性格句后印 LvN时（GetStringWidth 定 X，避免字节格大空隙） */
static void print_met_level_inline(menu_print_t print, uint32_t left,
                                   uint32_t top, uint32_t level,
                                   uint32_t nature_tiles)
{
    uint8_t out[24];
    unsigned i = 0u;
    uint32_t x;
    unsigned hundreds;
    unsigned tens;
    unsigned ones;

    if (level == 0u)
        level = 5u;
    hundreds = udiv(level, 100u);
    tens = udiv(umod(level, 100u), 10u);
    ones = umod(level, 10u);
    out[i++] = CHAR_L;
    out[i++] = CHAR_V;
    if (hundreds != 0u)
        out[i++] = (uint8_t)(CHAR_0 + hundreds);
    if (hundreds != 0u || tens != 0u)
        out[i++] = (uint8_t)(CHAR_0 + tens);
    out[i++] = (uint8_t)(CHAR_0 + ones);
    out[i++] = 0xF7;
    out[i++] = 0x00;
    out[i++] = CHS_SHI_HI;
    out[i++] = CHS_SHI_LO;
    out[i] = 0xFF;
    x = (left + nature_tiles) & 0xFFu;
    print_colored(print, out, FG_BODY, x, top);
}

static void print_met_line_loc(menu_print_t print, uint32_t left, uint32_t top,
                              uint32_t loc)
{
    uint8_t zai[8];
    uint8_t locbuf[OUT_MAX];
    uint8_t tail[24];
    unsigned zi = 0u;
    unsigned li = 0u;
    unsigned ti = 0u;
    uint32_t x;
    copy_loc_t copy_loc = (copy_loc_t)(ADDR_COPY_LOCATION | 1u);

    copy_loc((uint8_t *)ADDR_GSTRING_VAR1, loc);
    trim_gstring_var1();

    emit_f7(zai, &zi, CHS_ZAI_HI, CHS_ZAI_LO);
    finish(zai, &zi);

    emit_pcs(locbuf, &li, (const uint8_t *)ADDR_GSTRING_VAR1);
    finish(locbuf, &li);

    emit_f7(tail, &ti, CHS_YU_HI, CHS_YU_LO);
    emit_f7(tail, &ti, CHS_DAO_HI, CHS_DAO_LO);
    if (ti < 24u)
        tail[ti++] = CHAR_PERIOD;
    finish(tail, &ti);

    print_colored(print, zai, FG_BODY, left, top);
    x = (left + str_tiles_n(zai, sizeof zai)) & 0xFFu;
    print_colored(print, locbuf, FG_HI, x, top);
    x = (x + str_tiles_n(locbuf, sizeof locbuf)) & 0xFFu;
    print_colored(print, tail, FG_BODY, x, top);
}

void SummaryScreen_PrintTrainerMemo_hook_C(void *mon, uint32_t left,
                                           uint32_t top)
{
    menu_print_t print = (menu_print_t)(ADDR_MENU_PRINT_TEXT | 1u);
    fn1_t ot_match = (fn1_t)(ADDR_OT_MATCH_OWNER | 1u);
    fn2_t get_mon = (fn2_t)(ADDR_GET_MON_DATA | 1u);
    uint32_t line2_top;
    uint32_t match;
    uint32_t loc;
    uint32_t level;
    uint32_t met_game;
    uint32_t nature_tiles;

    left &= 0xFFu;
    top &= 0xFFu;
    line2_top = (top + 2u) & 0xFFu;

    nature_tiles = print_nature_line(print, mon, left, top);

    match = ot_match(mon) & 0xFFu;
    if (match == 1u) {
        loc = get_mon(mon, MON_DATA_MET_LOCATION) & 0xFFu;
        level = get_mon(mon, MON_DATA_MET_LEVEL) & 0xFFu;
        if (loc > 0x57u) {
            print(k_fateful, left, line2_top);
            return;
        }
        print_met_level_inline(print, left, top, level, nature_tiles);
        print_met_line_loc(print, left, line2_top, loc);
        return;
    }

    met_game = get_mon(mon, MON_DATA_MET_GAME) & 0xFFu;
    loc = get_mon(mon, MON_DATA_MET_LOCATION) & 0xFFu;
    level = get_mon(mon, MON_DATA_MET_LEVEL) & 0xFFu;

    if (met_game == 0u || met_game > 3u) {
        print(k_fateful, left, line2_top);
        return;
    }
    if (loc == 0xFFu) {
        print(k_trade_met, left, line2_top);
        return;
    }
    if (loc == 0xFEu || loc > 0x57u) {
        print(k_fateful, left, line2_top);
        return;
    }
    print_met_level_inline(print, left, top, level, nature_tiles);
    print_met_line_loc(print, left, line2_top, loc);
}
