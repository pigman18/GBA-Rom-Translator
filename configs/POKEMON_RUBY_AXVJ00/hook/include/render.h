#ifndef RENDER_H
#define RENDER_H

#include "game.h"
#include "text.h"

/* ============================================================================
 * render.h — 渲染层结构 + 原语（v4 text_render.h 复刻）
 *   渲染行入口 DrawGlyphTiles（会话校验 + linear/GRID 分派 + 两趟 refpr）
 *   在 PrintNextChar_hook.c；落址算法在 engine.c；配置在 scene.c。
 * ==========================================================================*/

/* 一字形的四个 tile 源（12px：TL/TR/BL/BR 各半列）。glyph_id 供 scene 做
 * per-glyph 槽绑定：0x8000|gidx = F9 汉字（可 PTR）；(fn<<8)|code = PCS/日文。 */
struct ChsGlyphTiles {
    const uint8_t *tl;
    const uint8_t *bl;
    const uint8_t *tr;
    const uint8_t *br;
    uint16_t glyph_id;
};

/* pokeruby TextGlyph（DecompressGlyph_Chinese 输出） */
struct TextGlyph {
    uint32_t gfxBufferTop[8];      /* 32B：上 8 行（2bpp） */
    uint32_t gfxBufferBottom[8];   /* 32B：下 8 行 */
    uint8_t  width;
    uint8_t  height;
};

/* 渲染行入口 */
void DrawGlyphTiles(TextPrinter *win, const struct ChsGlyphTiles *t, unsigned w);

/* FA/FB（等 A 箭头）前的相位对齐：半列相位时补 off、顶齐 cursorTileX */
void DrawGlyphTiles_arrow_prepare(TextPrinter *win);
void arrow_inplace12(TextPrinter *win);

/* 像素原语 */
uint8_t *vram_tile(TextPrinter *win, uint16_t tile);

/* 4bpp 烘焙 + 相位移位 + spill 一步到位（src 是未烘焙的 2bpp 字模） */
void DrawGlyphTile_refpr(
    TextPrinter *win, struct GlyphTileInfo *info,
    const uint8_t *src32, uint8_t *dest, uint8_t *spillTile);

/* 中文字库（ADDR_FONT_CHS_NORMAL/SMALL，索引=(code&0x7FFF)<<7，0x8000 再+64） */
void DecompressGlyph_Chinese(struct TextGlyph *glyph, uint16_t ChineseChar, uint8_t fontId);
uint8_t GetChineseFontWidthFunc(uint16_t ChineseChar, uint8_t fontId);

#endif /* RENDER_H */
