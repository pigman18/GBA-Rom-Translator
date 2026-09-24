/* =============================================================================
 * chs_render.c — v1 8px 汉字渲染层（Middle 档 · 零分配器，2026-09-22）
 *
 * 用户拍板：「先做一版最简洁的 8px 字体显示」。
 * 本文件的全部机制只有一句话：
 *
 *      **一个汉字 = 池里连续两个 4bpp 砖；砖号由「字 → 槽」粘性查表给定。**
 *
 * ── 为什么是这个形状（反汇编 + 实机 dump 实证，逐条可核）───────────────
 * 1. 引擎自己画字的落砖规则是**纯函数零状态**：
 *      FontSubTable[0/3/7] @0x08003584（8 条指令，逐指令核过）——
 *        r2 = glyph*2 + win[0x16](TILE_BASE)  → upper
 *        r2 += 0x10000 → 截断 u16            → lower（与 upper 同号）
 *        bl 0x080036DC  = UpdateTilemap(win, upper, lower)
 *      InitWindowTileData @0x08002A50 的 font0/3 分支同源：
 *        dest = tpl[+0x0C] + TILE_BASE*32 + glyph*64  ⇒ **每字两个砖**。
 *      ⇒ 「字 c → 砖对 (TILE_BASE+2c, TILE_BASE+2c+1)」，不需要任何分配器、
 *        不需要任何复位信号，所以原版日文重画/光标乱移永远不跳字。
 * 2. 汉字字集 7168 个 ⇒ 纯函数要 14336 砖 > VRAM 1024 砖 ⇒ 必须复用
 *    ⇒ 需要「字 → 槽」映射。**这就是分配器存在的唯一理由**，而只要映射是
 *    **粘性**的，重画就自动等于原地覆写，幂等性免费获得。
 *    （v8~v38 的失败不在"有映射"，而在"映射会变"：段表/相位/避让带全都在
 *      每帧重新决定砖号，于是 map 还指着的砖被搬走 ⇒ 疯狂跳字。）
 * 3. 字模：4bpp Middle 库 @ADDR_FONT_CHS_MIDDLE，128B/字 = 4 个 8x8 砖
 *    [TL][BL][TR][BR]。全 3000 字采样：nibble 只有 {0,15}、墨迹只在列 0..7、
 *    行 2..12、TR/BR 恒零 ⇒ 上砖=src[0:32)（行 0..7）、下砖=src[32:64)（行 8..15），
 *    **一次 64B 直拷，零位流重排、零缩放、零相位**。
 * 4. 池几何：窗口九宫格 = 512..520；引擎字形缓存实测用到 503/504；
 *    全部 40+ 份实机 dump 里 map 引用号 ≥521 的一个都没有
 *    （即 bg charBase 块之外无人引用）⇒ 池 = **[521, 1024)**。
 * 5. 颜色：4bpp BG 的 palette index 0 = 透明，而字模的底色正好是 0
 *    ⇒ 必须换成窗口自己的底色，否则字被挖空。字模只有 {0,15} 两值，
 *    映射 15 → win[WIN_COLOR_C]（墨）、0 → win[WIN_COLOR_D]（底）。
 *    ⚠ 若实机看整字变实心方块/底色不对，就是 C/D 语义反了，改这两行即可。
 *
 * ── 容量与回收策略（「宁缺不砸」）─────────────────────────────────
 * 池 503 砖 ⇒ 224 槽（521 + 224*2 = 969，剩 969..1023 留白作安全边际）。
 *   · 表未满：新字直接追加 ⇒ 绝不覆盖任何 map 还指着的砖。
 *   · 表已满且**屏签名未变**（同一窗口模板 + 同一 charBase）⇒ 拒绝发号，
 *     不写 map，但照常推进游标（字消失、行不错位）。>224 个不同字的屏会退化，
 *     但**已画对的字永远不会被改坏**。
 *   · 表已满且**屏签名变了**（= 换了窗口/换了层）⇒ 整表换代重来，
 *     新屏从槽 0 重新发号。换代那一帧可能花一下（老屏残留砖被覆写），
 *     下一帧全部命中即稳定。
 * 屏签名只看 (窗口模板指针, charBase)：**不看 text 指针**——短语重定向
 * （redirect_phrase_stream）会在窗口原串与短语流之间来回切 text 指针，
 * 若把 text 指针算进签名就会每帧换代。
 * ============================================================================= */
