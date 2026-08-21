/* GetGlyphTilePointers_hook.c — Hook3：官方字库取址的 CHS 分支 + 分发器。
 *
 * 地址订钉：main.asm `.org GetGlyphTilePointers` 8B 桩 far-jump 到
 * text/entry.s 的 GetGlyphTilePointers_Hook（寄存器/栈约定在 .s）；
 * 本文件只写逻辑：
 *   - bit15=0 → bl 重定位副本 GetGlyphTilePointers_Orig（entry.s .incbin）
 *   - bit15=1 → CHS 解析（FontChsNormal 内 TL/BL、TR/BR 指针）
 */
#include "game.h"

/*
 * CHS 字模解析。伪 glyph 编码：bit15=右半(TR/BR)，bits0-14=gidx。
 * FontChsNormal 布局：TL@+0x00 BL@+0x20 TR@+0x40 BR@+0x60（32B/tile）。
 * 官方调用方字形均 ≤0xFF，bit15 门控零冲突（全 ROM 仅 FontFunc[1]/[2] 两调用方）。
 */
void GetGlyphTilePointers_CHS(uint32_t fontNum, uint32_t glyph,
                              uint8_t **upperTilePtr, uint8_t **lowerTilePtr)
{
    uint32_t gidx = glyph & CHS_GLYPH_IDX_MASK;
    uint8_t *base = (uint8_t *)(ADDR_FONT_CHS_NORMAL + (gidx << 7));

    (void)fontNum;
    if (glyph & CHS_GLYPH_HALF_BIT)
        base += 64u;
    *upperTilePtr = base;
    *lowerTilePtr = base + 32u;
}

/* 原函数重定位副本（text/entry.s，.incbin baserom 0x3730..0x382F）。 */
void GetGlyphTilePointers_Orig(uint32_t fontNum, uint32_t glyph,
                               uint8_t **upperTilePtr, uint8_t **lowerTilePtr);

/* C 分发器：entry.s GetGlyphTilePointers_Hook 调入。 */
void GetGlyphTilePointers_C(uint32_t fontNum, uint32_t glyph,
                            uint8_t **upperTilePtr, uint8_t **lowerTilePtr)
{
    if (glyph & CHS_GLYPH_HALF_BIT)
        GetGlyphTilePointers_CHS(fontNum, glyph, upperTilePtr, lowerTilePtr);
    else
        GetGlyphTilePointers_Orig(fontNum, glyph, upperTilePtr, lowerTilePtr);
}
