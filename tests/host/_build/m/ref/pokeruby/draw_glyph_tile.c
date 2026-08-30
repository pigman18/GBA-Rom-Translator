/* =====================================================================================
 * draw_glyph_tile.c — reference vendored primitives（pret/pokeruby text.c）
 *
 * source  : tools/pokeruby/src/text.c
 *           sGlyphMasks[L251], sGlyphShiftAmounts[L345],
 *           Shift funcs tables [L466-495], ApplyColors_[L2729/2752],
 *           DrawGlyphTile_[L3877/4090], ShiftGlyphTile_*_[L3952/4161]
 * fetched : local clone tools/pokeruby @ master（diff 同步以该镜像为准）
 * 改写    : 仅一处机械参数化——两个 DrawGlyphTile 主函数的 sGlyphBuffer 全局
 *           （IWRAM）改为首参 struct GlyphBuffer *gb；其余逐字保留。
 * 契约    : 标准 GBA tile 字节序（高半 nibble=左列），colors[16]=终端色 LUT
 *           （[i]=i 直通、[0]=bg、[14]=shadow、[15]=fg）；横向溢出写入
 *           dest+32B 的物理右邻槽——调用方须保证 pair 相邻性。
 * 入口    : refpr_draw_tile_unshadowed / refpr_draw_tile_shadowed
 * ===================================================================================== */
#include "../../include/text_render.h"

typedef uint8_t  u8;
typedef uint16_t u16;
typedef int32_t  s32;
typedef uint32_t u32;

#ifndef TEXT_MODE_UNKNOWN2
#define TEXT_MODE_UNKNOWN2 2u
#endif

/* upstream src/text.c L72 */
struct ShiftAmount
{
    u32 left;
    u32 right;
};

/* upstream src/text.c L163-178（前置声明，函数体在文件尾） */
static void ShiftGlyphTile_UnshadowedFont_Width0(struct GlyphBuffer *, u8 *, u32 *, u8);
static void ShiftGlyphTile_UnshadowedFont_Width1(struct GlyphBuffer *, u8 *, u32 *, u8);
static void ShiftGlyphTile_UnshadowedFont_Width2(struct GlyphBuffer *, u8 *, u32 *, u8);
static void ShiftGlyphTile_UnshadowedFont_Width3(struct GlyphBuffer *, u8 *, u32 *, u8);
static void ShiftGlyphTile_UnshadowedFont_Width4(struct GlyphBuffer *, u8 *, u32 *, u8);
static void ShiftGlyphTile_UnshadowedFont_Width5(struct GlyphBuffer *, u8 *, u32 *, u8);
static void ShiftGlyphTile_UnshadowedFont_Width6(struct GlyphBuffer *, u8 *, u32 *, u8);
static void ShiftGlyphTile_UnshadowedFont_Width7(struct GlyphBuffer *, u8 *, u32 *, u8);
static void ShiftGlyphTile_UnshadowedFont_Width8(struct GlyphBuffer *, u8 *, u32 *, u8);

static void ShiftGlyphTile_ShadowedFont_Width0(struct GlyphBuffer *, u32 *, u32 *, u8);
static void ShiftGlyphTile_ShadowedFont_Width1(struct GlyphBuffer *, u32 *, u32 *, u8);
static void ShiftGlyphTile_ShadowedFont_Width2(struct GlyphBuffer *, u32 *, u32 *, u8);
static void ShiftGlyphTile_ShadowedFont_Width3(struct GlyphBuffer *, u32 *, u32 *, u8);
static void ShiftGlyphTile_ShadowedFont_Width4(struct GlyphBuffer *, u32 *, u32 *, u8);
static void ShiftGlyphTile_ShadowedFont_Width5(struct GlyphBuffer *, u32 *, u32 *, u8);
static void ShiftGlyphTile_ShadowedFont_Width6(struct GlyphBuffer *, u32 *, u32 *, u8);
static void ShiftGlyphTile_ShadowedFont_Width7(struct GlyphBuffer *, u32 *, u32 *, u8);
static void ShiftGlyphTile_ShadowedFont_Width8(struct GlyphBuffer *, u32 *, u32 *, u8);