#include "text.h"

/* ---- 池几何 ------------------------------------------------------------ */
#define V1_POOL_BASE    521u    /* 首个池砖号（窗口九宫格 512..520 之上） */
#define V1_SLOT_CAP     224u    /* 521 + 224*2 = 969 ≤ 1024 */
#define V1_MEDIA_BYTES  128u    /* 4bpp Middle：1 字 = 128B 容器 */
#define V1_PAIR_BYTES   64u     /* 真正用到的上/下两砖 = 64B */

/* ---- 状态区（全 ROM 无字面量引用、多屏 dump 连续零；见 game_addrs.asm）---- */
#define V1_KEYS   ((uint16_t *)(uintptr_t)ADDR_V1_KEY_TAB)  /* u16[224] 字键 */
#define V1_N      (*(uint16_t *)(uintptr_t)ADDR_V1_SLOT_N)  /* 已发号个数 */
#define V1_MAG    (*(uint16_t *)(uintptr_t)ADDR_V1_MAGIC)   /* 初始化魔法 */
#define V1_SIGTPL (*(uint32_t *)(uintptr_t)ADDR_V1_SIG_TPL) /* 屏签名：模板指针 */
#define V1_SIGCB  (*(uint8_t *)(uintptr_t)ADDR_V1_SIG_CB)   /* 屏签名：charBase */

#define V1_MAGIC_TAG    0x5631u  /* 'V1' */

/* 键空位哨兵：合法 key 的最大值 < 0xFFFF（汉字键 §see below 最高 0x7BFF）。 */
#define V1_KEY_NONE     0xFFFFu

/* 汉字键：gid 13 bit（<7168）+ charBase 2 bit + 字库 1 bit
 * ⇒ 让「不同层」和「不同字号档」的同 gid 互不串用。
 * 日文（DrawGlyph）不经这张表：它交引擎自己的 tm1 处理器落砖，走引擎坐标系。 */
#define V1_KEY_SMALL_BIT 0x8000u   /* bit15 空闲（gid ≤ 13 bit、cb ≤ bit14） */
#define V1_KEY_CHS(gid, cb, small) \
    ((uint16_t)((gid) | ((uint16_t)(cb) << 13) \
                | ((small) ? V1_KEY_SMALL_BIT : 0u)))

#define V1_VRAM_LO  0x06000000u
#define V1_VRAM_HI  0x06018000u

/* =========================================================================
 * 取窗口所在层的字模基址
 *   引擎 InitWindowTileData 的用法就是 `ldr r0,[tpl,#12]`（0x08002A8E）。
 *   charBase 由基址反推（基址 >>14 & 3），比读 tpl[+1] 更贴底——
 *   我们真正要写的就是这个地址，键也用它来区分层。
 * ========================================================================= */
static uint32_t v1_base(TextPrinter *win, uint8_t *cb_out)
{
    uint8_t *tpl = win_template(win);
    uint32_t base = win_u32(tpl, TPL_TILE_DATA);

    if (base < V1_VRAM_LO || base >= V1_VRAM_HI)
        base = V1_VRAM_LO | ((uint32_t)win_u8(tpl, TPL_CHARBASE) << 14u);

    *cb_out = (uint8_t)((base >> 14u) & 3u);
    return base;
}

/* =========================================================================
 * 「字 → 槽」粘性发号
 *   返回槽号(0..223)；返回 V1_KEY_NONE 表示**拒绝发号**（同屏超容量），
 *   调用方必须仍然推进游标，只是不写 map。
 * ========================================================================= */
