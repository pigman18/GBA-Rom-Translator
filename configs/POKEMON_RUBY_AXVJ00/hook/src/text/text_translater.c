/* =====================================================================================
 * text_translate.c — 翻译链路（F9 协议层）
 *
 * 职责：文本流中翻译标记的解释与分派，不含任何渲染实现。
 *   F9 00 ll tt        单汉字 → pack_glyph_index → PrintGlyph（引擎渲染件）
 *   F9 <op> hi lo      短语引用 → PhraseTable（内联绘制或切流）
 *   PCS 单字节          → SLT2 slot 表匹配 → 替换流绘制
 *   宽度工具            → phrase_width_px / GetStringWidth（F9 感知流遍历）
 *
 * 与引擎的边界：只经 include/text.h 的 PrintGlyph / DrawGlyph 触达渲染，
 * 只经 game.h 的 win_* 访问器触达窗口状态——引擎内部（渲染行/分配）对本文件不可见，
 * 便于引擎侧重构与 upstream 对照更新互不影响。
 *
 * 来源：原 src/text.c §2/§12/§13/§16 原样迁出（除 pitch 槽 write_op 记账随
 * 槽位机制一并移除）。协议常量 CHS_ESCAPE/CHS_PHRASE_DEFAULT/ADDR_* 见 game.h。
 * ===================================================================================== */
#include "text.h"
#include "text_render.h"

/* =====================================================================
 * §glyph — 字形源统一解析（自 text_render.c 迁入）
 * ===================================================================== */
int GetGlyph(TextPrinter *win, uint32_t code, uint8_t *out128, uint8_t *outWidth)
{
    uint8_t fontNum = win_u8(win, WIN_FONTNUM_REAL);
    if (fontNum > 6u)
        fontNum = 3u;

    if (code == 0) {
        unsigned i;
        for (i = 0; i < 128u; i++)
            out128[i] = 0;
        *outWidth = 8u;
        return 1;
    }

    if (code >= SYM_GLYPH_BASE && code < SYM_GLYPH_BASE + SYM_GLYPH_COUNT) {
        const uint8_t *src = (const uint8_t *)(ADDR_FONT_CHS_SYM
                                               + (code - SYM_GLYPH_BASE) * 64u);
        unsigned i;
        for (i = 0; i < 32u; i++) {
            out128[0x00 + i] = src[i];
            out128[0x20 + i] = src[32u + i];
        }
        for (i = 0; i < 64u; i++)
            out128[0x40 + i] = 0;
        *outWidth = 8u;
        return 1;
    }

    {
        uint8_t *upper = 0;
        uint8_t *lower = 0;

        if (code >= 0xF7)
            return 0;
        GetGlyphTilePointers_Origin(fontNum, (uint16_t)code, &upper, &lower);
        if (!upper || !lower)
            return 0;

        for (unsigned i = 0; i < 64u; i++)
            out128[0x40 + i] = 0;
        if (FontIsShadowed(fontNum)) {
            copy_tile32(out128 + 0x00, upper);
            copy_tile32(out128 + 0x20, lower);
        } else {
            CopyGlyph1bppTo4bpp_Origin(upper, (uint32_t *)(uintptr_t)(out128 + 0x00), 0xFu, 0x0u);
            CopyGlyph1bppTo4bpp_Origin(lower, (uint32_t *)(uintptr_t)(out128 + 0x20), 0xFu, 0x0u);
        }
        *outWidth = 8u;
        return 1;
    }
}

/* =====================================================================
 * §T1 协议原语（原 text.c §2）
 * ===================================================================== */
static int lead_trail_ok(uint8_t lead, uint8_t trail)
{
    if (lead >= 0xFA || trail >= 0xFA)
        return 0;
    if (lead < 0x01 || lead > 0x1E)
        return 0;
    if (lead == 0x06 || lead == 0x1B)
        return 0;
    return 1;
}

