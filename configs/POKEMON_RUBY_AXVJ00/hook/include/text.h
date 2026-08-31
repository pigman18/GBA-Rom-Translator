/* =====================================================================================
 * text.h — 文本引擎公共类型与跨模块 API（include/src 布局）
 *
 * 结构仿 pokeemerald text.h（upstream: rh-hideout-chinese/pokeemerald-expansion）：
 *   struct TextGlyph / gCurGlyph —— 引擎级字形缓冲（DecompressGlyph_Chinese 填充，
 *   渲染行读取），与 upstream 同名字段对齐，便于后续 upstream 更新对照。
 *
 * 模块划分（解耦，用途见各文件头）：
 *   src/text.c           引擎：状态机 / 取字 / 渲染行 / PCS 分发（本文件 API 提供方）
 *   src/chinese_text.c   中文内容解析（upstream 移植）：字模解压 + 宽度
 *   src/text_translate.c 翻译链路：F9 协议（F900 汉字 / F980 短语 / SLT2 slot）
 * ===================================================================================== */
#ifndef TEXT_H
#define TEXT_H

#include "game.h"

/* ---- upstream struct TextGlyph（pokeemerald text.h 同构）----
 * gfxBufferTop = 上半行两 tile（TL | TR），gfxBufferBottom = 下半行（BL | BR），
 * 各 16×u32 = 2×32B tile。width/height 由 DecompressGlyph_Chinese 设置。
 *
 * ⚠️ 存储位置（2026-08-25 定案）：upstream 的 gCurGlyph 是链接器分配的全局；
 * 本工程 game.bin 为 freestanding 平坦镜像（link/game.ld 无 RAM 段），全局
 * 变量会落 ROM（0x088xxxxx）→ 写入被硬件丢弃（首版五图全花根因，game.map
 * gCurGlyph=0x08801a34 实证）。故字形缓冲改为**打印机栈上局部变量**，由
 * 调用方（PrintGlyph）显式传入 DecompressGlyph_Chinese——与旧引擎栈上
 * buf[128] 同款，为全工程唯一被长期验证的可写暂存。 */
struct TextGlyph {
    uint32_t gfxBufferTop[16];
    uint32_t gfxBufferBottom[16];
    uint8_t width;
    uint8_t height;
};

/* ---- 字形取字（text_translater.c 提供，PrintNextChar 消费）---- */
int GetGlyph(TextPrinter *win, uint32_t code, uint8_t *out128, uint8_t *outWidth);

/* ---- 引擎渲染件（PrintNextChar_hook.c 提供，text_translate.c 消费）---- */

/* F9 00 汉字渲染：gidx = pack_glyph_index(lead, trail)，宽度随 fontNum
 * （font4 → FontChsSmall 8px，其余 → FontChsNormal 12px）。 */
void PrintGlyph(TextPrinter *win, uint32_t gidx, unsigned glyphWidth);

/* PCS 单字节（半角）统一渲染入口。
 *   SYM 标点带（0x36-0x3E，tm0/tm3）→ 中文标点字库相位感知自绘；
 *   其余半角（tm0/tm3）→ 先把相位补齐到列首，再交原生（防覆盖前字尾 +
 *   防 4px 空洞）；tm1/tm2 无像素路径 → 返回 0 交调用方原生分发。
 * 返回 1=已消费；0=未消费。fontfunc thunk 在原生分发**之前**调用它。 */
int DrawHalfWidth(TextPrinter *win, uint32_t cur_char);

/* PCS 单字节渲染入口（text_translater.c 的 slot/phrase 替换流内消费）。
 * 恒返回 1=已消费（引擎零回落：不可印位直接吞掉）。 */
int DrawGlyph(TextPrinter *win, uint32_t cur_char);

/* 原生 FontFunc 处理器分发（fontfunc_hook.c 提供）。
 * 直调 Origin 地址常量（防经 FontFuncTable 递归）；textMode 4-7 静默消费。
 * thunk（FontFuncTm*_Hook）与 DrawGlyph 共用。 */
void FontFunc_NativeDispatch(uint8_t tm, TextPrinter *win, uint32_t c);

/* ---- 翻译链路（src/text_translate.c 提供，text.c 状态机消费）---- */

/* 翻译层单字符入口：
 *   CHS_ESCAPE (0xF9) → 读 op 分派：op==0 单汉字（PrintGlyph）；
 *     op==0x80/其他 短语（PhraseTable 内联或切流）
 *   其余 PCS 字节     → SLT2 slot 表匹配 → 替换流绘制
 * 返回 1=已消费；0=交还引擎原生渲染（DrawGlyph）。 */
int TranslateHandleChar(TextPrinter *win, uint32_t c);

#endif /* TEXT_H */
