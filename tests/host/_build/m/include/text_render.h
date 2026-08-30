/* ============================================================================
 * tests/host/text_render.h — 测试 shim（仅宿主对拍 harness 用，严禁进 ROM 构建）
 *
 * 用途：给 vendored 官方原语 reference/pokeruby/draw_glyph_tile.c 提供
 * 编译所需的两个结构体（原 include/text_render.h 已随 v4 引擎移除，
 * 该文件通过 -I tests/host 解析到本 shim）。字段布局只需满足 vendored
 * 文件的访问面，与 ROM 侧真实结构无关。
 * ==========================================================================*/
#ifndef TEXT_RENDER_TEST_SHIM_H
#define TEXT_RENDER_TEST_SHIM_H

#include <stdint.h>

struct GlyphBuffer {
    uint32_t pixelRows[16];
    uint8_t colors[16];
};

struct GlyphTileInfo {
    uint32_t *dest;
    uint8_t *src;
    uint32_t colors[16];
    uint8_t width;
    uint8_t startPixel;
    uint8_t textMode;
};

#endif /* TEXT_RENDER_TEST_SHIM_H */