static uint16_t pack_glyph_index(uint8_t lead, uint8_t trail)
{
    uint32_t idx = lead;
    if (idx >= 6) {
        if (idx >= 0x1B)
            idx -= 1;
        idx -= 1;
    }
    idx -= 1;
    return (uint16_t)((idx << 8) | trail);
}

/* =====================================================================
 * §T2 PhraseTable（原 text.c §12）
 * layout: PhraseOffsets[code] (u32 @ADDR_PHRASE_OFFSETS, sentinel≥0x01000000)
 *         → PhraseTable + off (PCS 流 @ADDR_PHRASE_TABLE, 终止 0xFF)
 * ===================================================================== */
static const uint8_t *phrase_stream_lookup(uint16_t code)
{
    const uint32_t *offsets = (const uint32_t *)ADDR_PHRASE_OFFSETS;
    const uint8_t *table = (const uint8_t *)ADDR_PHRASE_TABLE;
    uint32_t off = offsets[code];

    if (off >= 0x01000000u)
        return 0;
    return table + off;
}

static int phrase_stream_no_wait_controls(const uint8_t *stream)
{
    unsigned i = 0;

    if (!stream)
        return 0;
    while (stream[i] != 0xFF) {
        if (stream[i] == CHS_ESCAPE) {
            if (stream[i + 1] != 0)
                return 0;
            i += 4;
            if (i > 256u)
                return 0;
            continue;
        }
        if (stream[i] == 0xFD) {
            /* FD nn：占位符，可由 fd_expand_print 调官方展开对内联打印 */
            i += 2;
            if (i > 256u)
                return 0;
            continue;
        }
        if (stream[i] >= 0xFAu)
            return 0;
        i++;
    }
    return 1;
}

/* ---- FD 占位符：官方展开对（ADDR_FD_RESOLVER + ADDR_FD_SUBPRINT）--------
 * 快径循环（0x08002DE8）state7 的官方实现就是：
 *   index += 1; SUBPRINT(win, RESOLVER(text[旧 index]))。
 * RESOLVER 查 0x081BBAC8 函数表返回变量串指针；SUBPRINT 换 text/index 跑
 * 快径循环把串打完（缓冲内容里的 F9 80 嵌套引用会再次进我们的重定向，
 * 道具名等因此显示中文）再恢复 text/index/state。
 * ⚠ 打印器的 state7（0x08002F78）只是"跳过 id"的残迹；预处理循环
 *   （0x08002E54）没有 s7 分支——FD 在那条路上会漏成 id 字节被当字形
 *   （PCS 0x01=あ / 0x03=う，2026-08-29 拾道具对话实证）。 */
typedef uint32_t (*fn_fd_resolver)(uint32_t id);
typedef void (*fn_fd_subprint)(TextPrinter *win, uint32_t str);

static void fd_expand_print(TextPrinter *win, uint8_t id)
{
    uint32_t str = ((fn_fd_resolver)(ADDR_FD_RESOLVER | 1u))((uint32_t)id);

    ((fn_fd_subprint)(ADDR_FD_SUBPRINT | 1u))(win, str);
}

static int phrase_parent_continues(const uint8_t *text, uint16_t index)
{
    return text[index + 3] != 0xFF;
}

static int inline_phrase_no_controls(TextPrinter *win, uint16_t index, uint16_t code)
{
    const uint8_t *stream = phrase_stream_lookup(code);
    unsigned i = 0;
    unsigned n = 0;

    if (!stream || !phrase_stream_no_wait_controls(stream))
        return 0;

    while (stream[i] != 0xFF) {
        if (stream[i] == CHS_ESCAPE && stream[i + 1] == 0) {
            uint8_t lead = stream[i + 2];
            uint8_t trail = stream[i + 3];
            uint16_t gidx;
            if (!lead_trail_ok(lead, trail))
                return 0;
            gidx = pack_glyph_index(lead, trail);
            if (gidx < CHS_FONT_GLYPH_MAX)
                PrintGlyph(win, gidx, CHS_GLYPH_ADVANCE_PX);
            i += 4;
        } else if (stream[i] == 0xFD) {
            fd_expand_print(win, stream[i + 1]);
            i += 2;
        } else {
            if (!DrawGlyph(win, stream[i]))
                return 0;
            i++;
        }
        if (++n > 32u)
            break;
    }
    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 3));
    return 1;
}

