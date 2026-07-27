/*
 * TODO(未验�?: 未挂 main.asm�? * 旧双字节中文测宽（DrawGlyphTiles 时代）；现主路径�?F9+PrintNextChar�? * 对应 pokeruby: GetGlyphWidth (src/text.c)
 */
#include "game.h"

uint8_t GetGlyphWidth_Chinese(TextPrinter *win, uint32_t glyph)
{
    (void)win;
    (void)glyph;
    /* 占位：启用时按旧 GetGlyphWidthChinese.s 补全（lead/trail + font 0/3 �?4 tiles�?*/
    return 0;
}
