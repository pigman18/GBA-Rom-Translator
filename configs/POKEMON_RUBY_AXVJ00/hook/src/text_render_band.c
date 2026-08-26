/* =====================================================================================
 * text_render_band.c — scratch 共享带渲染（现行 B3 引擎移植，纯搬移）
 *
 * 来源：text.c §2b/§6b/§6c/§7/§9（2026-08-26 回滚后的 B3 基线）。
 * 策略：像素写共享 scratch 带（cb 分区常数），PhaseBind 行相位 + 扫描定隙/
 * 盲顺序/带尾回卷/in_place；表项经 sWriteGlyphTilemapFuncs 门控（fn3/fn4）。
 * 对照组：与 render_inplace12（bak 原生寻址）经 RENDER_SEL_ADDR 切换对比。
 * ===================================================================================== */
#include "game.h"
#include "text_render.h"

#define PCS_MENU_CURSOR      0xEFu

/* =====================================================================
 * 行相位表（0x0203FF80-FFCF 安全区；反汇编定案：原生引擎不维护
 * 像素相位——tm1 writer 只推 win[0x1B]，win[0x1A] 是窗口属性位域非游标）
 * ===================================================================== */
static uint16_t PhaseKey(TextPrinter *win)
{
    /* 行指纹：换行/换流自动换 key = 相位自动归零。勿折入 CURSOR_X
     * （原生每字推进，非行标识）与 TextPrinter*（栈上回收，中流抖动）。 */
    uint8_t *tpl = win_template(win);
    uint16_t w = tpl ? (uint16_t)(((uintptr_t)tpl >> 2) & 0xFFFFu) : 0;
    uint16_t stream = (uint16_t)((win_u32(win, WIN_TEXT_PTR) >> 2) & 0xFFFFu);
    return (uint16_t)(win_u16(win, WIN_TILE_BASE)
                      ^ ((uint16_t)win_u8(win, WIN_CURSOR_Y) << 8)
                      ^ (uint16_t)win_u8(win, WIN_CURSOR_TILE_Y)
                      ^ w
                      ^ stream);
}

static volatile struct ChsPhase *PhaseBind(TextPrinter *win, int *out_is_new)
{
    volatile struct ChsPhase *tab =
        (volatile struct ChsPhase *)ADDR_CHS_PITCH_SLOTS;
    volatile uint8_t *gen = (volatile uint8_t *)ADDR_CHS_PITCH_CTRL;
    volatile uint8_t *age = (volatile uint8_t *)(ADDR_CHS_PITCH_CTRL + 1u);
    uint16_t key = PhaseKey(win);
    uint8_t cur_tx = win_u8(win, WIN_CURSOR_TILE_X);
    unsigned i;
    unsigned best;
    uint8_t best_age;
    uint8_t g;

    if (out_is_new)
        *out_is_new = 0;

    for (i = 0; i < CHS_PHASE_COUNT; i++) {
        if (tab[i].key == key) {
            /* 失配检测：win[0x1B]（下一绘制格）≠ tx0+(px>>3) 且 > 之
             * ⇒ 中间插了原生字形（(1,4) 路径，整格步进）→ 相位归零、
             * 行锚前移到当前格（原生 8px 整格后相位恒 0，衔接无缝）；
             * ≤ 之 ⇒ 重印/换行残留 → 同样归零重锚。
             * out_is_new 语义（B3）：0=同行续接；1=新槽；2=同键重锚
             * （=同内容重绘信号，分配器据此原地复用本流带首）。 */
            uint8_t want = (uint8_t)(tab[i].tx0 + (tab[i].px >> 3));
            if (cur_tx != want) {
                tab[i].px = 0;
                tab[i].tx0 = cur_tx;
                if (cur_tx > want && out_is_new)
                    *out_is_new = 0;   /* 原生插字：同行续接，非新行 */
                else if (out_is_new)
                    *out_is_new = 2;   /* 重印/回退：同键重锚 */
            }
            g = (uint8_t)(*gen + 1u);
            *gen = g;
            age[i] = g;
            return &tab[i];
        }
    }

    /* 旧槽位版 LRU 语义（逐值等价）：优先 age==0 空闲槽；无空槽才驱逐
     * 最老。禁止 gen%8 轮转——会在有空槽时偷走活跃行的相位（继续画面
     * 单字空洞根因）。 */
    best = 0;
    best_age = 255;
    for (i = 0; i < CHS_PHASE_COUNT; i++) {
        if (age[i] == 0) {
            best = i;
            break;
        }
        if (age[i] < best_age) {
            best_age = age[i];
            best = i;
        }
    }
    g = (uint8_t)(*gen + 1u);
    *gen = g;
    age[best] = g;
    tab[best].key = key;
    tab[best].px = 0;
    tab[best].tx0 = cur_tx;
    tab[best].adv12 = 1;
    tab[best].scr_org = 0;
    tab[best].scr_next = 0;
    if (out_is_new)
        *out_is_new = 1;
    return &tab[best];
}

