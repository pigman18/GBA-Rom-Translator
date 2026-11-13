/* SummaryScreen_NameLayoutTiles_hook — 能力页物种名旁 ♂/♀ 的 X。
 *
 * origin（AXVJ @ 0x0809D230..）：
 *   PrintColored(name, 4, 14)
 *   gender_left = StringLength(name) + 4
 *   PrintGender(mon, gender_left, 14)
 *
 * 日版无 GetGlyphWidth/GetStringWidth，把 StringLength 字节数当 8px 格。
 * F7 中文每字 4 字节 / 12px：StringLength(火焰鸡)=12 → left=16，
 * ♂ 被推到右栏备忘（origin x≈75 / 错位 x≈131）。
 *
 * 订址桩从 bl StringLength 起接管：用 GetStringWidth 算格数后调 PrintGender。
 * D230..D254（物种名表寻址，patch-table 会改）与 D274 基址字面量不动。
 */
#include "game.h"

typedef void (*print_gender_t)(void *mon, uint32_t left, uint32_t top);

#define NAME_LEFT  4u
#define NAME_TOP   0x0Eu

void SummaryScreen_NameLayoutTiles_hook_C(const uint8_t *name, void *mon)
{
    uint32_t px = GetStringWidth(name, 64u);
    uint32_t tiles =
        (px + CHS_GLYPH_ADVANCE_JP_PX - 1u) / CHS_GLYPH_ADVANCE_JP_PX;
    uint32_t gender_left = (NAME_LEFT + tiles) & 0xFFu;
    print_gender_t print_gender = (print_gender_t)(0x0809D278u | 1u);

    print_gender(mon, gender_left, NAME_TOP);
}
