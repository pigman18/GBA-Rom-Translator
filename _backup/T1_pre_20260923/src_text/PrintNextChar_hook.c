/* =====================================================================================
 * PrintNextChar_hook.c — 渲染落点（翻译通路消费端）
 *
 * 统一模型（2026-09-04）：
 *   1) 非 FA..FF → TranslateHandleChar / DrawGlyph（翻译通路）
 *   2) resolve(tm, fn, 场景表) → 档位：tm2/fn4/req8 → 小库；场景表 → Middle/小库；
 *      否则 → 大库（11×11 步进 12）
 *   3) 取字 → g128 → chs_emit：按 tm 落点
 *        tm2     写 win[0x20] 缓冲，列步进 +0x40（官方血条再 CpuSet→OBJ）
 *        tm0     官方线性 TILE_BASE+TILE_OFFSET + UTM（不同 BASE 区互不冲 VRAM）
 *        tm1     v8_alloc + UTM，并 TILE_OFFSET += adv*2
 *        tm3     v8_alloc + UTM，不推 TILE_OFFSET（网格只推 cursorTileX）
 *   tm1 是分配器的主因（预渲染窗无自写 VRAM）；tm3 中文叠字领号避 atlas。
 *   tm0 不走 v8_alloc：战斗四格(BASE≈0x90)与「怎么办」(BASE≈0x190) 同 tpl/同 cb，
 *   若共用 0x100 起领号，后一次 Init 会盖掉前一次 VRAM。
 * ===================================================================================== */
#include "text.h"
#include "blend_glyph.h"
#include "tile_alloc.h"
#include "scene_cfg.h"

/* ---- resolve：tm + fn + 场景表 + 请求步进 → 步进/墨宽/字形源 ----
 * 档位解析优先级（高 → 低）：
 *   ① tm2（血条缓冲直绘）/ fn4 / 请求 8px  → 1bpp 小库 9×9，步进 10、墨宽 9；
 *   ② 场景字号表（scene_cfg.c，键 tpl+win，curX 分区）：
 *        V6_FONT_PX_MIDDLE → 1bpp Middle 9×11，步进 10、墨宽 9（窄身全高，如领航员）
 *        V6_FONT_PX_SMALL  → 1bpp 小库 9×9，步进 10、墨宽 9
 *   ③ 默认 → 1bpp 大库 11×11，步进 12、墨宽 11。
 * 场景表**不覆盖** ①（血条/强制小字体是硬约束）。
 * 历史：2026-09-08「两档制 2.0」曾把场景表整体退役；2026-09-11 重建为档位选择器。 */
static void resolve_draw(TextPrinter *win, uint8_t req_px, uint8_t *tm_out,
                         uint8_t *fn_out, uint8_t *adv_out, uint8_t *ink_out,
                         uint8_t *lib_out)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
    uint8_t fn = win_u8(win, WIN_FONTNUM_REAL);
    uint8_t scene_px;

    if (fn > 6u)
        fn = 3u;
    *tm_out = tm;

    *fn_out = (tm == 2u) ? 4u : fn;
    if (tm == 2u || fn == 4u || req_px == 8u) {
        *adv_out = CHS_GLYPH_ADVANCE_SMALL_PX;
        *ink_out = CHS_GLYPH_INK_SMALL_PX;
        *lib_out = CHS_FONT_LIB_1BPP_SMALL;
        return;
    }

    /* 场景字号表：tpl 取 win[0x00] 模板指针，win 取打印器自身地址，
     * 分区键取 WIN_CURSOR_X（整个字符串的起始列，按串恒定）。 */
    scene_px = v6_scene_font(win_u32(win, WIN_TEMPLATE),
                             (uint32_t)(uintptr_t)win,
                             win_u8(win, WIN_CURSOR_X));

    if (scene_px == V6_FONT_PX_MIDDLE) {
        *adv_out = CHS_GLYPH_ADVANCE_SMALL_PX;
        *ink_out = CHS_GLYPH_INK_SMALL_PX;
        *lib_out = CHS_FONT_LIB_MIDDLE;
        return;
    }
    if (scene_px == V6_FONT_PX_SMALL) {
        *adv_out = CHS_GLYPH_ADVANCE_SMALL_PX;
        *ink_out = CHS_GLYPH_INK_SMALL_PX;
        *lib_out = CHS_FONT_LIB_1BPP_SMALL;
        return;
    }

    /* R1-A 宽度单源：值唯一定义在 game.h 宽度单源块 */
    *adv_out = CHS_GLYPH_ADVANCE_PX;
    *ink_out = CHS_GLYPH_INK_PX;
    *lib_out = CHS_FONT_LIB_1BPP_BIG;
}

