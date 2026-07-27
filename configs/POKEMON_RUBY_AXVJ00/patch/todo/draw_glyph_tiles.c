/*
 * TODO(未验�?: 未挂 main.asm�? * 旧双字节中文绘制路径；已�?PrintNextChar + F9 + DrawGlyph_Chinese 取代�? * 对应 pokeruby: DrawGlyphTiles (src/text.c)
 */
#include "game.h"

int DrawGlyphTiles_Chinese(TextPrinter *win, uint32_t glyph)
{
    (void)win;
    (void)glyph;
    return 0; /* 0=回退原版 */
}