static const u32 sGlyphMasks[9][8][3] =
{
    {
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xFFFFFFF0, },
        { 0x0000000F,0xFFFFFFFF,0xFFFFFF00, },
        { 0x000000FF,0xFFFFFFFF,0xFFFFF000, },
        { 0x00000FFF,0xFFFFFFFF,0xFFFF0000, },
        { 0x0000FFFF,0xFFFFFFFF,0xFFF00000, },
        { 0x000FFFFF,0xFFFFFFFF,0xFF000000, },
        { 0x00FFFFFF,0xFFFFFFFF,0xF0000000, },
        { 0x0FFFFFFF,0xFFFFFFFF,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xFFFFFF00, },
        { 0x0000000F,0xFFFFFFFF,0xFFFFF000, },
        { 0x000000FF,0xFFFFFFFF,0xFFFF0000, },
        { 0x00000FFF,0xFFFFFFFF,0xFFF00000, },
        { 0x0000FFFF,0xFFFFFFFF,0xFF000000, },
        { 0x000FFFFF,0xFFFFFFFF,0xF0000000, },
        { 0x00FFFFFF,0xFFFFFFFF,0x00000000, },
        { 0x0FFFFFFF,0xFFFFFFF0,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xFFFFF000, },
        { 0x0000000F,0xFFFFFFFF,0xFFFF0000, },
        { 0x000000FF,0xFFFFFFFF,0xFFF00000, },
        { 0x00000FFF,0xFFFFFFFF,0xFF000000, },
        { 0x0000FFFF,0xFFFFFFFF,0xF0000000, },
        { 0x000FFFFF,0xFFFFFFFF,0x00000000, },
        { 0x00FFFFFF,0xFFFFFFF0,0x00000000, },
        { 0x0FFFFFFF,0xFFFFFF00,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xFFFF0000, },
        { 0x0000000F,0xFFFFFFFF,0xFFF00000, },
        { 0x000000FF,0xFFFFFFFF,0xFF000000, },
        { 0x00000FFF,0xFFFFFFFF,0xF0000000, },
        { 0x0000FFFF,0xFFFFFFFF,0x00000000, },
        { 0x000FFFFF,0xFFFFFFF0,0x00000000, },
        { 0x00FFFFFF,0xFFFFFF00,0x00000000, },
        { 0x0FFFFFFF,0xFFFFF000,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xFFF00000, },
        { 0x0000000F,0xFFFFFFFF,0xFF000000, },
        { 0x000000FF,0xFFFFFFFF,0xF0000000, },
        { 0x00000FFF,0xFFFFFFFF,0x00000000, },
        { 0x0000FFFF,0xFFFFFFF0,0x00000000, },
        { 0x000FFFFF,0xFFFFFF00,0x00000000, },
        { 0x00FFFFFF,0xFFFFF000,0x00000000, },
        { 0x0FFFFFFF,0xFFFF0000,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xFF000000, },
        { 0x0000000F,0xFFFFFFFF,0xF0000000, },
        { 0x000000FF,0xFFFFFFFF,0x00000000, },
        { 0x00000FFF,0xFFFFFFF0,0x00000000, },
        { 0x0000FFFF,0xFFFFFF00,0x00000000, },
        { 0x000FFFFF,0xFFFFF000,0x00000000, },
        { 0x00FFFFFF,0xFFFF0000,0x00000000, },
        { 0x0FFFFFFF,0xFFF00000,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xF0000000, },
        { 0x0000000F,0xFFFFFFFF,0x00000000, },
        { 0x000000FF,0xFFFFFFF0,0x00000000, },
        { 0x00000FFF,0xFFFFFF00,0x00000000, },
        { 0x0000FFFF,0xFFFFF000,0x00000000, },
        { 0x000FFFFF,0xFFFF0000,0x00000000, },
        { 0x00FFFFFF,0xFFF00000,0x00000000, },
        { 0x0FFFFFFF,0xFF000000,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0x00000000, },
        { 0x0000000F,0xFFFFFFF0,0x00000000, },
        { 0x000000FF,0xFFFFFF00,0x00000000, },
        { 0x00000FFF,0xFFFFF000,0x00000000, },
        { 0x0000FFFF,0xFFFF0000,0x00000000, },
        { 0x000FFFFF,0xFFF00000,0x00000000, },
        { 0x00FFFFFF,0xFF000000,0x00000000, },
        { 0x0FFFFFFF,0xF0000000,0x00000000, },
    },
};

static const struct ShiftAmount sGlyphShiftAmounts[8] =
{
    {  0, 32 },
    {  4, 28 },
    {  8, 24 },
    { 12, 20 },
    { 16, 16 },
    { 20, 12 },
    { 24,  8 },
    { 28,  4 },
};