/* tm3 官方网格（0x080034E0 反汇编钉死）：
 * tile = TILE_BASE + left(0x1A) + 2 + cursorTileX(0x1B)
 *        + (cursorY(0x1C) + cursorTileY(0x1D)) * 30。
 * 数据直接写在 tilemap 引用的格子上（窗口自有 stride-30 网格区）。
 * 下行 tile = +30（下一 tilemap 行）。 */
static uint16_t chs_tm3_grid_tile(TextPrinter *win)
{
    return (uint16_t)(win_u16(win, WIN_TILE_BASE)
                      + win_u8(win, WIN_CURSOR_X)
                      + 2u + win_u8(win, WIN_CURSOR_TILE_X)
                      + (uint16_t)((win_u8(win, WIN_CURSOR_Y)
                                    + win_u8(win, WIN_CURSOR_TILE_Y)) * 30u));
}

/* 本 tm 的「下半 tile」偏移：tm3 网格 = +30（下一行），其余竖直对 = +1 */
static uint16_t chs_lower_delta(uint8_t tm)
{
    return (tm == 3u) ? 30u : 1u;
}

/* tm0：跟官方线性寻址；tm3：官方网格（窗口自有区）；其余（tm1 共享图集）
 * 走 v8 动态分配（AXVJ tm1 无窗口私有区，反汇编定论 2026-09-08） */
static uint16_t chs_claim_tile(TextPrinter *win, uint8_t tm, uint8_t font_px,
                               uint8_t glyph_len)
{
    if (tm == 0u)
        return (uint16_t)(win_u16(win, WIN_TILE_BASE)
                          + win_u16(win, WIN_TILE_OFFSET));
    if (tm == 3u)
        return chs_tm3_grid_tile(win);
    return v8_alloc_tile(win, font_px, glyph_len);
}

static void fill_colors(TextPrinter *win, uint8_t colors[16])
{
    uint8_t fg_ov = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    uint8_t color_c = fg_ov ? fg_ov : win_u8(win, WIN_COLOR_C);
    uint8_t color_d = win_u8(win, WIN_COLOR_D);
    uint8_t color_e = win_u8(win, WIN_COLOR_E);
    unsigned i;

    for (i = 0; i < 16u; i++)
        colors[i] = color_d;
    colors[14] = color_e;
    colors[15] = color_c;
}

static void chs_fill_bg(TextPrinter *win, uint8_t tm, uint16_t tile,
                        unsigned x0, unsigned x1)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
    uint8_t colors[16];
    uint8_t zero[32];
    uint16_t dlow = chs_lower_delta(tm);
    unsigned i;

    if (x1 <= x0 || x0 > 7u)
        return;
    if (x1 > 8u)
        x1 = 8u;
    if (!tpl)
        return;
    tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!tile_data)
        return;
    fill_colors(win, colors);
    for (i = 0; i < 32u; i++)
        zero[i] = 0u;
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)tile << 5)),
                           0, zero, x1 - x0, x0, colors);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(tile + dlow) << 5)),
                           0, zero, x1 - x0, x0, colors);
}