/* =====================================================================
 * tm0 Linear 核心（TILE_OFF 连续光栅；floor=4；无 UI 重映射——
 * tm0 场景（对话 0x90 起/详情页 0x290 起）实测不与保留带重叠）
 * ===================================================================== */
static uint16_t GetCursorTileNum(
    TextPrinter *win, unsigned xOffset, unsigned yOffset)
{
    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    return (uint16_t)(tile_base + off + 2u * xOffset + yOffset);
}

/* pokeruby WriteGlyphTilemap：cursor 格落一对表项（upperTileNum/lowerTileNum）；
 * tx 为行相位折算的 tile 列（行相位表承载；win[0x1B] 仅作镜像同步）。 */
static void WriteGlyphTilemap(TextPrinter *win, uint8_t tx, uint16_t upperTileNum,
                              uint16_t lowerTileNum)
{
    win_set_u8(win, WIN_CURSOR_TILE_X, tx);
    UpdateTilemap_Origin(win, upperTileNum, lowerTileNum);
}

/* 相位推进 + cursorTileX 同步。
 * win[0x1B] 语义 = 「下一绘制格」= tx0+(px>>3)：原生 writer（(1,4) 路径，
 * 表项写 win[0x1B] 后 +1）接续混排时恰好无缝衔接；纯 CHS 流内下一字形
 * map_tx 同式，PhaseBind 期望值同式，三方一致。 */
static void ChsAdvanceCursor(volatile struct ChsPhase *st, TextPrinter *win,
                             unsigned glyphWidth)
{
    st->px = (uint16_t)(st->px + glyphWidth);
    st->adv12 = (uint8_t)(glyphWidth == 12u);
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(st->tx0 + (st->px >> 3)));
}