static uint16_t v1_slot(uint16_t key, uint32_t sig_tpl, uint8_t sig_cb)
{
    uint16_t n, i;

    if (V1_MAG != V1_MAGIC_TAG) {         /* EWRAM 上电是随机值，首用必须清零 */
        V1_MAG = V1_MAGIC_TAG;
        V1_N = 0;
    }

    n = V1_N;
    for (i = 0; i < n; i++)
        if (V1_KEYS[i] == key)
            return i;                     /* 命中：同字同槽 ⇒ 重画=原地覆写 */

    if (n >= V1_SLOT_CAP) {               /* 满了：只有"换屏"才允许回收 */
        if (V1_SIGTPL != sig_tpl || V1_SIGCB != sig_cb) {
            n = 0;
        } else {
            return V1_KEY_NONE;
        }
    }

    V1_KEYS[n] = key;
    V1_N = (uint16_t)(n + 1u);
    V1_SIGTPL = sig_tpl;
    V1_SIGCB = sig_cb;
    return n;
}

/* 4bpp 字节 → 上屏字节。字模只有 nibble 0 / 15 两个值，故"非零即墨"。 */
static uint8_t v1_remap_byte(uint8_t b, uint8_t ink, uint8_t bg)
{
    uint8_t hi = (uint8_t)(b >> 4);
    uint8_t lo = (uint8_t)(b & 0x0Fu);

    return (uint8_t)(((hi ? ink : bg) << 4) | (lo ? ink : bg));
}

/* =========================================================================
 * 落一对砖 + 写 map + 推进一格
 *   src64 = 上砖 32B 紧接 下砖 32B。
 *   remap=1：字模是 {0,15} 裸值，须做值→色映射（汉字库）。
 *   remap=0：引擎自己的字体砖里已经是窗口调色板索引，原样搬。
 * ========================================================================= */
static void v1_put_pair(TextPrinter *win, uint32_t base, uint16_t key,
                        const uint8_t *src64, int remap,
                        uint32_t sig_tpl, uint8_t sig_cb)
{
    uint16_t slot = v1_slot(key, sig_tpl, sig_cb);

    if (slot != V1_KEY_NONE) {
        uint16_t top = (uint16_t)(V1_POOL_BASE + (uint32_t)slot * 2u);
        uint8_t *dst = (uint8_t *)(uintptr_t)(base + (uint32_t)top * 32u);

        if (remap) {
            uint8_t ink = win_u8(win, WIN_COLOR_C);
            uint8_t bg = win_u8(win, WIN_COLOR_D);
            unsigned i;

            for (i = 0; i < V1_PAIR_BYTES; i++)
                dst[i] = v1_remap_byte(src64[i], ink, bg);
        } else {
            copy_tile32(dst, src64);
            copy_tile32(dst + 32, src64 + 32);
        }

        /* 原生 UpdateTilemap：写当前格 + 下一 map 行（+32 格），
         * 自带 win[0x0F]<<12 的调色板位，不动任何游标。 */
        UpdateTilemap_PreserveCursorX(win, top, (uint16_t)(top + 1u));
    }

    /* 无论画没画成，格位一律推进 1（= 8px = 一个 map 格）——
     * 与引擎 tm1/tm2/tm3 处理器的 cursorTileX+=1 同语义。 */
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
}

/* =========================================================================
 * 字库分档（字号）
 *   引擎的 tm1 分派器 0x0800360C 逐指令：`ldrb r0,[r4,#11]`（= win[0x0B]）
 *   → `FontSubTable[fontNum]` ⇒ **字号由 win[0x0B] 决定，不是 win[0x0A]**
 *   （0x0A 是 textMode，喂 FontFuncTable）。
 *   ⇒ 必须按 win[0x0B] 选档，否则「大字号窗口」会被画成小字号（或反之），
 *     字宽/字高与窗口排版不匹配 ⇒ 溢出压到相邻行/UI 上。
 *   用户拍板（2026-09-22）：**fontNum == 4 一律走 Small 档**（队伍页宝可梦名）。
 *   两档都是同一套 128B 容器（[TL][BL][TR][BR]，墨迹只在列 0..7），
 *   行偏移已烘进字库本身（Middle 墨迹行 2..12 / Small 墨迹行 5..13），
 *   所以换档只换地址，**不动 64B 直拷的几何、不动步进（恒 8px/格）**。
 * ========================================================================= */