typedef void (*ShiftGlyphTileUnshadowedFunc)(struct GlyphBuffer *, u8 *, u32 *, u8);

static const ShiftGlyphTileUnshadowedFunc sShiftGlyphTileUnshadowedFuncs[] =
{
    ShiftGlyphTile_UnshadowedFont_Width0,
    ShiftGlyphTile_UnshadowedFont_Width1,
    ShiftGlyphTile_UnshadowedFont_Width2,
    ShiftGlyphTile_UnshadowedFont_Width3,
    ShiftGlyphTile_UnshadowedFont_Width4,
    ShiftGlyphTile_UnshadowedFont_Width5,
    ShiftGlyphTile_UnshadowedFont_Width6,
    ShiftGlyphTile_UnshadowedFont_Width7,
    ShiftGlyphTile_UnshadowedFont_Width8,
};
typedef void (*ShiftGlyphTileShadowedFunc)(struct GlyphBuffer *, u32 *, u32 *, u8);

static const ShiftGlyphTileShadowedFunc sShiftGlyphTileShadowedFuncs[] =
{
    ShiftGlyphTile_ShadowedFont_Width0,
    ShiftGlyphTile_ShadowedFont_Width1,
    ShiftGlyphTile_ShadowedFont_Width2,
    ShiftGlyphTile_ShadowedFont_Width3,
    ShiftGlyphTile_ShadowedFont_Width4,
    ShiftGlyphTile_ShadowedFont_Width5,
    ShiftGlyphTile_ShadowedFont_Width6,
    ShiftGlyphTile_ShadowedFont_Width7,
    ShiftGlyphTile_ShadowedFont_Width8,
};

static void ApplyColors_UnshadowedFont(const u8 *src, u32 *dest, u8 foreground, u8 background)
{
    u32 a[2];
    s32 i;
    const u8 *srcRows = src;

    a[0] = background;
    a[1] = foreground;

    for (i = 0; i < 8; i++)
    {
        u32 destRow = a[srcRows[i] & 1]
                    | (a[(srcRows[i] >> 1) & 1] << 4)
                    | (a[(srcRows[i] >> 2) & 1] << 8)
                    | (a[(srcRows[i] >> 3) & 1] << 12)
                    | (a[(srcRows[i] >> 4) & 1] << 16)
                    | (a[(srcRows[i] >> 5) & 1] << 20)
                    | (a[(srcRows[i] >> 6) & 1] << 24)
                    | (a[(srcRows[i] >> 7)    ] << 28);
        dest[i] = destRow;
    }
}

static void ApplyColors_ShadowedFont(const void *src, void *dest, u8 foreground, u8 shadow, u8 background)
{
    u32 a[0x10];
    s32 i;
    const u32 *curSrc;
    u32 *curDest;
    u32 colorMask;

    a[0x1] = 0x1;
    a[0x2] = 0x2;
    a[0x3] = 0x3;
    a[0x4] = 0x4;
    a[0x5] = 0x5;
    a[0x6] = 0x6;
    a[0x7] = 0x7;
    a[0x8] = 0x8;
    a[0x9] = 0x9;
    a[0xA] = 0xA;
    a[0xB] = 0xB;
    a[0xC] = 0xC;
    a[0xD] = 0xD;
    a[0x0] = background;
    a[0xE] = shadow;
    a[0xF] = foreground;

    colorMask = 0xF;

    curSrc = src;
    curDest = dest;

    for (i = 7; i >= 0; i--)
    {
        u32 row = *curSrc++;
        u32 recoloredRow = a[row & colorMask]
                         | (a[(row >> 4) & colorMask] << 4)
                         | (a[(row >> 8) & colorMask] << 8)
                         | (a[(row >> 12) & colorMask] << 12)
                         | (a[(row >> 16) & colorMask] << 16)
                         | (a[(row >> 20) & colorMask] << 20)
                         | (a[(row >> 24) & colorMask] << 24)
                         | (a[(row >> 28)            ] << 28);
        *curDest++ = recoloredRow;
    }
}