static void band_tm0(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned linear,
    unsigned glyphWidth)
{
    (void)linear;    /* tm0 恒 Linear（网格语义归 tm1/tm3 共用行） */
    volatile struct ChsPhase *st;
    unsigned startPixel;
    unsigned w2;
    uint16_t off, up0, lo0;
    uint8_t map_tx;
    struct GlyphTileInfo info;

    if (glyphWidth < 8u)
        glyphWidth = 8u;
    if (glyphWidth > 12u)
        glyphWidth = 12u;

    st = PhaseBind(win, 0);

    /* bak ensure_linear_dest_floor 基础下限：tm0 空白 tile = TILE_BASE+0，
     * OFF<4 时首字形会踩掉空白对（之后清屏/翻页把碎片当背景铺出）。 */
    {
        uint16_t off0 = win_u16(win, WIN_TILE_OFFSET);
        if (off0 < 4u)
            win_set_u16(win, WIN_TILE_OFFSET, 4u);
    }

    if (st->px == 0)
        st->tx0 = win_u8(win, WIN_CURSOR_TILE_X);

    startPixel = (unsigned)(st->px & 7u);
    map_tx = (uint8_t)(st->tx0 + (st->px >> 3));

    info.textMode = 0;
    info.colors = 0;

    /* ---- 第一趟：宽 8（TL/BL，startPixel>0 时 spill 到右邻） ---- */
    off = win_u16(win, WIN_TILE_OFFSET);
    up0 = GetCursorTileNum(win, 0, 0);
    lo0 = GetCursorTileNum(win, 0, 1);
    info.startPixel = (uint8_t)startPixel;
    info.width = 8;
    info.src = tiles->tl;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, up0);
    if (startPixel > 0u)
        draw_tile(win, &info, (uint8_t *)(uintptr_t)vram_tile(win, up0 + 2));
    else
        draw_tile(win, &info, 0);
    info.src = tiles->bl;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, lo0);
    if (startPixel > 0u)
        draw_tile(win, &info, (uint8_t *)(uintptr_t)vram_tile(win, lo0 + 2));
    else
        draw_tile(win, &info, 0);
    WriteGlyphTilemap(win, map_tx, up0, lo0);
    win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));

    w2 = (glyphWidth > 8u) ? (glyphWidth - 8u) : 0u;
    if (w2 == 0u) {
        ChsAdvanceCursor(st, win, glyphWidth);
        return;
    }

    /* px 不在此推进（ChsAdvanceCursor 统一 +w）；pass2 列 = 起始列+1：
     * 12px 字形跨 2 列，pass2 落 tx0+((px+8)>>3)。双重推进（+8 再 +12）
     * 会使 px 每字 +20 → px>>3 整列数每字多 1 → pass2 表项右移一列
     * （2026-08-25 gdb 日志定案：px 序列 0/20/40/60，半字根因）。 */
    map_tx = (uint8_t)(st->tx0 + ((st->px + 8u) >> 3));
    off = win_u16(win, WIN_TILE_OFFSET);
    up0 = GetCursorTileNum(win, 0, 0);
    lo0 = GetCursorTileNum(win, 0, 1);
    info.width = (uint8_t)w2;
    info.src = tiles->tr;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, up0);
    draw_tile(win, &info, 0);
    info.src = tiles->br;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, lo0);
    draw_tile(win, &info, 0);
    WriteGlyphTilemap(win, map_tx, up0, lo0);
    /* bak 同款：相位 0 时第二趟落在第一趟推进后的列内（下一字形从同列
     * 相位 4 续接，不再推进）；相位 >0 时第二趟耗尽当前列（下一字形相位 0
     * 需新列，+2）。写反会导致 12px 序列逐字错位、互相啃食。 */
    win_set_u16(win, WIN_TILE_OFFSET,
                (uint16_t)(off + ((startPixel == 0u) ? 0u : 2u)));

    ChsAdvanceCursor(st, win, glyphWidth);
}

/* =====================================================================
 * 表项写入分发（sWriteGlyphTilemapFuncs[fontNum]，tm1/tm3 路径）
 * 已验证 fn3/fn4 = cursor 格成对写；未验证 fontNum → UNKNOWN 不写。
 * ===================================================================== */
typedef void (*WriteGlyphTilemapFunc)(TextPrinter *, uint16_t, uint16_t);

static void WriteGlyphTilemap_Unknown(TextPrinter *win, uint16_t up, uint16_t lo)
{
    (void)win;
    (void)up;
    (void)lo;    /* UNKNOWN：不写（缺字排查信号） */
}

static void WriteGlyphTilemap_Font3_Font4(TextPrinter *win, uint16_t up, uint16_t lo)
{
    UpdateTilemap_Origin(win, up, lo);
}

static const WriteGlyphTilemapFunc sWriteGlyphTilemapFuncs[8] = {
    WriteGlyphTilemap_Unknown,   /* 0：未观测 */
    WriteGlyphTilemap_Unknown,   /* 1：未观测 */
    WriteGlyphTilemap_Unknown,   /* 2：未观测 */
    WriteGlyphTilemap_Font3_Font4,   /* 3：对话/菜单/详情页（gdb 实证） */
    WriteGlyphTilemap_Font3_Font4,   /* 4：队伍名（gdb 实证） */
    WriteGlyphTilemap_Unknown,   /* 5 */
    WriteGlyphTilemap_Unknown,   /* 6 */
    WriteGlyphTilemap_Unknown,   /* 7 */
};