static void redirect_phrase_stream(TextPrinter *win, uint16_t code)
{
    const uint8_t *stream = phrase_stream_lookup(code);

    if (!stream)
        return;
    win_set_u32(win, WIN_TEXT_PTR, (uint32_t)(uintptr_t)stream);
    win_set_u16(win, WIN_TEXT_INDEX, 0);
}

/* =====================================================================
 * §T3 SlotTable 查找族（原 text.c §13；'SLT2' 分桶 / legacy 平铺）
 * ===================================================================== */
static uint32_t fnv1a_hash(const uint8_t *data, unsigned len)
{
    uint32_t h = 0x811c9dc5u;
    unsigned i;
    for (i = 0; i < len; i++) {
        h ^= data[i];
        h *= 0x01000193u;
    }
    return h;
}

static uint32_t slot_rd_le32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static int slot_draw_chinese(TextPrinter *win, const uint8_t *chinese,
                             uint16_t next_index)
{
    unsigned ci = 0;

    while (chinese[ci] != 0xFF) {
        if (chinese[ci] == CHS_ESCAPE && chinese[ci + 1] == 0) {
            uint8_t lead = chinese[ci + 2];
            uint8_t trail = chinese[ci + 3];
            uint16_t gidx;
            if (lead_trail_ok(lead, trail)) {
                gidx = pack_glyph_index(lead, trail);
                if (gidx < CHS_FONT_GLYPH_MAX)
                    PrintGlyph(win, gidx, CHS_GLYPH_ADVANCE_PX);
            }
            ci += 4;
        } else if (chinese[ci] == 0xFD) {
            fd_expand_print(win, chinese[ci + 1]);
            ci += 2;
        } else {
            DrawGlyph(win, chinese[ci]);
            ci++;
        }
    }
    win_set_u16(win, WIN_TEXT_INDEX, next_index);
    return 1;
}

#define SLOT_TABLE_MAGIC_V2   0x32544C53u  /* 'SLT2' */
#define SLOT_V2_MAX_WINDOW    32u

static int slot_lookup_v2(TextPrinter *win, uint32_t cur_char,
                          const uint8_t *table,
                          const uint8_t *text, uint16_t index)
{
    uint16_t n_buckets = (uint16_t)(table[4] | (table[5] << 8));
    uint16_t max_jp = (uint16_t)(table[6] | (table[7] << 8));
    const uint8_t *offs;
    uint32_t beg, end, i;
    uint8_t stream_buf[SLOT_V2_MAX_WINDOW];
    uint32_t ph[SLOT_V2_MAX_WINDOW + 1];
    unsigned cap;
    unsigned cnt = 0;

    if (n_buckets == 0 || cur_char >= n_buckets || max_jp == 0)
        return 0;
    if (max_jp > SLOT_V2_MAX_WINDOW)
        max_jp = SLOT_V2_MAX_WINDOW;

    offs = table + 8;
    beg = slot_rd_le32(offs + (uint32_t)cur_char * 4u);
    end = slot_rd_le32(offs + (uint32_t)cur_char * 4u + 4u);
    if (beg >= end)
        return 0;

    ph[0] = 0x811c9dc5u;
    {
        int pos = (int)index - 1;
        cap = max_jp;
        while (cnt < cap) {
            uint8_t b = (cnt == 0) ? (uint8_t)cur_char : text[pos + cnt];
            if (b == 0xFF)
                break;
            stream_buf[cnt] = b;
            ph[cnt + 1] = (ph[cnt] ^ b) * 0x01000193u;
            cnt++;
        }
    }
    if (cnt == 0)
        return 0;

    {
        uint16_t best_len = 0;
        const uint8_t *best_cn = 0;
        uint16_t best_next = 0;

        for (i = beg; i < end;) {
            uint16_t len = (uint16_t)(table[i + 4] | (table[i + 5] << 8));
            if (len >= 1u && len <= cnt && slot_rd_le32(table + i) == ph[len]) {
                unsigned k, match = 1;
                for (k = 0; k < len; k++) {
                    if (table[i + 6 + k] != stream_buf[k]) {
                        match = 0;
                        break;
                    }
                }
                if (match && len >= best_len) {
                    best_len = len;
                    best_cn = table + i + 6u + len;
                    best_next = (uint16_t)(index - 1 + len);
                }
            }
            i += 6u + len;
            while (i < end && table[i] != 0xFF)
                i++;
            i++;
        }
        if (best_len > 0)
            return slot_draw_chinese(win, best_cn, best_next);
    }
    return 0;
}