s32 refpr_draw_tile_unshadowed(struct GlyphBuffer *gb, struct GlyphTileInfo *glyphTileInfo)
{
    struct GlyphBuffer *glyphBuffer = gb;
    u32 colors[2];
    u32 *buffer = glyphTileInfo->dest;
    const u32 *masks = sGlyphMasks[glyphTileInfo->width][glyphTileInfo->startPixel];
    u32 mask1 = masks[0] | masks[2];

    glyphBuffer->pixelRows[0] = buffer[0] & mask1;
    glyphBuffer->pixelRows[1] = buffer[1] & mask1;
    glyphBuffer->pixelRows[2] = buffer[2] & mask1;
    glyphBuffer->pixelRows[3] = buffer[3] & mask1;
    glyphBuffer->pixelRows[4] = buffer[4] & mask1;
    glyphBuffer->pixelRows[5] = buffer[5] & mask1;
    glyphBuffer->pixelRows[6] = buffer[6] & mask1;
    glyphBuffer->pixelRows[7] = buffer[7] & mask1;

    if (glyphTileInfo->startPixel + glyphTileInfo->width > 8)
    {
        u32 mask2 = masks[1];
        if (glyphTileInfo->textMode == TEXT_MODE_UNKNOWN2)
        {
            glyphBuffer->pixelRows[8] = buffer[8] & mask2;
            glyphBuffer->pixelRows[9] = buffer[9] & mask2;
            glyphBuffer->pixelRows[10] = buffer[10] & mask2;
            glyphBuffer->pixelRows[11] = buffer[11] & mask2;
            glyphBuffer->pixelRows[12] = buffer[12] & mask2;
            glyphBuffer->pixelRows[13] = buffer[13] & mask2;
            glyphBuffer->pixelRows[14] = buffer[14] & mask2;
            glyphBuffer->pixelRows[15] = buffer[15] & mask2;
        }
        else
        {
            glyphBuffer->pixelRows[8] = buffer[16] & mask2;
            glyphBuffer->pixelRows[9] = buffer[17] & mask2;
            glyphBuffer->pixelRows[10] = buffer[18] & mask2;
            glyphBuffer->pixelRows[11] = buffer[19] & mask2;
            glyphBuffer->pixelRows[12] = buffer[20] & mask2;
            glyphBuffer->pixelRows[13] = buffer[21] & mask2;
            glyphBuffer->pixelRows[14] = buffer[22] & mask2;
            glyphBuffer->pixelRows[15] = buffer[23] & mask2;
        }
    }

    colors[0] = glyphTileInfo->colors[0];
    colors[1] = glyphTileInfo->colors[15];

    sShiftGlyphTileUnshadowedFuncs[glyphTileInfo->width](glyphBuffer, glyphTileInfo->src, colors, glyphTileInfo->startPixel);

    buffer[0] = glyphBuffer->pixelRows[0];
    buffer[1] = glyphBuffer->pixelRows[1];
    buffer[2] = glyphBuffer->pixelRows[2];
    buffer[3] = glyphBuffer->pixelRows[3];
    buffer[4] = glyphBuffer->pixelRows[4];
    buffer[5] = glyphBuffer->pixelRows[5];
    buffer[6] = glyphBuffer->pixelRows[6];
    buffer[7] = glyphBuffer->pixelRows[7];

    if (glyphTileInfo->startPixel + glyphTileInfo->width > 8)
    {
        if (glyphTileInfo->textMode != TEXT_MODE_UNKNOWN2)
            buffer += 8;
        buffer[8] = glyphBuffer->pixelRows[8];
        buffer[9] = glyphBuffer->pixelRows[9];
        buffer[10] = glyphBuffer->pixelRows[10];
        buffer[11] = glyphBuffer->pixelRows[11];
        buffer[12] = glyphBuffer->pixelRows[12];
        buffer[13] = glyphBuffer->pixelRows[13];
        buffer[14] = glyphBuffer->pixelRows[14];
        buffer[15] = glyphBuffer->pixelRows[15];
    }

    return (glyphTileInfo->startPixel + glyphTileInfo->width) / 8;
}

static void ShiftGlyphTile_UnshadowedFont_Width0(struct GlyphBuffer *glyphBuffer, u8 *src, u32 *a3, u8 startPixel)
{
}

static void ShiftGlyphTile_UnshadowedFont_Width1(struct GlyphBuffer *glyphBuffer, u8 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u8 i;
    for (i = 0; i < 8; i++)
    {
        u32 val = colors[src[i] >> 7];
        u32 *dest = &glyphBuffer->pixelRows[i];
        dest[0] |= val << shiftAmount->left;
        dest[8] |= val >> shiftAmount->right;
    }
}

