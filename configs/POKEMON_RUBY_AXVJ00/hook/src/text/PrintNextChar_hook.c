/* PrintNextChar_hook.c — F9 协议分流 + slot 查表 + 短语重定向。
 *
 * 地址订钉：main.asm `.org PrintNextChar_RegularGlyph` → entry.s PrintNextChar
 * （寄存器/lr 约定在 .s）。绘制委托给 DrawGlyph_CHS_hook.c /
 * DrawGlyphTiles_hook.c；字模取址委托给 GetGlyphTilePointers_hook.c。
 */
#include "game.h"

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
        if (stream[i] >= 0xFAu)
            return 0;
        i++;
    }
    return 1;
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
                PrintGlyph_CHS(win, gidx);
            i += 4;
        } else {
            if (!DrawGlyph_CHS(win, stream[i]))
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

/**
 * slot_lookup_and_draw — type=slot 运行时查表拦截。
 *
 * SlotTable v2 格式（'SLT2' magic，src/meowth/translated_slot.py 生成）：
 *   Header (.align 4):
 *     u32 magic = 0x32544C53 ('SLT2')
 *     u32 n_buckets(u16 LE) | max_jp_len(u16 LE)
 *     u32 bucket_offset[n_buckets+1]   （相对 SlotTable 标签的字节偏移）
 *   Entries 按 jp_bytes[0] 分桶组排放，桶内保持原表顺序：
 *     key(4B FNV1a(jp)) | jp_len_le16(2B) | jp_bytes | chinese_bytes(... 0xFF)
 *
 * 查找：cur_char 即桶号 → 只遍历所在桶（801 条/94 首字节/最大桶 43 条）；
 * 流窗口以 max_jp_len 封顶（v1 每字符扫到 0xFF 最多拷 255B 是卡顿主因之一）；
 * 拷贝窗口时增量算 FNV 前缀哈希 ph[len]，条目 key 与 ph[len] 直接比对，
 * 免去每条目的重复哈希；命中才逐字节核对（防哈希碰撞）。
 * 匹配语义与 v1 完全一致：jp[0]==cur_char 才可能命中，桶内先到先得。
 *
 * Legacy 平铺格式（key|len|jp|cn … 4x00 哨兵）在 magic 不匹配时走
 * slot_lookup_legacy 线性查找——行为与旧版逐字节一致，供回滚/旧表兼容。
 */
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

/* 命中后逐字节绘制中文 F9 流并推进 INDEX（legacy/v2 共用）。 */
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
                    PrintGlyph_CHS(win, gidx);
            }
            ci += 4;
        } else {
            DrawGlyph_CHS(win, chinese[ci]);
            ci++;
        }
    }
    win_set_u16(win, WIN_TEXT_INDEX, next_index);
    return 1;
}

/* v2 分桶查找。入口已保证 magic 匹配、cur_char<0x100。 */
#define SLOT_TABLE_MAGIC_V2   0x32544C53u  /* 'SLT2' */
#define SLOT_V2_MAX_WINDOW    32u         /* 窗口硬上限（表头 max_jp_len 再封顶） */

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
        return 0;                       /* 空桶：两次索引读即返回 */

    /* 单次有界扫描：拷贝窗口 + 增量 FNV 前缀哈希（ph[k]=fnv1a(前 k 字节)），
     * 条目 key 与 ph[len] 直接比对，替代逐条目重哈希。
     * 上限为编译期常量、cnt 用 unsigned，无回绕风险。 */
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
            if (match)
                return slot_draw_chinese(
                    win, table + i + 6u + len,
                    (uint16_t)(index - 1 + len));
        }
        i += 6u + len;
        while (i < end && table[i] != 0xFF)
            i++;
        i++;
    }
    return 0;
}

/* legacy 平铺表线性查找——与旧版 slot_lookup_and_draw 逐字节一致。 */
static int slot_lookup_legacy(TextPrinter *win, uint32_t cur_char,
                              const uint8_t *text, uint16_t index)
{
    const uint8_t *table = (const uint8_t *)ADDR_SLOT_TABLE;
    unsigned i = 0;
    uint8_t stream_buf[256];
    uint8_t stream_len = 0;
    unsigned k;

    /* 从当前字节开始读，遇到 0xFF 停止，不包含 0xFF。
     * cnt 必须是 int：uint8_t 对 sizeof(256) 比较恒真会被编译器删掉边界，
     * 流内 255 字节内无 0xFF 时 cnt 回绕 → 死循环（开场白逗号卡死根因）。 */
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

    /* 遍历 SlotTable：按 key 匹配，再逐字节核对 */
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
                if (match)
                    return slot_draw_chinese(
                        win, &table[i + entry_len],
                        (uint16_t)(index - 1 + entry_len));
            }
        }
        i += entry_len;
        while (table[i] != 0xFF)
            i++;
        i++;
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

    /* v2 分桶表（'SLT2'）：O(桶大小)；旧平铺表自动回退线性。 */
    if (slot_rd_le32(table) == SLOT_TABLE_MAGIC_V2)
        return slot_lookup_v2(win, cur_char, table, text, index);

    return slot_lookup_legacy(win, cur_char, text, index);
}

/**
 * PrintNextChar_C — F9 优先；可印 JP 必须走 CHS 同池（禁回 FontFunc 双路径）。
 */
int PrintNextChar_C(TextPrinter *win, uint32_t cur_char)
{
    /* 缓冲型打印机（血条 textMode2 / RenderTextHandleBold textMode1+font4）：
     * dest=win[0x20]，CHS 引擎不适用，整体交原版 FontFunc */
    if (scene_is_buffer_printer(win))
        return 0;

    if (cur_char == 0xEFu) {
        if (DrawMenuCursorEF(win))
            return 1;
        return 0;
    }

    /* ---- F9 协议优先 ---- */
    if (cur_char == CHS_ESCAPE) {
        const uint8_t *text =
            (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
        uint16_t index = win_u16(win, WIN_TEXT_INDEX);
        const uint8_t *p = text + index;
        uint8_t op = p[0];

        if (op == 0) {
            uint32_t tptr = win_u32(win, WIN_TEXT_PTR);
            if (index == 1
                && (tptr < ADDR_PHRASE_TABLE || tptr >= ADDR_FONT_CHS_NORMAL))
                chs_bind_pitch_slot(win, 0)->write_op = 0;
            {
                uint8_t lead = p[1];
                uint8_t trail = p[2];
                uint16_t gidx;
                if (!lead_trail_ok(lead, trail))
                    return 0;
                win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 3));
                gidx = pack_glyph_index(lead, trail);
                if (gidx >= CHS_FONT_GLYPH_MAX)
                    return 1;
                PrintGlyph_CHS(win, gidx);
                return 1;
            }
        }

        {
            volatile struct ChineseTileState *st = chs_bind_pitch_slot(win, 0);
            uint16_t code = (uint16_t)((p[1] << 8) | p[2]);
            int parent_cont = phrase_parent_continues(text, index);

            if (op == CHS_PHRASE_DEFAULT || parent_cont) {
                st->write_op = 0;
            } else {
                st->write_op = op;
            }

            if (parent_cont && inline_phrase_no_controls(win, index, code))
                return 1;

            redirect_phrase_stream(win, code);
            return 1;
        }
    }

    /* ---- type=slot: JP hex → 中文替换查找表 ---- */
    if (slot_lookup_and_draw(win, cur_char))
        return 1;

    /* ---- 普通 JP PCS：同套 CHS 绘制 ---- */
    return DrawGlyph_CHS(win, cur_char);
}