static int slot_lookup_legacy(TextPrinter *win, uint32_t cur_char,
                              const uint8_t *text, uint16_t index)
{
    const uint8_t *table = (const uint8_t *)ADDR_SLOT_TABLE;
    unsigned i = 0;
    uint8_t stream_buf[256];
    uint8_t stream_len = 0;
    unsigned k;

    /* cnt 必须 int：uint8_t 对 sizeof 比较恒真会被编译器删边界 → 回绕死循环 */
    {
        int pos = (int)index - 1;
        int cnt = 0;
        while (cnt < (int)sizeof(stream_buf)) {
            uint8_t b = (cnt == 0) ? (uint8_t)cur_char : text[pos + cnt];
            if (b == 0xFF)
                break;
            stream_buf[cnt] = b;
            cnt++;
        }
        if (cnt > 255)
            cnt = 255;
        stream_len = (uint8_t)cnt;
    }

    if (stream_len == 0)
        return 0;

    {
        uint16_t best_len = 0;
        const uint8_t *best_cn = 0;
        uint16_t best_next = 0;

        while (table[i] != 0 || table[i + 1] != 0 || table[i + 2] != 0 || table[i + 3] != 0) {
            uint32_t entry_key;
            uint16_t entry_len;
            entry_key = (uint32_t)table[i] | ((uint32_t)table[i + 1] << 8)
                      | ((uint32_t)table[i + 2] << 16) | ((uint32_t)table[i + 3] << 24);
            i += 4;
            entry_len = (uint16_t)table[i] | ((uint16_t)table[i + 1] << 8);
            i += 2;

            if (entry_len > 0 && entry_len <= stream_len) {
                uint32_t h = fnv1a_hash(stream_buf, entry_len);
                if (h == entry_key) {
                    unsigned match = 1;
                    for (k = 0; k < entry_len; k++) {
                        if (table[i + k] != stream_buf[k]) {
                            match = 0;
                            break;
                        }
                    }
                    if (match && entry_len >= best_len) {
                        best_len = entry_len;
                        best_cn = &table[i + entry_len];
                        best_next = (uint16_t)(index - 1 + entry_len);
                    }
                }
            }
            i += entry_len;
            while (table[i] != 0xFF)
                i++;
            i++;
        }
        if (best_len > 0)
            return slot_draw_chinese(win, best_cn, best_next);
    }
    return 0;
}