static void ShiftGlyphTile_UnshadowedFont_Width2(struct GlyphBuffer *glyphBuffer, u8 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u8 i;
    for (i = 0; i < 8; i++)
    {
        u32 val = (colors[(src[i] >> 7) & 1] << 0)
                | (colors[(src[i] >> 6) & 1] << 4);
        u32 *dest = &glyphBuffer->pixelRows[i];
        dest[0] |= val << shiftAmount->left;
        dest[8] |= val >> shiftAmount->right;
    }
}

static void ShiftGlyphTile_UnshadowedFont_Width3(struct GlyphBuffer *glyphBuffer, u8 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u8 i;
    for (i = 0; i < 8; i++)
    {
        // XXX: why 4?
        u32 val = (colors[(src[i] >> 7) & 1] <<  0)
                | (colors[(src[i] >> 6) & 1] <<  4)
                | (colors[(src[i] >> 5) & 1] <<  8)
                | (colors[(src[i] >> 4) & 1] << 12);
        u32 *dest = &glyphBuffer->pixelRows[i];
        dest[0] |= val << shiftAmount->left;
        dest[8] |= val >> shiftAmount->right;
    }
}

static void ShiftGlyphTile_UnshadowedFont_Width4(struct GlyphBuffer *glyphBuffer, u8 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u8 i;
    for (i = 0; i < 8; i++)
    {
        u32 val = (colors[(src[i] >> 7) & 1] <<  0)
                | (colors[(src[i] >> 6) & 1] <<  4)
                | (colors[(src[i] >> 5) & 1] <<  8)
                | (colors[(src[i] >> 4) & 1] << 12);
        u32 *dest = &glyphBuffer->pixelRows[i];
        dest[0] |= val << shiftAmount->left;
        dest[8] |= val >> shiftAmount->right;
    }
}

static void ShiftGlyphTile_UnshadowedFont_Width5(struct GlyphBuffer *glyphBuffer, u8 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u8 i;
    for (i = 0; i < 8; i++)
    {
        u32 val = (colors[(src[i] >> 7) & 1] <<  0)
                | (colors[(src[i] >> 6) & 1] <<  4)
                | (colors[(src[i] >> 5) & 1] <<  8)
                | (colors[(src[i] >> 4) & 1] << 12)
                | (colors[(src[i] >> 3) & 1] << 16);
        u32 *dest = &glyphBuffer->pixelRows[i];
        dest[0] |= val << shiftAmount->left;
        dest[8] |= val >> shiftAmount->right;
    }
}

static void ShiftGlyphTile_UnshadowedFont_Width6(struct GlyphBuffer *glyphBuffer, u8 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u8 i;
    for (i = 0; i < 8; i++)
    {
        u32 val = (colors[(src[i] >> 7) & 1] <<  0)
                | (colors[(src[i] >> 6) & 1] <<  4)
                | (colors[(src[i] >> 5) & 1] <<  8)
                | (colors[(src[i] >> 4) & 1] << 12)
                | (colors[(src[i] >> 3) & 1] << 16)
                | (colors[(src[i] >> 2) & 1] << 20);
        u32 *dest = &glyphBuffer->pixelRows[i];
        dest[0] |= val << shiftAmount->left;
        dest[8] |= val >> shiftAmount->right;
    }
}

static void ShiftGlyphTile_UnshadowedFont_Width7(struct GlyphBuffer *glyphBuffer, u8 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u8 i;
    for (i = 0; i < 8; i++)
    {
        u32 val = (colors[(src[i] >> 7) & 1] <<  0)
                | (colors[(src[i] >> 6) & 1] <<  4)
                | (colors[(src[i] >> 5) & 1] <<  8)
                | (colors[(src[i] >> 4) & 1] << 12)
                | (colors[(src[i] >> 3) & 1] << 16)
                | (colors[(src[i] >> 2) & 1] << 20)
                | (colors[(src[i] >> 1) & 1] << 24);
        u32 *dest = &glyphBuffer->pixelRows[i];
        dest[0] |= val << shiftAmount->left;
        dest[8] |= val >> shiftAmount->right;
    }
}

static void ShiftGlyphTile_UnshadowedFont_Width8(struct GlyphBuffer *glyphBuffer, u8 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u8 i;
    for (i = 0; i < 8; i++)
    {
        u32 val = (colors[(src[i] >> 7) & 1] <<  0)
                | (colors[(src[i] >> 6) & 1] <<  4)
                | (colors[(src[i] >> 5) & 1] <<  8)
                | (colors[(src[i] >> 4) & 1] << 12)
                | (colors[(src[i] >> 3) & 1] << 16)
                | (colors[(src[i] >> 2) & 1] << 20)
                | (colors[(src[i] >> 1) & 1] << 24)
                | (colors[(src[i] >> 0) & 1] << 28);
        u32 *dest = &glyphBuffer->pixelRows[i];
        dest[0] |= val << shiftAmount->left;
        dest[8] |= val >> shiftAmount->right;
    }
}


