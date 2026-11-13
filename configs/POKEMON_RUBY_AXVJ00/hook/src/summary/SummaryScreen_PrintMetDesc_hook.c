/* SummaryScreen_PrintMetDesc_hook — 能力页训练家备忘「遭遇描述」行。
 *
 * origin（AXVJ PokemonSummaryScreen_PrintTrainerMemo @ 0x0809D03C）：
 *   CopyLocationName → gStringVar1
 *   Menu_PrintText(「\CC050E\02\CC050Fで であった」等, left, top+2)
 * 公共落点 @ 0x0809D1DE。
 *
 * JP 模板 = 地点占位 +「で であった／かえった／あったようだ」。
 * 中文自然语序 =「在」+ 地点 +「遇见了／得到了／遇见的样子」。
 * 若仍走 FD02 模板前置「在」，会与 JP 按字节算的左缘打架；
 * 本钩子接管该入口：清底后一次拼好整句再 Menu_PrintText。
 * 无 FD02 的交换/宿命等串原样转发。
 */
#include "game.h"

typedef void (*menu_print_t)(const uint8_t *str, uint32_t left, uint32_t top);

#define OUT_MAX     96u

/* F7 码位（charmap） */
#define CHS_ZAI_HI  0x0Fu
#define CHS_ZAI_LO  0xE6u
#define CHS_YU_HI   0x0Fu
#define CHS_YU_LO   0xA4u
#define CHS_JIAN_HI 0x05u
#define CHS_JIAN_LO 0xE6u
#define CHS_LE_HI   0x08u
#define CHS_LE_LO   0x9Eu
#define CHS_DE2_HI  0x03u  /* 得 */
#define CHS_DE2_LO  0x0Au
#define CHS_DAO_HI  0x03u
#define CHS_DAO_LO  0x04u
#define CHS_DE_HI   0x03u  /* 的 */
#define CHS_DE_LO   0x0Bu
#define CHS_YANG_HI 0x0Eu
#define CHS_YANG_LO 0xE2u
#define CHS_ZI_HI   0x11u
#define CHS_ZI_LO   0x0Bu

/* 清底少用空墨槽：每颗 F7 仍占 VRAM 字模，扫太宽会挤掉顶栏「取消」tile */
#define FIELD_TILES 4u

enum {
    SUFFIX_MET = 0,
    SUFFIX_GOT,
    SUFFIX_SEEMS
};

static void emit_empty_pad(uint8_t *out, unsigned *i)
{
    if (*i + 4u >= OUT_MAX)
        return;
    out[(*i)++] = 0xF7;
    out[(*i)++] = 0x00;
    out[(*i)++] = 0x01;
    out[(*i)++] = 0xF7;
}

static void emit_f7(uint8_t *out, unsigned *i, uint8_t hi, uint8_t lo)
{
    if (*i + 4u >= OUT_MAX)
        return;
    out[(*i)++] = 0xF7;
    out[(*i)++] = 0x00;
    out[(*i)++] = hi;
    out[(*i)++] = lo;
}

static int tpl_has_fd02(const uint8_t *tpl)
{
    unsigned n = 0;

    if (!tpl)
        return 0;
    while (tpl[n] != 0xFFu && n < 64u) {
        if (tpl[n] == 0xFDu && n + 1u < 64u && tpl[n + 1u] == 0x02u)
            return 1;
        n++;
    }
    return 0;
}

static int tpl_has_f7(const uint8_t *tpl, uint8_t hi, uint8_t lo)
{
    unsigned n = 0;

    while (tpl[n] != 0xFFu && n + 3u < 64u) {
        if (tpl[n] == 0xF7u && tpl[n + 1u] == 0x00u &&
            tpl[n + 2u] == hi && tpl[n + 3u] == lo)
            return 1;
        n++;
    }
    return 0;
}

