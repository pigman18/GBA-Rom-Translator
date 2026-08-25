/* =====================================================================================
 * chinese_text.c — 中文内容解析（upstream 移植）
 *
 * upstream: rh-hideout-chinese/pokeemerald-expansion src/chinese_text.c
 * 职责与 upstream 一致：字模索引 → 解压进字形缓冲 → 设置 width/height。
 * 渲染（写窗口 tile / 推进游标）不在此层——由 src/text.c 引擎渲染行完成，
 * 与 upstream「DecompressGlyph 填缓冲 + PrintGlyph 原生写」的分层一致。
 *
 * ⚠️ 与 upstream 的存储差异：upstream 写全局 gCurGlyph（decomp 链接器分配）；
 * 本工程 game.bin 为 freestanding 平坦镜像、无 RAM 段，全局落 ROM 写无效
 * （首版五图全花根因），故缓冲由调用方栈上分配、经参数传入（text.h 存储说明）。
 * ===================================================================================== */
#include "text.h"
#include "chinese_text.h"

/* 伪 glyph 编码（原 game.h GLYPH_SRC_CHS 家族收编至此，内部专用）：
 * bit15 = 右半（TR/BR，字库内 +64B），bits0-14 = 字模号。 */
#define CHS_GLYPH_HALF_BIT   0x8000u
#define CHS_GLYPH_IDX_MASK   0x7FFFu
#define CHS_FONT_GLYPH_MAX   7168

static void copy_tile32(void *dst, const void *src)
{
    const uint32_t *s = (const uint32_t *)src;
    uint32_t *d = (uint32_t *)dst;
    d[0] = s[0]; d[1] = s[1]; d[2] = s[2]; d[3] = s[3];
    d[4] = s[4]; d[5] = s[5]; d[6] = s[6]; d[7] = s[7];
}

/* 仅在通过状态机 F9 帧定界后使用（upstream 注：仅在通过 IsChineseChar 检测后使用）。 */
void DecompressGlyph_Chinese(struct TextGlyph *glyph, uint16_t ChineseChar, uint8_t fontId)
{
    const uint8_t *base;
    const uint8_t *g;

    if (ChineseChar >= CHS_FONT_GLYPH_MAX)
        ChineseChar = 0;

    /* 根据字体类别选择字库（upstream 同款分支；fontId 语义对齐原生 fontNum）：
     * font4（队伍名等小字窗）→ FontChsSmall 8px；其余 → FontChsNormal 12px。 */
    base = (fontId == 4u) ? (const uint8_t *)ADDR_FONT_CHS_SMALL
                          : (const uint8_t *)ADDR_FONT_CHS_NORMAL;
    g = base + ((uint32_t)(ChineseChar & CHS_GLYPH_IDX_MASK) << 7);
    if (ChineseChar & CHS_GLYPH_HALF_BIT)
        g += 64u;

    /* 本工程字模布局：TL+0 / BL+32 / TR+64 / BR+96（各 32B tile）。
     * 填入 upstream struct TextGlyph 行主序：Top = TL|TR，Bottom = BL|BR。 */
    copy_tile32(&glyph->gfxBufferTop[0], g + 0u);
    copy_tile32(&glyph->gfxBufferTop[8], g + 64u);
    copy_tile32(&glyph->gfxBufferBottom[0], g + 32u);
    copy_tile32(&glyph->gfxBufferBottom[8], g + 96u);

    glyph->width = GetChineseFontWidthFunc(ChineseChar, fontId);
    glyph->height = (fontId == 4u) ? 8u : 12u;
}

/* 根据字体类别返回字宽（upstream 同名；本工程汉字宽 = 库定宽，无逐字表）。 */
uint8_t GetChineseFontWidthFunc(uint16_t ChineseChar, uint8_t fontId)
{
    (void)ChineseChar;
    switch (fontId) {
    case 4u:
        return 8u;   /* FontChsSmall：与原生 font4 半角小字同节奏 */
    default:
        return 12u;  /* FontChsNormal：12px 产品字宽 */
    }
}