s32 refpr_draw_tile_shadowed(struct GlyphBuffer *gb, struct GlyphTileInfo *glyphTileInfo)
{
    struct GlyphBuffer *glyphBuffer = gb;
    u32 *buffer = glyphTileInfo->dest;
    const u32 *masks = sGlyphMasks[glyphTileInfo->width][glyphTileInfo->startPixel];
    u32 mask1 = masks[0] | masks[2];

    glyphBuffer->pixelRows[0] = buffer[0] & mask1;
    glyphBuffer->pixelRows[1] = buffer[1] & mask1;
    glyphBuffer->pixelRows[2] = buffer[2] & mask1;
    glyphBuffer->pixelRows[3] = buffer[3] & mask1;
    glyphBuffer->pixelRows[4] = buffer[4] & mask1;
    glyphBuffer->pixelRows[5] = buffer[5] & mask1;
    glyphBuffer->pixelRows[6] = buffer[6] & mask1;
    glyphBuffer->pixelRows[7] = buffer[7] & mask1;

    if (glyphTileInfo->startPixel + glyphTileInfo->width > 8)
    {
        u32 mask2 = masks[1];
        if (glyphTileInfo->textMode == TEXT_MODE_UNKNOWN2)
        {
            glyphBuffer->pixelRows[8] = buffer[8] & mask2;
            glyphBuffer->pixelRows[9] = buffer[9] & mask2;
            glyphBuffer->pixelRows[10] = buffer[10] & mask2;
            glyphBuffer->pixelRows[11] = buffer[11] & mask2;
            glyphBuffer->pixelRows[12] = buffer[12] & mask2;
            glyphBuffer->pixelRows[13] = buffer[13] & mask2;
            glyphBuffer->pixelRows[14] = buffer[14] & mask2;
            glyphBuffer->pixelRows[15] = buffer[15] & mask2;
        }
        else
        {
            glyphBuffer->pixelRows[8] = buffer[16] & mask2;
            glyphBuffer->pixelRows[9] = buffer[17] & mask2;
            glyphBuffer->pixelRows[10] = buffer[18] & mask2;
            glyphBuffer->pixelRows[11] = buffer[19] & mask2;
            glyphBuffer->pixelRows[12] = buffer[20] & mask2;
            glyphBuffer->pixelRows[13] = buffer[21] & mask2;
            glyphBuffer->pixelRows[14] = buffer[22] & mask2;
            glyphBuffer->pixelRows[15] = buffer[23] & mask2;
        }
    }

    sShiftGlyphTileShadowedFuncs[glyphTileInfo->width](glyphBuffer, (u32 *)glyphTileInfo->src, glyphTileInfo->colors, glyphTileInfo->startPixel);

    buffer[0] = glyphBuffer->pixelRows[0];
    buffer[1] = glyphBuffer->pixelRows[1];
    buffer[2] = glyphBuffer->pixelRows[2];
    buffer[3] = glyphBuffer->pixelRows[3];
    buffer[4] = glyphBuffer->pixelRows[4];
    buffer[5] = glyphBuffer->pixelRows[5];
    buffer[6] = glyphBuffer->pixelRows[6];
    buffer[7] = glyphBuffer->pixelRows[7];

    if (glyphTileInfo->startPixel + glyphTileInfo->width > 8)
    {
        if (glyphTileInfo->textMode != TEXT_MODE_UNKNOWN2)
            buffer += 8;
        buffer[8] = glyphBuffer->pixelRows[8];
        buffer[9] = glyphBuffer->pixelRows[9];
        buffer[10] = glyphBuffer->pixelRows[10];
        buffer[11] = glyphBuffer->pixelRows[11];
        buffer[12] = glyphBuffer->pixelRows[12];
        buffer[13] = glyphBuffer->pixelRows[13];
        buffer[14] = glyphBuffer->pixelRows[14];
        buffer[15] = glyphBuffer->pixelRows[15];
    }

    return (glyphTileInfo->startPixel + glyphTileInfo->width) / 8;
}