/* 样/よう → 遇见的样子；得/かえ → 得到了；否则遇见了 */
static int pick_suffix(const uint8_t *tpl)
{
    unsigned n = 0;

    if (tpl_has_f7(tpl, CHS_YANG_HI, CHS_YANG_LO))
        return SUFFIX_SEEMS;
    if (tpl_has_f7(tpl, CHS_DE2_HI, CHS_DE2_LO))
        return SUFFIX_GOT;

    while (tpl[n] != 0xFFu && n + 1u < 64u) {
        /* JP「よう」粗匹配：0x26 0x03 出现在 あったようだ */
        if (tpl[n] == 0x26u && tpl[n + 1u] == 0x03u)
            return SUFFIX_SEEMS;
        /* JP「かえ」：0x06 0x04 在 かえった */
        if (tpl[n] == 0x06u && tpl[n + 1u] == 0x04u)
            return SUFFIX_GOT;
        n++;
    }
    return SUFFIX_MET;
}

static void emit_suffix(uint8_t *out, unsigned *i, int kind)
{
    if (kind == SUFFIX_GOT) {
        emit_f7(out, i, CHS_DE2_HI, CHS_DE2_LO);
        emit_f7(out, i, CHS_DAO_HI, CHS_DAO_LO);
        emit_f7(out, i, CHS_LE_HI, CHS_LE_LO);
        return;
    }
    if (kind == SUFFIX_SEEMS) {
        emit_f7(out, i, CHS_YU_HI, CHS_YU_LO);
        emit_f7(out, i, CHS_JIAN_HI, CHS_JIAN_LO);
        emit_f7(out, i, CHS_DE_HI, CHS_DE_LO);
        emit_f7(out, i, CHS_YANG_HI, CHS_YANG_LO);
        emit_f7(out, i, CHS_ZI_HI, CHS_ZI_LO);
        return;
    }
    emit_f7(out, i, CHS_YU_HI, CHS_YU_LO);
    emit_f7(out, i, CHS_JIAN_HI, CHS_JIAN_LO);
    emit_f7(out, i, CHS_LE_HI, CHS_LE_LO);
}

void SummaryScreen_PrintMetDesc_hook_C(const uint8_t *tpl, uint32_t left,
                                       uint32_t top)
{
    uint8_t clear[OUT_MAX];
    uint8_t out[OUT_MAX];
    unsigned ci = 0;
    unsigned i = 0;
    unsigned clear_pads;
    unsigned k;
    menu_print_t print = (menu_print_t)(ADDR_MENU_PRINT_TEXT | 1u);
    int kind;

    left &= 0xFFu;
    top &= 0xFFu;

    if (!tpl_has_fd02(tpl)) {
        print(tpl, left, top);
        return;
    }

    clear_pads = 0u;
    for (k = 0u; k < FIELD_TILES * CHS_GLYPH_ADVANCE_JP_PX; k += CHS_GLYPH_ADVANCE_PX)
        clear_pads++;
    for (k = 0u; k < clear_pads; k++)
        emit_empty_pad(clear, &ci);
    clear[ci] = 0xFF;
    print(clear, left, top);

    kind = pick_suffix(tpl);

    /* 在 + 着色 + FD02（交给 Menu_PrintText 展开 StringVar1）+ 后缀 */
    emit_f7(out, &i, CHS_ZAI_HI, CHS_ZAI_LO);
    if (i + 3u < OUT_MAX) {
        out[i++] = 0xFC;
        out[i++] = 0x05;
        out[i++] = 0x0E;
    }
    if (i + 2u < OUT_MAX) {
        out[i++] = 0xFD;
        out[i++] = 0x02;
    }
    if (i + 3u < OUT_MAX) {
        out[i++] = 0xFC;
        out[i++] = 0x05;
        out[i++] = 0x0F;
    }
    emit_suffix(out, &i, kind);
    if (i < OUT_MAX)
        out[i] = 0xFF;
    else
        out[OUT_MAX - 1u] = 0xFF;
    /* 「在」比 JP 地点首字多占一截；左移 1 格挤进窗缘内边距，避免被裁 */
    if (left > 0u)
        left -= 1u;
    print(out, left, top);
}