static int slot_lookup_and_draw(TextPrinter *win, uint32_t cur_char)
{
    const uint8_t *table = (const uint8_t *)ADDR_SLOT_TABLE;
    const uint8_t *text =
        (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    uint16_t index = win_u16(win, WIN_TEXT_INDEX);

    if (cur_char >= 0x100u)
        return 0;

    if (slot_rd_le32(table) == SLOT_TABLE_MAGIC_V2)
        return slot_lookup_v2(win, cur_char, table, text, index);

    return slot_lookup_legacy(win, cur_char, text, index);
}

/* =====================================================================
 * §T4 翻译层单字符入口（原 text.c §15 PrintNextChar_Hook 的
 * F9 分支 + slot 分支；F9 短语 op → pitch 槽 write_op（scene_mode2_apply 消费）
 * ===================================================================== */
int TranslateHandleChar(TextPrinter *win, uint32_t c)
{
    const uint8_t *text;
    uint16_t idx2;
    const uint8_t *p;
    uint8_t op;

    if (c != CHS_ESCAPE)
        return slot_lookup_and_draw(win, c);

    text = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    idx2 = win_u16(win, WIN_TEXT_INDEX);
    p = text + idx2;
    op = p[0];

    if (op == 0) {
        uint8_t lead = p[1];
        uint8_t trail = p[2];
        uint16_t gidx;
        /* 旧 chs_pitch_set_write_op 已随 pitch 分配器移除（落址回归原生协议） */
        (void)win_u32(win, WIN_TEXT_PTR);

        if (!lead_trail_ok(lead, trail)) {
            win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx2 + 3));
            return 1;
        }
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx2 + 3));
        gidx = pack_glyph_index(lead, trail);
        if (gidx < CHS_FONT_GLYPH_MAX)
            PrintGlyph(win, gidx, CHS_GLYPH_ADVANCE_PX);
        return 1;
    }

    {
        uint16_t code = (uint16_t)((p[1] << 8) | p[2]);
        int parent_cont = phrase_parent_continues(text, idx2);

        (void)op;                       /* 旧 pitch write_op 随分配器一并移除 */

        if (parent_cont && inline_phrase_no_controls(win, idx2, code))
            return 1;

        redirect_phrase_stream(win, code);
        return 1;
    }
}

/* =====================================================================
 * §T5 流像素宽度（原 text.c §16；GetStringWidth 为导出工具，
 * 消费方 src/map_name_popup/MapNamePopup_hook.c）
 * ===================================================================== */
static uint32_t phrase_width_px(const uint8_t *stream)
{
    uint32_t w = 0;
    uint32_t i = 0;

    if (!stream)
        return CHS_GLYPH_ADVANCE_PX;

    while (i < 256u && stream[i] != 0xFF) {
        uint8_t b = stream[i];
        if (b == CHS_ESCAPE) {
            if (stream[i + 1] == 0)
                w += CHS_GLYPH_ADVANCE_PX;
            i += 4;
            continue;
        }
        if (b >= PCS_CTRL_BASE) {
            i += 1;
            continue;
        }
        w += CHS_GLYPH_ADVANCE_JP_PX;
        i += 1;
    }
    return w;
}

uint32_t GetStringWidth(const uint8_t *buf, uint32_t max_bytes)
{
    uint32_t w = 0;
    uint32_t len = 0;
    const uint32_t *offsets = (const uint32_t *)ADDR_PHRASE_OFFSETS;

    while (len < max_bytes && buf[len] != 0xFF) {
        if (buf[len] == CHS_ESCAPE && len + 3 < max_bytes) {
            uint8_t op = buf[len + 1];
            uint16_t code = (uint16_t)((buf[len + 2] << 8) | buf[len + 3]);
            if (op == 0) {
                w += CHS_GLYPH_ADVANCE_PX;
            } else if (code < 0x2000u) {
                uint32_t off = offsets[code];
                w += (off < 0x01000000u)
                         ? phrase_width_px((const uint8_t *)ADDR_PHRASE_TABLE + off)
                         : CHS_GLYPH_ADVANCE_PX;
            } else {
                w += CHS_GLYPH_ADVANCE_PX;
            }
            len += 4;
        } else if (buf[len] >= PCS_CTRL_BASE) {
            len += 1;
        } else {
            w += CHS_GLYPH_ADVANCE_JP_PX;
            len += 1;
        }
    }
    return w;
}