/* 12px/11px 两段式 + 相位共享；ink=墨宽、advance=步进（11×11 库：11/12）。
 * 返回游标推进列数 adv = (phase + advance) >> 3 */
static unsigned print_glyph_px(TextPrinter *win,
                               const uint8_t g128[CHS_CELL_BYTES],
                               unsigned ink, unsigned advance)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
    uint8_t colors[16];
    uint8_t up[32], lo[32];
    unsigned px, phase, w0, w1, adv;
    uint16_t t0, t1, dlow;
    uint8_t tx0, tm;

    px = v8_phase_get(win);
    phase = px & 7u;
    w0 = (8u - phase < ink) ? (8u - phase) : ink;
    w1 = ink - w0;
    adv = (phase + advance) >> 3;
    dlow = chs_lower_delta(win_u8(win, WIN_TEXTMODE) & 7u);
    tx0 = win_u8(win, WIN_CURSOR_TILE_X);
    tm = win_u8(win, WIN_TEXTMODE) & 7u;
    if (adv < 1u)
        adv = 1u;
    if (!tpl)
        return adv;
    tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!tile_data)
        return adv;

    fill_colors(win, colors);

    if (phase == 0u || tm == 0u || tm == 3u) {
        /* 字形 = 竖直对（t0=上半 8 行、t0+1=下半 8 行），8px/12px 均占 2 tile。
         * 此处不得省成 1：t0+1 未占位会被后续领号回收踩踏。
         * R1-A（2026-09-23）零状态化：phase0 = 领新列；tm0（BASE+OFFSET 线性）
         * / tm3（网格 f(cursorTileX)）在 phase!=0 时，领号公式与上一字尾列
         * **逐位同式**（此时 Δ列=1 恒成立，见 tile_alloc.h 推导）⇒ 直接由
         * 公式复原，不再读任何存储状态。 */
        t0 = chs_claim_tile(win, tm, advance, 2u);
        if (t0 == 0u)
            return adv;
    } else {
        /* tm1 共享图集：行尾列由队列游标纯算推导（tail = CURSOR - 2）。
         * 推导不可用（队列换主 / 本会话尚无领号）⇒ **退回领新对**。
         * **绝不**让 t0 保持 0：tile 0 = charBase 首格，写它是不可逆的破坏
         * （像素进官方格 + 表项指向 tile 0）。 */
        t0 = v8_phase_last_tile(win);
        if (t0 == 0u) {
            t0 = chs_claim_tile(win, tm, advance, 2u);
            if (t0 == 0u)
                return adv;
        }
    }
    /* tm0 线性：下一列 = t0+2；tm3 网格：下一列 = t0+1；v8 则再 alloc 一对 */
    if (w1 != 0u) {
        if (tm == 0u)
            t1 = (uint16_t)(t0 + 2u);
        else if (tm == 3u)
            t1 = (uint16_t)(t0 + 1u);
        else {
            t1 = chs_claim_tile(win, tm, advance, 2u);
            if (t1 == 0u) {
                /* 尾列领不到（v8 队列耗尽）⇒ **放弃右半**，绝不退化成写 tile 0。
                 * tile 0 = charBase 首格（图集/空白槽）：写它一箭双雕地坏 ——
                 *   ① 该字的右半像素落进官方格 ⇒ 破坏别人的字形；
                 *   ② 紧接着 UpdateTilemap 把 **tile 0** 写进本格表项 ⇒ 该格
                 *      显示成空白/官方首格内容。
                 * 实机表现就是「字只剩半个」。宁缺不砸：本字只留左半。 */
                w1 = 0u;
            }
        }
    } else {
        t1 = 0u;
    }

    extract_cols(g128, 0u, w0, up, lo);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)t0 << 5)),
                           0, up, w0, phase, colors);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(t0 + dlow) << 5)),
                           0, lo, w0, phase, colors);

    if (w1 != 0u) {
        extract_cols(g128, w0, w1, up, lo);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)t1 << 5)),
                               0, up, w1, 0u, colors);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(t1 + dlow) << 5)),
                               0, lo, w1, 0u, colors);
        chs_fill_bg(win, tm, t1, w1, 8u);
    }

    UpdateTilemap_PreserveCursorX(win, t0, (uint16_t)(t0 + dlow));
    if (w1 != 0u) {
        win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(tx0 + 1u));
        UpdateTilemap_PreserveCursorX(win, t1, (uint16_t)(t1 + dlow));
    }
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(tx0 + adv));

    v8_phase_advance((uint16_t)advance);
    return adv;
}