/* =====================================================================
 * tm1/tm3 scratch 分配（B3 终版：流启动扫描定址 + 流内盲顺序 +
 * 带尾回卷本流带首；2026-08-25 嫁接至行相位表架构）
 * ---------------------------------------------------------------------
 * 等宽窗 tileData = 多窗共享静态只读 atlas，无私有可写区，像素必须落
 * charBlock 自由区，表项经 sWriteGlyphTilemapFuncs 指向 scratch。
 * 所有权：流启动（新绑/失配重锚/px==0）时扫本窗 BG tilemap 引用位图
 * 定空闲隙——tile 可写 ⇔ 无可见表项引用（原生不变量查实）。
 * 流状态 {scr_org,scr_next} 挂 ChsPhase 槽。流内盲顺序：own-next 恒相邻；
 * 带尾回卷 scr_org（本流带首，自踩语义）。容量：8px 非溢出字形 2 tile；
 * cb=2 带 [0x100,0x1DF)（223 tile）。流启动扫描带 16 tile 最小 run，
 * 无则退 n，再无则本流带首。tilemap 缺失（防御）→ 退回全局游标路径。
 * 自由区表（gdb 采集实测；charBlock 绝对 tile 号）：
 *  cb=1（font4 队伍窗）→ [0x0102,0x014B]。
 *  cb=2（font3 菜单/对话/图鉴/能力页）→ [0x0100,0x01DF]（▶/UI 章 0x1E0 之下）。
 *  cb=0（弹窗/对话）→ [0x0101,0x01AB]（地图 tileset 共存未明）。 */

/* 引用位图：扫本窗 BG tilemap 全部 0x400 表项，标记 [lo,lo+span) 内
 * 被引用 tile（bits[d>>5] 的 bit[d&31]，d=tile-lo）。 */
static void GlyphScanRefs(uint8_t *tpl, uint16_t lo, uint16_t span, uint32_t *bits)
{
    const uint16_t *tmap = (const uint16_t *)(uintptr_t)win_u32(tpl, 0x10);
    unsigned i;

    for (i = 0; i < 8u; i++)
        bits[i] = 0;
    if (!tmap)
        return;
    for (i = 0; i < 0x400u; i++) {
        uint32_t d = (uint32_t)(tmap[i] & 0x03FFu) - lo;
        if (d < span)
            bits[d >> 5] |= 1u << (d & 31u);
    }
}

/* 位图内首个连续 n 空位：自 prefer 起扫到带尾再回卷带首；无则 0xFFFF。 */
static uint16_t GlyphScanRun(const uint32_t *bits, uint16_t span, unsigned n, uint16_t prefer)
{
    uint16_t off;
    unsigned run = 0;

    if (prefer >= span)
        prefer = 0;
    for (off = 0; off < span; off++) {
        uint16_t idx = (uint16_t)(prefer + off);
        if (idx >= span)
            idx = (uint16_t)(idx - span);
        if (bits[idx >> 5] & (1u << (idx & 31u))) {
            run = 0;
            continue;
        }
        if (++run == n) {
            int first = (int)idx - (int)n + 1;
            if (first < 0)
                first += span;
            return (uint16_t)first;
        }
    }
    return 0xFFFFu;
}