static void ShiftGlyphTile_ShadowedFont_Width0(struct GlyphBuffer *glyphBuffer, u32 *src, u32 *colors, u8 startPixel)
{
}

static void ShiftGlyphTile_ShadowedFont_Width1(struct GlyphBuffer *glyphBuffer, u32 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u8 i;
    for (i = 0; i < 8; i++)
    {
        u32 val = colors[src[i] & 0xF];
        u32 *dest = &glyphBuffer->pixelRows[i];
        dest[0] |= val << shiftAmount->left;
        dest[8] |= val >> shiftAmount->right;
    }
}

static void ShiftGlyphTile_ShadowedFont_Width2(struct GlyphBuffer *glyphBuffer, u32 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u8 i;
    for (i = 0; i < 8; i++)
    {
        u32 val = (colors[(src[i] >> 0) & 0xF] << 0)
                | (colors[(src[i] >> 4) & 0xF] << 4);
        u32 *dest = &glyphBuffer->pixelRows[i];
        dest[0] |= val << shiftAmount->left;
        dest[8] |= val >> shiftAmount->right;
    }
}

static void ShiftGlyphTile_ShadowedFont_Width3(struct GlyphBuffer *glyphBuffer, u32 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u8 i;
    for (i = 0; i < 8; i++)
    {
        u32 val = (colors[(src[i] >> 0) & 0xF] << 0)
                | (colors[(src[i] >> 4) & 0xF] << 4)
                | (colors[(src[i] >> 8) & 0xF] << 8);
        u32 *dest = &glyphBuffer->pixelRows[i];
        dest[0] |= val << shiftAmount->left;
        dest[8] |= val >> shiftAmount->right;
    }
}

static void ShiftGlyphTile_ShadowedFont_Width4(struct GlyphBuffer *glyphBuffer, u32 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u8 i;
    for (i = 0; i < 8; i++)
    {
        u32 val = (colors[(src[i] >>  0) & 0xF] <<  0)
                | (colors[(src[i] >>  4) & 0xF] <<  4)
                | (colors[(src[i] >>  8) & 0xF] <<  8)
                | (colors[(src[i] >> 12) & 0xF] << 12);
        u32 *dest = &glyphBuffer->pixelRows[i];
        dest[0] |= val << shiftAmount->left;
        dest[8] |= val >> shiftAmount->right;
    }
}

#define SHIFT_GLYPH_WIDTH5_STEP(i)                          \
val = (colors[(src[i] >>  0) & 0xF] <<  0)                  \
    | (colors[(src[i] >>  4) & 0xF] <<  4)                  \
    | (colors[(src[i] >>  8) & 0xF] <<  8)                  \
    | (colors[(src[i] >> 12) & 0xF] << 12)                  \
    | (colors[(src[i] >> 16) & 0xF] << 16);                 \
glyphBuffer->pixelRows[i]     |= val << shiftAmount->left;  \
glyphBuffer->pixelRows[i + 8] |= val >> shiftAmount->right; \

static void ShiftGlyphTile_ShadowedFont_Width5(struct GlyphBuffer *glyphBuffer, u32 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u32 val;
    SHIFT_GLYPH_WIDTH5_STEP(0)
    SHIFT_GLYPH_WIDTH5_STEP(1)
    SHIFT_GLYPH_WIDTH5_STEP(2)
    SHIFT_GLYPH_WIDTH5_STEP(3)
    SHIFT_GLYPH_WIDTH5_STEP(4)
    SHIFT_GLYPH_WIDTH5_STEP(5)
    SHIFT_GLYPH_WIDTH5_STEP(6)
    SHIFT_GLYPH_WIDTH5_STEP(7)
}

#define SHIFT_GLYPH_WIDTH6_STEP(i)                          \
val = (colors[(src[i] >>  0) & 0xF] <<  0)                  \
    | (colors[(src[i] >>  4) & 0xF] <<  4)                  \
    | (colors[(src[i] >>  8) & 0xF] <<  8)                  \
    | (colors[(src[i] >> 12) & 0xF] << 12)                  \
    | (colors[(src[i] >> 16) & 0xF] << 16)                  \
    | (colors[(src[i] >> 20) & 0xF] << 20);                 \
glyphBuffer->pixelRows[i]     |= val << shiftAmount->left;  \
glyphBuffer->pixelRows[i + 8] |= val >> shiftAmount->right; \