/* tm2 血条：win[0x20] 线性缓冲直绘（无分配器/无 tilemap，列槽=0x40=上/下半
 * 两 tile）。9×9 字体（步进 10、墨 9）相位两段式：本列 phase..phase+w0，
 * 尾列 0..w1 并把 w1..8 清底；每字推进 adv 列（dst += adv*0x40）。
 * 相位用全局 v8_phase（InitTextPrinter 会话边界复位，血条名是独立会话）。 */
static unsigned tm2_print_px(TextPrinter *win,
                             const uint8_t g128[CHS_CELL_BYTES],
                             unsigned ink, unsigned advance)
{
    uint8_t colors[16];
    uint8_t up[32], lo[32], zero[32];
    uint32_t dst, dnext;
    unsigned px, phase, w0, w1, adv, i;

    dst = win_u32(win, WIN_TILE_DATA);
    if (dst == 0u)
        return 1u;

    px = v8_phase_get(win);
    phase = px & 7u;
    w0 = (8u - phase < ink) ? (8u - phase) : ink;
    w1 = ink - w0;
    adv = (phase + advance) >> 3;
    if (adv < 1u)
        adv = 1u;

    fill_colors(win, colors);
    for (i = 0; i < 32u; i++)
        zero[i] = 0u;

    extract_cols(g128, 0u, w0, up, lo);
    (void)blend_glyph_4bpp((uint32_t *)(void *)dst, 0, up, w0, phase, colors);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(dst + 0x20u), 0, lo, w0, phase,
                           colors);

    dnext = dst + 0x40u;
    if (w1 != 0u) {
        extract_cols(g128, w0, w1, up, lo);
        (void)blend_glyph_4bpp((uint32_t *)(void *)dnext, 0, up, w1, 0u, colors);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(dnext + 0x20u), 0, lo, w1,
                               0u, colors);
        if (w1 < 8u) {
            (void)blend_glyph_4bpp((uint32_t *)(void *)dnext, 0, zero,
                                   8u - w1, w1, colors);
            (void)blend_glyph_4bpp((uint32_t *)(void *)(dnext + 0x20u), 0,
                                   zero, 8u - w1, w1, colors);
        }
    } else if (phase + w0 < 8u) {
        /* 墨未跨列且本列未写满（8px 标点等）：右侧清底防残留 */
        (void)blend_glyph_4bpp((uint32_t *)(void *)dst, 0, zero,
                               8u - (phase + w0), phase + w0, colors);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(dst + 0x20u), 0, zero,
                               8u - (phase + w0), phase + w0, colors);
    }

    win_set_u32(win, WIN_TILE_DATA, dst + (uint32_t)adv * 0x40u);
    v8_phase_advance((uint16_t)advance);
    return adv;
}

/* ---- 唯一落点：按 tm 写目标；返回推进列数（供 TILE_OFFSET）----
 * advance=本字步进像素（12/10），ink=墨宽（11/9），二者分离（11×11 库
 * 墨 11 步进 12、9×9 库墨 9 步进 10，pokeE 语义）。
 * 旧 8px/16px 光栅路径已删（2026-09-08 两档制 2.0；advance 恒为
 * 12/10/8，全走相位两段式 print_glyph_px）。 */
