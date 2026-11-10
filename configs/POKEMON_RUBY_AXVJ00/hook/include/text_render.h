/* text_render.h — 汉字位图直绘（方案B：ink-only / 任意相位 / 单趟多列） */
#ifndef TEXT_RENDER_H
#define TEXT_RENDER_H

#include "game.h"
#include "text.h"

/* 字形源：128B 4bpp 的四个象限（各 32B，TL/BL/TR/BR）+ 墨迹盒 + 步进。 */
struct ChsGlyphTiles {
    const uint8_t *tl;   /* 槽列 0..7  行 0..7  */
    const uint8_t *bl;   /* 槽列 0..7  行 8..15 */
    const uint8_t *tr;   /* 槽列 8..15 行 0..7  */
    const uint8_t *br;   /* 槽列 8..15 行 8..15 */
    uint16_t glyph_id;   /* 缓存键（当前绘制不消费，保留给上层） */
    uint8_t ink_w;       /* 墨迹宽（列） */
    uint8_t ink_h;       /* 墨迹高（行） */
    uint8_t pad_top;     /* 墨迹在 16 高槽里的起始行 */
};

/* 单字形绘制：写一行文本里的一个字符，游标按 advance 前进。 */
void DrawGlyphTiles(TextPrinter *win, const struct ChsGlyphTiles *t, unsigned advance);

/* 在行首对齐 ▼ / 光标：把行内像素游标推到下一个 8px 列边界。 */
void arrow_inplace12(TextPrinter *win);

/* 汉字字模解压（128B / 16×16 槽）与步进。 */
void DecompressGlyph_Chinese(struct TextGlyph *glyph, uint16_t ChineseChar, uint8_t fontId);
uint8_t GetChineseFontWidthFunc(uint16_t ChineseChar, uint8_t fontId);
void ChsGlyphMetrics(uint8_t fontId, struct ChsGlyphTiles *t);

/* 把一块 32B 4bpp 源 tile 原样写进 VRAM 指定 tile（▶ 光标等固定图标用）。 */
void ChsBlitTileDirect(TextPrinter *win, const uint8_t *src32, uint16_t tile);

void copy_tile32(void *dst_vram, const void *src_iwram);
uint8_t *vram_tile(TextPrinter *win, uint16_t tile);

/* 行状态 write_op（F9 短语 op；场景门控读取，绘制不使用）。 */
uint8_t chs_pitch_write_op(TextPrinter *win);
void chs_pitch_set_write_op(TextPrinter *win, uint8_t op);

#endif /* TEXT_RENDER_H */
