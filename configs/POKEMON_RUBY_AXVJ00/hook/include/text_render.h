/* text_render.h — refpr + pitch + 日版 GetCursorTileNum（薄路径） */
#ifndef TEXT_RENDER_H
#define TEXT_RENDER_H

#include "game.h"
#include "text.h"

struct ChsGlyphTiles {
    uint8_t *tl;
    uint8_t *bl;
    uint8_t *tr;
    uint8_t *br;
    uint16_t glyph_id;
};

void DrawGlyphTiles(TextPrinter *win, const struct ChsGlyphTiles *t, unsigned w);
void DrawGlyphTiles_arrow_prepare(TextPrinter *win);
void arrow_inplace12(TextPrinter *win);

void DecompressGlyph_Chinese(struct TextGlyph *glyph, uint16_t ChineseChar, uint8_t fontId);
uint8_t GetChineseFontWidthFunc(uint16_t ChineseChar, uint8_t fontId);
unsigned GetGlyphWidthChinese(TextPrinter *win, uint32_t gidx_or_code, unsigned glyphWidth);

void DrawGlyphTile_refpr(
    TextPrinter *win, struct GlyphTileInfo *info,
    const uint8_t *src32, uint8_t *dest, uint8_t *spillTile);

int32_t refpr_draw_tile_shadowed(struct GlyphBuffer *gb, struct GlyphTileInfo *info);
void refpr_colors_init(struct GlyphBuffer *gb, uint8_t fg, uint8_t shadow, uint8_t bg);

void copy_tile32(void *dst_vram, const void *src_iwram);
uint8_t *vram_tile(TextPrinter *win, uint16_t tile);

#endif /* TEXT_RENDER_H */