static uint16_t GlyphScratchAlloc(TextPrinter *win,
                                  volatile struct ChsPhase *st,
                                  int slot_new, unsigned n)
{
    uint8_t *tpl = win_template(win);
    uint8_t cb = tpl ? tpl[1] : 0;
    uint16_t lo, hi, span, base;
    int restart, initialized, in_place;

    if (cb == 1) {
        lo = 0x0102u;
        hi = 0x014Bu;
    } else if (cb == 2) {
        lo = 0x0100u;
        hi = 0x01DFu;
    } else {
        lo = 0x0101u;
        hi = 0x01ABu;
    }
    span = (uint16_t)(hi - lo + 1u);

    if (!tpl || !win_u32(tpl, 0x10)) {
        /* tilemap 缺失（防御）：退回全局游标路径（7732 基线行为） */
        uint16_t cur = *(volatile uint16_t *)ADDR_GLYPH_ALLOC_NEXT;
        if (cur < lo || (uint16_t)(cur + n - 1u) > hi)
            cur = lo;
        *(volatile uint16_t *)ADDR_GLYPH_ALLOC_NEXT = (uint16_t)(cur + n);
        return cur;
    }

    /* 流启动 = 新绑 / 失配重锚 / px==0（PhaseBind 重锚恒清 px；行内 px
     * 单调递增不回 0）。
     * slot_new 语义（PhaseBind）：0=同行续接；1=新槽（新流，扫描定隙）；
     * 2=同键重锚（=同内容重绘，gdb 实证选项页 297 次/格三空隙轮转 =
     * 闪烁根因）→ 原地复用 scr_org：同字形写同 tile、表项重写同值，
     * 幂等零闪烁，且不再消耗自由带。FE 换行因 key 含 cursorY 必换槽。 */
    initialized = (st->scr_org != 0u || st->scr_next != 0u);
    in_place = (slot_new == 2) && initialized;
    restart = !in_place &&
              ((slot_new != 0) || (st->px == 0u) || !initialized);

    if (in_place) {
        base = st->scr_org;                 /* 原地重画：表项已指向本带 */
        st->scr_next = (uint8_t)(base + n);
    } else if (restart) {
        uint32_t bits[8];
        uint16_t prefer = st->scr_org;
        uint16_t got;
        GlyphScanRefs(tpl, lo, span, bits);
        got = GlyphScanRun(bits, span, 16u, prefer);
        if (got == 0xFFFFu)
            got = GlyphScanRun(bits, span, n, prefer);
        if (got == 0xFFFFu)
            got = prefer;                       /* 全带满：本流带首自踩 */
        st->scr_org = (uint8_t)got;
        st->scr_next = (uint8_t)(got + n);
        base = got;
    } else {
        /* 流内盲顺序：own-next 恒相邻（t-2/n 链成立），不扫描不重定位；
         * 带尾回卷本流带首（自踩语义，非塌缩，永不落 0x100 踩他流）。 */
        uint16_t next = st->scr_next;
        if ((uint16_t)(next + n) > span) {
            next = st->scr_org;
        }
        st->scr_next = (uint8_t)(next + n);
        base = next;
    }

    return (uint16_t)(lo + base);
}

