/* =====================================================================================
 * chinese_text.h — 中文内容解析（upstream 移植）
 *
 * upstream: rh-hideout-chinese/pokeemerald-expansion src/chinese_text.c
 * （保留 upstream 函数命名：DecompressGlyph_Chinese / GetChineseFontWidthFunc）
 *
 * 与 upstream 的差异（适配日版红宝石二进制 + 本工程 F9 协议）：
 *  - 不移植 IsChineseChar / IsChinesePunctuation：upstream 从文本流裸双字节码
 *    检测汉字；本工程由 F9 帧定界（F9 00 ll tt），状态机已隔离出汉字码，
 *    检测函数无消费方。
 *  - 字库源：upstream gFontNormalChineseGlyphs（.latfont 编译期符号）→
 *    本工程 ADDR_FONT_CHS_NORMAL / ADDR_FONT_CHS_SMALL（armips 侧载 ROM 区）。
 *    fontId 语义对齐：font4 → Small 8px 库，其余 → Normal 12px 库。
 *  - 字模格式：upstream 2bpp 四分块经 DecompressGlyphTile 展开；
 *    本工程字库即 4bpp tile 对（TL+0 / BL+32 / TR+64 / BR+96），直拷。
 * ===================================================================================== */
#ifndef CHINESE_TEXT_H
#define CHINESE_TEXT_H

#include "text.h"

/* 解压字模到 glyph（调用方栈上缓冲，见 text.h 存储说明）并设置
 * width/height（upstream 同名；upstream 写全局 gCurGlyph，本工程因
 * freestanding 无 .bss 改为显式传参，其余语义一致）。 */
void DecompressGlyph_Chinese(struct TextGlyph *glyph, uint16_t ChineseChar, uint8_t fontId);

/* 按字体类别返回字宽（upstream 同名；font4 小字 8px，其余 12px）。 */
uint8_t GetChineseFontWidthFunc(uint16_t ChineseChar, uint8_t fontId);

#endif /* CHINESE_TEXT_H */
