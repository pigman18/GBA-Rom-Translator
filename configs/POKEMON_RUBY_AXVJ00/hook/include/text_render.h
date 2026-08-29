/* ============================================================================
 * text_render.h — 像素原语 + 行像素相位（pitch 槽）+ 渲染行入口
 *
 * 实现即 bak/text_original/text_render.c（长期实测通过），仅两处标注
 * 2026-08-30 的小改（PTR 的 per-glyph 接入与 16px 步进），见该文件。
 * 落址/搬位在 src/text/text_scene.c（声明式配置）。
 * ==========================================================================*/
#ifndef TEXT_RENDER_H
#define TEXT_RENDER_H

#include "game.h"
#include "text.h"

/* 一字形的四个 tile 源（12px：TL/TR/BL/BR 各半列）。glyph_id 供 scene 做
 * per-glyph 槽绑定（scene_note_glyph）。 */
struct ChsGlyphTiles {
    uint8_t *tl;
    uint8_t *bl;
    uint8_t *tr;
    uint8_t *br;
    uint16_t glyph_id;
};

/* 渲染行入口（DrawGlyphTiles_common：会话校验 + linear/GRID 分派 + 两趟） */
void DrawGlyphTiles(TextPrinter *win, const struct ChsGlyphTiles *t, unsigned w);

/* FA/FB（等 A 箭头）前的相位对齐：半列相位时补 off、顶齐 cursorTileX */
void DrawGlyphTiles_arrow_prepare(TextPrinter *win);
void arrow_inplace12(TextPrinter *win);

/* ---- 像素原语 ---- */
void copy_tile32(void *dst_vram, const void *src_iwram);
uint8_t *vram_tile(TextPrinter *win, uint16_t tile);

/* 4bpp 烘焙 + 相位移位 + spill 一步到位（src 是未烘焙的 2bpp 字模） */
void DrawGlyphTile_refpr(
    TextPrinter *win, struct GlyphTileInfo *info,
    const uint8_t *src32, uint8_t *dest, uint8_t *spillTile);

/* ---- 中文字库 ---- */
void DecompressGlyph_Chinese(struct TextGlyph *glyph, uint16_t ChineseChar, uint8_t fontId);
uint8_t GetChineseFontWidthFunc(uint16_t ChineseChar, uint8_t fontId);
unsigned GetGlyphWidthChinese(TextPrinter *win, uint32_t gidx_or_code, unsigned glyphWidth);

/* ---- 行像素相位（pitch 槽，EWRAM 0x0203FF80/0x0203FF90，全引擎唯一一套）----
 * write_op：F9 短语 op 记账（mode2 默认路径消费）。 */
uint8_t chs_pitch_write_op(TextPrinter *win);
void chs_pitch_set_write_op(TextPrinter *win, uint8_t op);

int32_t refpr_draw_tile_shadowed(struct GlyphBuffer *gb, struct GlyphTileInfo *info);
void refpr_colors_init(struct GlyphBuffer *gb, uint8_t fg, uint8_t shadow, uint8_t bg);

#endif /* TEXT_RENDER_H */