static unsigned chs_emit(TextPrinter *win, uint8_t tm, unsigned advance,
                         const uint8_t g128[CHS_CELL_BYTES], unsigned ink)
{
    unsigned adv;

    if (ink == 0u)
        ink = advance;

    if (tm == 2u)
        return tm2_print_px(win, g128, ink, advance);

    adv = print_glyph_px(win, g128, ink, advance);
    if (tm == 0u || tm == 1u)
        win_set_u16(win, WIN_TILE_OFFSET,
                    (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + adv * 2u));
    return adv;
}

static void jp_glyph_to_g128(uint8_t font_num, uint16_t glyph,
                             uint8_t g128[CHS_CELL_BYTES])
{
    uint8_t *up, *lo;
    unsigned i;

    GetGlyphTilePointers_Origin(font_num, glyph, &up, &lo);
    for (i = 0; i < CHS_CELL_BYTES; i++)
        g128[i] = 0u;
    if (FontIsShadowed(font_num)) {
        copy_tile32(g128 + 0x00u, up);
        copy_tile32(g128 + 0x20u, lo);
    } else {
        CopyGlyph1bppTo4bpp_Origin(up, g128 + 0x00u, 15u, 0u);
        CopyGlyph1bppTo4bpp_Origin(lo, g128 + 0x20u, 15u, 0u);
    }
}

void chs_print(TextPrinter *win, uint32_t code, uint8_t fontSize)
{
    uint8_t tm, fn, adv, ink, lib;
    uint8_t g128[CHS_CELL_BYTES];
    uint8_t w = 0;
    uint8_t saved_fn;

    /* fontSize=请求步进（翻译层按 tm 传 chs_print_px 档位） */
    resolve_draw(win, fontSize, &tm, &fn, &adv, &ink, &lib);

    saved_fn = win_u8(win, WIN_FONTNUM_REAL);
    win_set_u8(win, WIN_FONTNUM_REAL, fn);
    if (!GetGlyph(win, code, g128, &w, lib)) {
        win_set_u8(win, WIN_FONTNUM_REAL, saved_fn);
        return;
    }
    win_set_u8(win, WIN_FONTNUM_REAL, saved_fn);
    (void)chs_emit(win, tm, adv, g128, ink);
}

int DrawHalfWidth(TextPrinter *win, uint32_t cur_char)
{
    uint8_t tm, fn, adv, ink, lib;
    uint8_t g128[CHS_CELL_BYTES];
    unsigned i;

    if (cur_char < SYM_GLYPH_BASE
        || cur_char >= SYM_GLYPH_BASE + SYM_GLYPH_COUNT)
        return 0;

    resolve_draw(win, 0u, &tm, &fn, &adv, &ink, &lib);
    (void)fn;
    (void)adv;
    (void)ink;
    (void)lib;

    {
        const uint8_t *sym =
            (const uint8_t *)ADDR_FONT_CHS_SYM
            + (cur_char - SYM_GLYPH_BASE) * 64u;
        for (i = 0; i < CHS_CELL_BYTES; i++)
            g128[i] = 0u;
        for (i = 0; i < 32u; i++) {
            g128[0x00 + i] = sym[i];
            g128[0x20 + i] = sym[32u + i];
        }
    }
    (void)chs_emit(win, tm, CHS_GLYPH_ADVANCE_JP_PX, g128,
                   CHS_GLYPH_ADVANCE_JP_PX);
    return 1;
}

int DrawGlyph(TextPrinter *win, uint32_t cur_char)
{
    uint8_t tm, fn, adv, ink, lib;
    uint8_t g128[CHS_CELL_BYTES];

    if (cur_char >= 0xF7u)
        return 1;
    if (DrawHalfWidth(win, cur_char))
        return 1;

    resolve_draw(win, 0u, &tm, &fn, &adv, &ink, &lib);
    (void)adv;
    (void)ink;
    (void)lib;
    jp_glyph_to_g128(fn, (uint16_t)cur_char, g128);
    /* 半角 JP：墨宽 8、步进 8（相位恒 0）—— 值取宽度单源 */
    (void)chs_emit(win, tm, CHS_GLYPH_ADVANCE_JP_PX, g128,
                   CHS_GLYPH_ADVANCE_JP_PX);
    return 1;
}

