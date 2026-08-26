/* =====================================================================================
 * text_render.h — render 家族接口 + 共享原语（纯机制，零策略）
 *
 * 切缝 = pointers 级：render 入口统一接收规范字模四指针（phase-0 形态），
 * 之上（流解码/字源解析/分发）归 PrintNextChar_hook.c，
 * 之下（状态/落点/像素/表项）归 text_render_inplace12.c。
 * ===================================================================================== */
#ifndef TEXT_RENDER_H
#define TEXT_RENDER_H

#include "game.h"
#include "text.h"   /* struct TextGlyph（DecompressGlyph_Chinese 形参；避免前向不完整类型） */

/* 字形载体：规范形四指针 + 缓存键基底（CHS=0x8000|gidx；JP/SYM=(fontNum<<8)|code） */
struct ChsGlyphTiles {
    uint8_t *tl;
    uint8_t *bl;
    uint8_t *tr;
    uint8_t *br;
    uint16_t glyph_id;
};

/* ---- 策略实现（内部按 textMode 分发；不支持的 tm 不绘制）---- */
void render_inplace12(TextPrinter *win, const struct ChsGlyphTiles *t, unsigned w);

/* ---- FA/FB 箭头前置同步 ---- */
void arrow_inplace12(TextPrinter *win);

/* ---- 字形源解析 + CHS 汉库（heritage：pokeemerald-expansion chinese_text.c）---- */
int GetGlyph(TextPrinter *win, uint32_t code, uint8_t *out128, uint8_t *outWidth);
void DecompressGlyph_Chinese(struct TextGlyph *glyph, uint16_t ChineseChar, uint8_t fontId);
uint8_t GetChineseFontWidthFunc(uint16_t ChineseChar, uint8_t fontId);

/* ---- reference 原语（pret/pokeemerald vendored，见 reference/pokeemerald/）----
 * 当前为 draw_tile 的官方对拍基准；runtime 切换与路线 B 整列模型绑定。 */
void ref_glyph_copy(uint8_t *windowTiles, uint32_t winStrideBytes,
                    uint32_t x, uint32_t y,
                    const uint32_t *glyphPixels, int32_t width, int32_t height);
void ref_fill_rect4bit(uint8_t *windowTiles, uint32_t winStrideBytes,
                       uint32_t x, uint32_t y,
                       int32_t width, int32_t height, uint8_t fillValue);

/* ---- reference 原语（pret/pokeruby vendored，见 reference/pokeruby/）----
 * Tile 序/颜色表语义与本工程一致；唯一的硬契约：横向溢出写入 dest+32B
 * 物理右邻槽，调用方须保证 pair 相邻（tm0 线性天然满足）。 */
struct GlyphBuffer;
int32_t refpr_draw_tile_unshadowed(struct GlyphBuffer *gb, struct GlyphTileInfo *info);
int32_t refpr_draw_tile_shadowed(struct GlyphBuffer *gb, struct GlyphTileInfo *info);
void refpr_colors_init(struct GlyphBuffer *gb, uint8_t fg, uint8_t shadow, uint8_t bg);

/* ---- 共享原语 ---- */
void copy_tile32(void *dst_vram, const void *src_iwram);
uint8_t *vram_tile(TextPrinter *win, uint16_t tile);
void draw_tile(TextPrinter *win, struct GlyphTileInfo *info, uint8_t *spillTile);

#endif /* TEXT_RENDER_H */