static const uint8_t *v1_pick_lib(TextPrinter *win)
{
    if (win_u8(win, WIN_FONTNUM_REAL) == 4u)
        return (const uint8_t *)(uintptr_t)ADDR_FONT_CHS_SMALL;
    return (const uint8_t *)(uintptr_t)ADDR_FONT_CHS_MIDDLE;
}

/* =========================================================================
 * 对外入口 1：F9 00 汉字
 *   code = pack_glyph_index(lead, trail)（< CHS_FONT_GLYPH_MAX）。
 *   索引正确性已实测：大=467 / 日=2389 / 口=1512 全部渲染正确。
 * ========================================================================= */
void chs_print(TextPrinter *win, uint32_t code, uint8_t fontSize)
{
    uint32_t gid = code & 0x1FFFu;
    uint8_t cb;
    uint32_t base;
    const uint8_t *lib;
    int small;

    (void)fontSize;                 /* 档位由 win[0x0B] 定；步进恒 8px/格 */
    if (gid >= CHS_FONT_GLYPH_MAX)
        return;

    base = v1_base(win, &cb);
    lib = v1_pick_lib(win);
    small = (lib != (const uint8_t *)(uintptr_t)ADDR_FONT_CHS_MIDDLE);
    v1_put_pair(win, base, V1_KEY_CHS(gid, cb, small),
                lib + gid * V1_MEDIA_BYTES,
                1, (uint32_t)(uintptr_t)win_template(win), cb);
}

/* =========================================================================
 * 对外入口 2：PCS 单字节（日文兜底）
 *   只在 F9 短语流 / slot 替换流内部出现（本串里的日文由 PrintNextChar_Hook
 *   退回原生，根本不进这里）。
 *   走引擎自己的 tm1 处理器 0x0800360C（逐指令核过）：
 *       r2 = FontSubTable[win[0x0B]]        ; 0x081BB3BC
 *       CallViaR2(r2)(win, glyph)           ; → 写 (TILE_BASE+2g, +1) 的 map 对
 *       win[0x1B] += 1                      ; **无条件**推进一格（对所有 font 档）
 *   ⇒ 步进语义与 chs_print 完全一致（都是 +1 格 = 8px），不需要任何补齐。
 *   砖数据由引擎预取（InitWindowTileData）提供。
 *   ⚠ 预取只覆盖窗口自己的串；若该日文字不在窗口原串里，砖内容可能是旧的
 *     —— 本版已知限制，但**不覆盖 VRAM、不砸别的字**。
 * ========================================================================= */
int DrawGlyph(TextPrinter *win, uint32_t cur_char)
{
    PrintGlyph_TextMode1_Origin(win, cur_char & 0xFFu);
    return 1;
}

/* =========================================================================
 * 对外入口 3：1bpp 位流 → 128B 4bpp 字形单元
 *   text_translater.c 的 GetGlyph（三个 1bpp 档）需要它才能链接；v1 的
 *   chs_print 走 4bpp 直拷，**不经过这里**（保留是为了 1bpp 档将来能直接复用）。
 *   语义：位流每行 width 位 MSB-first 连续排布、共 rows 行，从 line_off 行起落位；
 *   墨迹=15、空=0。单元布局与 4bpp 库一致：[0:32)TL [32:64)BL [64:96)TR [96:128)BR。
 * ========================================================================= */
void chs_cell_from_1bpp(const uint8_t *bits, uint32_t width, uint32_t rows,
                        uint32_t line_off, uint8_t cell[CHS_CELL_BYTES])
{
    uint32_t y, x, bit = 0;

    for (y = 0; y < CHS_CELL_BYTES; y++)
        cell[y] = 0;

    for (y = 0; y < rows; y++) {
        uint32_t r = y + line_off;
        uint32_t base;

        if (r >= 16u)
            break;
        base = ((r < 8u) ? 0u : 32u) + (r & 7u) * 4u;   /* 上半→TL，下半→BL */

        for (x = 0; x < width; x++, bit++) {
            if (!((bits[bit >> 3] >> (7u - (bit & 7u))) & 1u))
                continue;
            if (x < 8u)
                cell[base + (x >> 1)] |=
                    (uint8_t)((x & 1u) ? 0xF0u : 0x0Fu);
        }
    }
}
