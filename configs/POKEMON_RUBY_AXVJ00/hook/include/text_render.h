/* =====================================================================================
 * text_render.h — render 家族接口 + 共享原语（纯机制，零策略）
 *
 * 切缝 = pointers 级：render 入口统一接收规范字模四指针（phase-0 形态），
 * 之上（流解码/字源解析/分发）归 text.c，之下（状态/落点/像素/表项）归各 render。
 * ===================================================================================== */
#ifndef TEXT_RENDER_H
#define TEXT_RENDER_H

#include "game.h"

/* 字形载体：规范形四指针 + 缓存键基底（CHS=0x8000|gidx；JP/SYM=(fontNum<<8)|code） */
struct ChsGlyphTiles {
    uint8_t *tl;
    uint8_t *bl;
    uint8_t *tr;
    uint8_t *br;
    uint16_t glyph_id;
};

/* render 唯一入口签名（pointers 级） */
typedef void (*render_fn)(TextPrinter *win, const struct ChsGlyphTiles *t, unsigned w);

/* ---- 策略实现（各自内部按 textMode 分发；不支持的 tm 不绘制）---- */
void render_inplace12(TextPrinter *win, const struct ChsGlyphTiles *t, unsigned w);
void render_band(TextPrinter *win, const struct ChsGlyphTiles *t, unsigned w);
void render_vfw12(TextPrinter *win, const struct ChsGlyphTiles *t, unsigned w);

/* ---- FA/FB 箭头前置同步（随 render 选择，各自适配自家相位状态）---- */
void arrow_inplace12(TextPrinter *win);
void arrow_band(TextPrinter *win);

/* ---- 共享原语 ---- */
void copy_tile32(void *dst_vram, const void *src_iwram);
uint8_t *vram_tile(TextPrinter *win, uint16_t tile);
void draw_tile(TextPrinter *win, struct GlyphTileInfo *info, uint8_t *spillTile);

/* ---- 实验选择器 @0x0203FF8C（两代 pitch 布局的公共空闲字节）----
 * 0=调用点默认（vfw12） 1=band 2=inplace12 3=vfw12
 * mGBA 改该内存字节即同 ROM 切策略。 */
#define RENDER_SEL_ADDR 0x0203FF8Cu
render_fn render_active(render_fn dflt);

#endif /* TEXT_RENDER_H */