/* ---- tm1/tm3 策略主体（现行 PrintGlyph_TextMode1 逐值原样）---- */
static void band_scratch(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    volatile struct ChsPhase *st;
    unsigned w, startPixel, w2, spilled;
    uint16_t t, u1, l1, u2, l2;
    uint8_t fontNum = win_u8(win, WIN_FONTNUM_REAL) & 7u;
    int slot_new = 0;
    struct GlyphTileInfo info;

    if (glyphWidth < 8u)
        glyphWidth = 8u;
    if (glyphWidth > 12u)
        glyphWidth = 12u;
    w = glyphWidth;

    st = PhaseBind(win, &slot_new);
    if (st->px == 0)
        st->tx0 = win_u8(win, WIN_CURSOR_TILE_X);

    startPixel = (unsigned)(st->px & 7u);
    w2 = (w > 8u) ? (w - 8u) : 0u;
    spilled = (startPixel > 0u);

    /* 共享列（bak 原地合成语义）：startPixel>0 ⇒ 首列即上一字形溢出列。
     * 盲顺序分配下上一字形溢出对 = t-2/-1：pass1 在该对上 RMW 合成，
     * [0,startPixel) 保留上一字右半像素。8px 非溢出只消耗一对（2 tile）。
     * B3：流启动（新绑/失配重锚/px==0）扫描定空闲隙，流内盲顺序。 */
    t = GlyphScratchAlloc(win, st, slot_new, (w2 == 0u && !spilled) ? 2u : 4u);

    if (spilled) {
        u1 = (uint16_t)(t - 2u);
        l1 = (uint16_t)(t - 1u);
    } else {
        u1 = t;
        l1 = (uint16_t)(t + 1u);
        /* 表项：首列 cursor 格（仅全新列需要映射；共享列已指向 u1/l1） */
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(st->tx0 + (st->px >> 3)));
        sWriteGlyphTilemapFuncs[fontNum](win, u1, l1);
    }
    u2 = (uint16_t)(t + 2u);
    l2 = (uint16_t)(t + 3u);

    info.textMode = 0;
    info.colors = 0;
    info.startPixel = (uint8_t)startPixel;
    info.width = 8;

    /* 第一趟：TL/BL 宽 8（跨列 spill 到新溢出对） */
    info.src = tiles->tl;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, u1);
    draw_tile(win, &info, spilled ? (uint8_t *)(uintptr_t)vram_tile(win, u2) : 0);
    info.src = tiles->bl;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, l1);
    draw_tile(win, &info, spilled ? (uint8_t *)(uintptr_t)vram_tile(win, l2) : 0);

    /* px 不在此推进（pass1 的 +8 已并入下方表项列公式，ChsAdvanceCursor
     * 统一 +w）；双重推进会使 px 每字 +20 → 表项列右移一列（半字根因）。 */

    if (w2 == 0u) {
        /* 8px 字形（日文）：行尾半列 spill 也要落表项（bak 同款），
         * 否则右半像素落在无表项的列上 → 丢半边。spill 列 = 起始列+1。 */
        if (spilled) {
            win_set_u8(win, WIN_CURSOR_TILE_X,
                       (uint8_t)(st->tx0 + ((st->px + 8u) >> 3)));
            sWriteGlyphTilemapFuncs[fontNum](win, u2, l2);
        }
        ChsAdvanceCursor(st, win, w);
        return;
    }

    /* 第二趟：TR/BR 宽 w-8，startPixel 复用（写第 2 对的
     * [startPixel, +w2)，与第一趟 spill [0,startPixel) 拼满整列）。
     * pass2 表项列 = tx0+((px+8)>>3)（12px 字形的右半列）。 */
    info.width = (uint8_t)w2;
    info.src = tiles->tr;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, u2);
    draw_tile(win, &info, 0);
    info.src = tiles->br;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, l2);
    draw_tile(win, &info, 0);
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(st->tx0 + ((st->px + 8u) >> 3)));
    sWriteGlyphTilemapFuncs[fontNum](win, u2, l2);

    /* 相位推进 + cursorTileX 同步（行相位表承载，单次 +w） */
    ChsAdvanceCursor(st, win, w);
}

/* ---- render 入口：内部 textMode 分发（tm2/未验证不绘制）---- */
void render_band(TextPrinter *win, const struct ChsGlyphTiles *t, unsigned w)
{
    int slot_new = 0;

    switch (win_u8(win, WIN_TEXTMODE) & 7u) {
    case 0:
        (void)PhaseBind(win, &slot_new);
        if (slot_new) {
            uint16_t off = win_u16(win, WIN_TILE_OFFSET);
            win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
        }
        band_tm0(win, t, 1, w);
        break;
    case 1:
    case 3:
        band_scratch(win, t, w);
        break;
    default:
        break;
    }
}

/* ---- FA/FB 箭头前置同步（现行 §14b 相位部分；计数清零/尾跳在调用侧）---- */
void arrow_band(TextPrinter *win)
{
    volatile struct ChsPhase *st;

    st = PhaseBind(win, 0);
    if (st->px) {
        uint16_t cols = (uint16_t)((st->px + 7u) >> 3);
        uint8_t want = (uint8_t)(st->tx0 + cols);
        uint8_t cur_tx = win_u8(win, WIN_CURSOR_TILE_X);

        if (cur_tx == 0u && want > 0u) {
            /* 翻页后 cursor 归零：半列相位时 TILE_OFFSET +=2（防双▼，B04），
             * 相位归零重锚行首 */
            if (st->px & 7u) {
                uint16_t off = win_u16(win, WIN_TILE_OFFSET);
                win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
            }
            st->px = 0;
            st->tx0 = win_u8(win, WIN_CURSOR_TILE_X);
        } else {
            win_set_u8(win, WIN_CURSOR_TILE_X, want);
            if (st->px & 7u) {
                uint16_t off = win_u16(win, WIN_TILE_OFFSET);
                win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
            }
            st->px = 0;
            st->tx0 = win_u8(win, WIN_CURSOR_TILE_X);
        }
    }
}