static void ShiftGlyphTile_ShadowedFont_Width6(struct GlyphBuffer *glyphBuffer, u32 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u32 val;
    SHIFT_GLYPH_WIDTH6_STEP(0)
    SHIFT_GLYPH_WIDTH6_STEP(1)
    SHIFT_GLYPH_WIDTH6_STEP(2)
    SHIFT_GLYPH_WIDTH6_STEP(3)
    SHIFT_GLYPH_WIDTH6_STEP(4)
    SHIFT_GLYPH_WIDTH6_STEP(5)
    SHIFT_GLYPH_WIDTH6_STEP(6)
    SHIFT_GLYPH_WIDTH6_STEP(7)
}

#define SHIFT_GLYPH_WIDTH7_STEP(i)                          \
val = (colors[(src[i] >>  0) & 0xF] <<  0)                  \
    | (colors[(src[i] >>  4) & 0xF] <<  4)                  \
    | (colors[(src[i] >>  8) & 0xF] <<  8)                  \
    | (colors[(src[i] >> 12) & 0xF] << 12)                  \
    | (colors[(src[i] >> 16) & 0xF] << 16)                  \
    | (colors[(src[i] >> 20) & 0xF] << 20)                  \
    | (colors[(src[i] >> 24) & 0xF] << 24);                 \
glyphBuffer->pixelRows[i]     |= val << shiftAmount->left;  \
glyphBuffer->pixelRows[i + 8] |= val >> shiftAmount->right; \

static void ShiftGlyphTile_ShadowedFont_Width7(struct GlyphBuffer *glyphBuffer, u32 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u32 val;
    SHIFT_GLYPH_WIDTH7_STEP(0)
    SHIFT_GLYPH_WIDTH7_STEP(1)
    SHIFT_GLYPH_WIDTH7_STEP(2)
    SHIFT_GLYPH_WIDTH7_STEP(3)
    SHIFT_GLYPH_WIDTH7_STEP(4)
    SHIFT_GLYPH_WIDTH7_STEP(5)
    SHIFT_GLYPH_WIDTH7_STEP(6)
    SHIFT_GLYPH_WIDTH7_STEP(7)
}

#define SHIFT_GLYPH_WIDTH8_STEP(i)                          \
val = (colors[(src[i] >>  0) & 0xF] <<  0)                  \
    | (colors[(src[i] >>  4) & 0xF] <<  4)                  \
    | (colors[(src[i] >>  8) & 0xF] <<  8)                  \
    | (colors[(src[i] >> 12) & 0xF] << 12)                  \
    | (colors[(src[i] >> 16) & 0xF] << 16)                  \
    | (colors[(src[i] >> 20) & 0xF] << 20)                  \
    | (colors[(src[i] >> 24) & 0xF] << 24)                  \
    | (colors[(src[i] >> 28)      ] << 28);                 \
glyphBuffer->pixelRows[i]     |= val << shiftAmount->left;  \
glyphBuffer->pixelRows[i + 8] |= val >> shiftAmount->right; \

static void ShiftGlyphTile_ShadowedFont_Width8(struct GlyphBuffer *glyphBuffer, u32 *src, u32 *colors, u8 startPixel)
{
    const struct ShiftAmount *shiftAmount = &sGlyphShiftAmounts[startPixel];
    u32 val;
    SHIFT_GLYPH_WIDTH8_STEP(0)
    SHIFT_GLYPH_WIDTH8_STEP(1)
    SHIFT_GLYPH_WIDTH8_STEP(2)
    SHIFT_GLYPH_WIDTH8_STEP(3)
    SHIFT_GLYPH_WIDTH8_STEP(4)
    SHIFT_GLYPH_WIDTH8_STEP(5)
    SHIFT_GLYPH_WIDTH8_STEP(6)
    SHIFT_GLYPH_WIDTH8_STEP(7)
}


/* ---- colors LUT 构建（upstream text.c L2924-2950 等价形态）----
 * 官方规则：[i]=i 全直通，[0]=bg、[14]=shadow、[15]=fg 终端色覆盖；
 * 本工程终端色由 WIN_COLOR_C(fg)/D(bg)/E(shadow) 注入。 */
void refpr_colors_init(struct GlyphBuffer *gb, uint8_t fg, uint8_t shadow, uint8_t bg)
{
    u8 i;
    for (i = 0; i < 16u; i++)
        gb->colors[i] = i;
    gb->colors[0u]  = bg;
    gb->colors[14u] = shadow;
    gb->colors[15u] = fg;
}