int PrintNextChar_Hook(TextPrinter *win)
{
    const uint8_t *text;
    uint16_t idx;
    uint8_t c;

    if (!win)
        return 0;

    text = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    idx = win_u16(win, WIN_TEXT_INDEX);
    c = text[idx];

    /* FA..FF：Origin 尾调用进 ROM，返回后本函数后续语句不会执行 */
    if (c >= 0xFAu) {
        /* ① 等 A 箭头（FA=\l 滚动 / FB=\p 清屏）：把落列推到 ceil(px/8)，
         * 别让它压掉本行末字的**尾列**。
         *   · 引擎 DrawInitialDownArrow@0x08003F4C → 箭图形 blit 到固定 tile
         *     (TILE_BASE+0xFE) → UpdateTilemap(win, t, t+1)：**表项格由
         *     [WIN_CURSOR_TILE_X] 决定**（0x08003EA4..EAE 实证）。
         *   · 我们 12px 步进 = 1.5 列 ⇒ 行末常停在半列（px & 7 != 0）。此时
         *     CURSOR_TILE_X = floor(px/8) 恰好 = 行末字的**尾列**（12px 两段式
         *     里相邻字共享尾列）⇒ 箭头表项一盖，行末字只剩左半 = 实机「半个字」。
         *   · 文档 docs/FONT_12PX_DRAW.md：「同句 \p → TILE_X = base_tx +
         *     ceil(chs_px/8)（勿减 CURSOR_X）」= 半列时推一列到 ceil。
         *   ⚠ 推完**不还原**：闪烁箭头每帧按 CURSOR_TILE_X 重画，还原会再压回去。
         *   ⚠ 行内 px == 0（`\n{\p}` 空行）不动 —— 保持 FE 光标，避免双▼。 */
        if (c == 0xFAu || c == 0xFBu) {
            uint16_t px = v8_phase_get(win);

            if ((px & 7u) != 0u) {
                win_set_u8(win, WIN_CURSOR_TILE_X,
                           (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
                /* tm0 线性：箭头**图形**落在 TILE_BASE+TILE_OFFSET 那个 tile
                 * 上（0x08003DF0 分支）——行末同样停在尾列，一并推一列。 */
                if ((win_u8(win, WIN_TEXTMODE) & 7u) == 0u)
                    win_set_u16(win, WIN_TILE_OFFSET,
                                (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + 2u));
            }
        }
        /* ② 换行类控制码 → 显式复位行相位：FE(\n 换行) / FB(\l 滚动) / FA(\p 清屏)。
         * R1-A（2026-09-23）：行指纹已退役，本处 + InitTextPrinter 块边界是
         * 相位归零的**全部**归零点（v8_phase_get 不再做行标识推断）。
         * 漏检后果（历史实机 BUG，勿删本段的理由）：新行首字带走上一行累计
         * 相位 —— 累计 = 12n mod 8，**n 为奇数时 = 4** ⇒ 走 phase!=0 分支
         * 复用行尾字的尾列 tile ⇒ 覆写行尾字右半 ⇒ 实机「奇数个字的一行，
         * 换行后行尾只剩半个字」。 */
        if (c == 0xFAu || c == 0xFBu || c == 0xFEu)
            v8_phase_reset();
        return PrintNextChar_Origin(win);
    }

    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx + 1u));

    if (*(volatile uint8_t *)ADDR_V6_BYPASS != 0u)
        return 1;

    if (TranslateHandleChar(win, c))
        return 1;
    DrawGlyph(win, c);
    return 1;
}
