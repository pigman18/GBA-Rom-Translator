/* =====================================================================================
 * PrintNextChar_hook.c — v6 渲染层（PrintNextChar hook 的消费端）
 *
 * 设计原则（用户拍板 2026-09-01）：
 *   - 摆脱 v4/v5 的逐窗登记 / 声明式配置表 / atlas 扫描：不做任何窗口模板
 *     （win[0x00]）地址匹配，不维护占用位图，不做 OBJ 运行时避让。
 *   - 渲染管线三段式、彼此独立，可 16+12+8 混排：
 *       Stage1 解压     GetGlyph(win, code, out128, &w)   —— text_translater.c 提供
 *       Stage2 栅格化   chs_rasterize(g128, fontSize, ...) —— 本文件，纯函数，
 *                       只把字模按字号切成若干 4bpp 列对，不碰 VRAM/游标
 *       Stage3 落址     chs_place(win, textMode, fontSize, ...) —— 本文件，
 *                       按 textMode 选固定区间分配器，写 VRAM + UTM + 推游标
 *   - tile 分配器 = 每个 textMode 一段写死区间（相对当前 BG charBase 的偏移，
 *     相对号 < 0x200 天然不落 charBlock1+ 的 OBJ 精灵区），只避开 game.h 里
 *     已硬编码的 UI 图标带；简单高水位 / 按行分槽，接受偶尔叠文本，绝不撞 UI。
 *
 * 约定：
 *   - fontNum==4  → 8px 小字，fontSize 形参忽略；
 *     其余         → fontSize=12 或 16（默认 16，走 16px 整格，零相位状态）。
 *   - 半角（非中文标点）交原生 FontFunc；中文标点带（0x36-0x3E）用中文标点
 *     字库自绘一列 8px。
 * ===================================================================================== */
#include "text.h"
#include "blend_glyph.h"
#include "scene_cfg.h"
#include "tile_alloc.h"

/* =====================================================================
 * §V6 Stage3 落址分配器（tile 号独立 + 位置交官方；2026-09-01 定案）
 *   两条腿解耦（见 docs/结论_替换BUG治本方向_tile号独立分配.md）：
 *     【tile 号】（写 tile data 的索引）→ 自己的高水位分配器 v6_alloc_tile()，
 *        每画一个字领唯一递增的相对号，不再跟官方每行清零的 TILE_OFFSET 走。
 *        这样每字独享 tile，替换/叠加不再发生。
 *     【屏幕位置】（写 tilemap 哪格）→ 继续交官方光标（继续调 UpdateTilemap，
 *        它内部经 GetCursorTilemapPointer 用 CX/TX/CY/TY 现算表项位置，官方
 *        管得对，保留）。
 *   各 textMode 只决定「屏幕光标怎么推」（决定下一字放屏幕哪列）：
 *     mode0 线性 → 官方推 TILE_OFFSET += 2 + cursorTileX += 1。
 *     mode1      → 与 mode0 同构（gdb 实证红宝石日版所有 tm1 都是线性）。
 *     mode3 网格 → 官方只推 cursorTileX += 1，不推 TILE_OFFSET。
 *     mode2 血条 → 缓冲指针，无 VRAM/tilemap 分配。
 * ===================================================================== */
#define V6_PITCH12          12u
#define V6_PITCH16          16u

/* =====================================================================
 * §V6 场景规则表（精细落址：条件分字号 + 每行固定基址；2026-09-01）
 *   键 = 窗口模板地址（tpl = win[0x00]）。命中则：
 *     - curX 分区决定字号（16 = key 标签固定 / 12 = value 候选动态）；
 *     - 每行固定 tile 基址（row_tab），tile = 行基址 + 行内偏移(px>>3)*2，
 *       确定性排列、重绘幂等；未命中回退全局高水位 v6_alloc_tile()。
 *   ⚠ 分区独立：16px 区（key）在前、12px 区（value）在后，不任意混排
 *     （16 是 8 的倍数 phase 恒 0，key 区结束 phase 归 0，12px 区从 0 续）。
 *   参考 bak/text-v4/text_scene.c 的 kOptWindow，但只保留必要字段，不做
 *   v4 的 WinCfg+kWindows[]+gen/check 脚本那套重流程。
 *   （结构定义与配置实例见 scene_cfg.h / scene_cfg.c）。
 * ===================================================================== */

/* 查询访问器（结构/配置实例 extern 自 scene_cfg.h；本文件是唯一实现方） */
const struct V6SceneRule *v6_scene_lookup(uint32_t tpl)
{
    unsigned i;
    for (i = 0; i < kV6SceneN; i++)
        if (kV6Scenes[i].tpl == tpl)
            return &kV6Scenes[i];
    return 0;
}

const struct V6Zone *v6_scene_zone(const struct V6SceneRule *r, uint8_t cx)
{
    unsigned i;
    for (i = 0; i < r->zone_n; i++)
        if (cx < r->zones[i].cx_hi)
            return &r->zones[i];
    return &r->zones[r->zone_n - 1u];
}

uint8_t v6_scene_font(const struct V6SceneRule *r, uint8_t cx)
{
    return v6_scene_zone(r, cx)->font_px;
}

/* 两个 curX 是否落在同一 zone（off 与 font_px 均相同 ⇒ 同一并列区，共享同一段
 * 行带）。续接判据用：同 zone + curX 右移 = 同行后继块（「类型」→「8」），续接
 * 相位；异 zone（「慢」→「普通」）各占 off 分区，不续接。
 * ⚠ font_px 也参与判据：16px 标签列与 12px 候选列 off 可能同为 0，但字号不同
 *   = 不同行带、不同 tile 步进，必须判异区（否则候选列被误判为标签列后继块、
 *   相位不复位 ⇒ 落址错位）。 */
int v6_same_zone(const struct V6SceneRule *r, uint8_t cx_a, uint8_t cx_b)
{
    const struct V6Zone *za = v6_scene_zone(r, cx_a);
    const struct V6Zone *zb = v6_scene_zone(r, cx_b);

    return za->off == zb->off && za->font_px == zb->font_px;
}

/* 行号：r = (curY - row_y0) >> row_shift，clamp 到 [1, row_n]。 */
static unsigned v6_scene_row_index(const struct V6SceneRule *r, uint8_t cy)
{
    unsigned rr;
    if (cy <= r->row_y0) {
        rr = 1u;
    } else {
        rr = (unsigned)(cy - r->row_y0) >> r->row_shift;
        if (rr < 1u)
            rr = 1u;
        if (rr > r->row_n)
            rr = r->row_n;
    }
    return rr - 1u;
}

/* 行基址：zone 有独立 row_tab 则用 zone 表，否则用主表。
 * 标题行（curY <= row_y0）走 rule->title_base 专用带，不再 clamp 到行 0 与
 * 首行标签（curY=1 ⇒ row 0）共用一条带（2026-09-04 标题「设置」被「对话速度」
 * 覆盖的根因；gdb 实证标题 curY=0、r1 curY=1、r2 curY=5）。 */
uint16_t v6_scene_row_base(const struct V6SceneRule *r, const struct V6Zone *z,
                           uint8_t cy)
{
    if (cy <= r->row_y0 && r->title_base != 0u)
        return r->title_base;
    {
        const uint16_t *tab = (z && z->row_tab) ? z->row_tab : r->row_tab;
        return tab[v6_scene_row_index(r, cy)];
    }
}

/* =====================================================================
 * §V6 Stage2 栅格化（纯函数，零状态）
 *   把 128B 中文字模（[TL@0][BL@32][TR@64][BR@96]）按字号切成若干列对，
 *   每个列对 = 一块 upper 32B + 一块 lower 32B 的 4bpp tile 数据。
 *   fontSize=8  → 1 列（TL/BL）；16 → 2 列（TL/BL, TR/BR）；12 → extract_cols。
 *   返回列数；cols==0 表示不可栅格化。
 * ===================================================================== */
static unsigned chs_rasterize(const uint8_t g128[CHS_CELL_BYTES],
                              unsigned fontSize,
                              uint8_t out[4][32])
{
    if (fontSize == 8u) {
        /* 8px：只取左半 TL/BL */
        for (unsigned i = 0; i < 32u; i++) {
            out[0][i] = g128[0x00 + i];
            out[1][i] = g128[0x20 + i];
        }
        return 1u;
    }

    if (fontSize == 16u) {
        for (unsigned i = 0; i < 32u; i++) {
            out[0][i] = g128[0x00 + i];
            out[1][i] = g128[0x20 + i];
            out[2][i] = g128[0x40 + i];
            out[3][i] = g128[0x60 + i];
        }
        return 2u;
    }

    /* fontSize==12：墨迹 12px，输出列数与相位有关，此处由落址层经
     * extract_cols 处理（调用方传 fontSize=12 时走 chs_place 的 12px 分支）。 */
    return 2u;
}

/* =====================================================================
 * §V6 分配器核心修复（2026-09-01）：
 *   **tile 号从自家分配器领，与官方 TILE_BASE+TILE_OFFSET/cursorTileX 解耦**。
 *   屏幕光标继续走官方语义（mode0 推 TILE_OFFSET += 2、mode3 推 cursorTileX
 *   += 1），因为 UpdateTilemap_PreserveCursorX 内部用 cursor 算 tilemap 表项
 *   **位置**——这是必要的（否则字错位）。但**表项值**和 tile_data 索引不再
 *   用官方算出的 tile 号（多窗并发时该值被多个 win 的 InitTextPrinter 重置
 *   成 0，必然互撞）。
 *   v6 起先为高水位 v6_alloc_tile()；2026-09-04 起升级为 v7 动态分配器
 *   v7_alloc_tile(win)（读 tilemap 避让带 + 确定性绕开，见 tile_alloc.c）。
 * ===================================================================== */

/* =====================================================================
 * §V6 12px 相位（CHS_ADVANCE_12=1）
 *   12px 步进 12 mod 8 = 4 ⇒ 相位只在 0/4 两态。官方游标只有整列粒度，
 *   相位必须自存（struct ChsPhase @ ADDR_CHS_PHASE，8B×8，game.h）。
 *   key = 行指纹（TILE_BASE ^ CURSOR_Y<<8 ^ CURSOR_TILE_Y<<4 ^ template>>2），
 *   换行/换流自动换 key = 相位归零；失配检测（cursor 回退/跳列）防重印错位。
 *   ⚠ v6 tile 号独立分配：cur_tile 记「当前列已领 tile 号」，phase!=0 时复用
 *   （相邻 12px 字共享半列 tile），每 2 字省 1 列（4 tile）。
 * ===================================================================== */
#if CHS_ADVANCE_12
static uint16_t chs_phase_key(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint16_t w = tpl ? (uint16_t)(((uintptr_t)tpl >> 2) & 0xFFFFu) : 0;

    return (uint16_t)((win_u16(win, WIN_TILE_BASE)
                       ^ ((uint16_t)win_u8(win, WIN_CURSOR_Y) << 8)
                       ^ ((uint16_t)win_u8(win, WIN_CURSOR_TILE_Y) << 4)
                       ^ w) | 0x8000u);
}

static volatile struct ChsPhase *chs_phase_slot(TextPrinter *win, uint16_t key)
{
    volatile struct ChsPhase *tab = (volatile struct ChsPhase *)ADDR_CHS_PHASE;
    unsigned i;

    for (i = 0; i < CHS_PHASE_COUNT; i++)
        if (tab[i].key == key)
            return &tab[i];
    for (i = 0; i < CHS_PHASE_COUNT; i++) {
        if (tab[i].key == 0u) {
            tab[i].key = key;
            tab[i].px  = 0;
            tab[i].tx0 = win_u8(win, WIN_CURSOR_TILE_X);
            tab[i].last_cx = win_u8(win, WIN_CURSOR_X);
            tab[i].cur_tile = 0;
            return &tab[i];
        }
    }
    tab[0].key = key;
    tab[0].px  = 0;
    tab[0].tx0 = win_u8(win, WIN_CURSOR_TILE_X);
    tab[0].last_cx = win_u8(win, WIN_CURSOR_X);
    tab[0].cur_tile = 0;
    return &tab[0];
}

/* =====================================================================
 * §V6 块边界相位复位已迁出到 InitTextPrinter_hook.c（2026-09-04 拆分）。
 * chs_phase_px 以下仍是本文件的渲染层相位原语（块内异常防御）。
 * ===================================================================== */
/* 当前行内相位（0..7）。块边界复位已上移到 InitTextPrinter hook（chs_init_phase），
 * 这里只保留块内异常防御：curX 漂移或 cursorTileX 回退 ⇒ 归零。 */
static unsigned chs_phase_px(TextPrinter *win)
{
    uint16_t key = chs_phase_key(win);
    volatile struct ChsPhase *s = chs_phase_slot(win, key);
    uint8_t tx = win_u8(win, WIN_CURSOR_TILE_X);
    uint8_t cx = win_u8(win, WIN_CURSOR_X);

    if (cx != s->last_cx || tx < s->tx0) {
        /* 块内异常：curX 漂移 or cursorTileX 回退 ⇒ 归零防御 */
        s->px  = 0;
        s->tx0 = tx;
        s->cur_tile = 0;
        s->last_cx = cx;
    }
    return (unsigned)s->px;
}

static uint16_t chs_phase_cur_tile(TextPrinter *win)
{
    uint16_t key = chs_phase_key(win);
    volatile struct ChsPhase *s = chs_phase_slot(win, key);
    return s->cur_tile;
}

static void chs_phase_advance(TextPrinter *win, unsigned adv_px, uint16_t cur_tile)
{
    uint16_t key = chs_phase_key(win);
    volatile struct ChsPhase *s = chs_phase_slot(win, key);

    s->px = (uint16_t)(s->px + adv_px);
    s->cur_tile = cur_tile;
}

/* 底色填充：把某列 tile 的 [x0,x1) 像素区间写成 colors[0]（窗口底色）。
 * 4bpp 源恒 0 ⇒ expand 全 0 nibble ⇒ colors[0] = color_d。 */
static void chs_fill_bg(TextPrinter *win, uint16_t tile, unsigned x0, unsigned x1)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
    uint8_t fg_ov, color_c, color_d, color_e;
    uint8_t colors[16];
    uint8_t zero[32];
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

    fg_ov   = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    color_c = fg_ov ? fg_ov : win_u8(win, WIN_COLOR_C);
    color_d = win_u8(win, WIN_COLOR_D);
    color_e = win_u8(win, WIN_COLOR_E);
    for (i = 0; i < 16u; i++)
        colors[i] = color_d;
    colors[14] = color_e;
    colors[15] = color_c;
    for (i = 0; i < 32u; i++)
        zero[i] = 0u;

    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)tile << 5)),
                           0, zero, x1 - x0, x0, colors);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(tile + 1u) << 5)),
                           0, zero, x1 - x0, x0, colors);
}

/* 任意墨宽两段式渲染（12px 中文 ink=12 / 8px 标点 ink=8）：
 *   phase + ink 不是 8 的倍数时拆两段，两段都落在目标 tile 可用区间内，
 *   永不溢出。tile 号：row_base!=0（命中场景规则）→ 行基址 + 列偏移(px>>3)*2
 *   确定性；否则 phase==0 领新列 / phase!=0 复用 cur_tile，第二段再领下一列。
 *   返回推进列数 adv=(phase+ink)/8，已推 cursorTileX 并记 cur_tile。
 *   TILE_OFFSET 由调用方按 adv*2 推进（mode0/1）。 */
static unsigned print_glyph_px(TextPrinter *win,
                               const uint8_t g128[CHS_CELL_BYTES],
                               unsigned ink)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
    uint8_t fg_ov, color_c, color_d, color_e;
    uint8_t colors[16];
    uint8_t up[32], lo[32];
    unsigned px = chs_phase_px(win);
    unsigned phase = px & 7u;
    unsigned w0 = (8u - phase < ink) ? (8u - phase) : ink;
    unsigned w1 = ink - w0;
    unsigned adv = (phase + ink) / 8u;
    uint16_t t0, t1;
    uint16_t row_base = 0u;
    uint8_t tx0 = win_u8(win, WIN_CURSOR_TILE_X);
    unsigned i;

    if (adv < 1u)
        adv = 1u;
    if (!tpl)
        return adv;
    tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!tile_data)
        return adv;

    fg_ov   = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    color_c = fg_ov ? fg_ov : win_u8(win, WIN_COLOR_C);
    color_d = win_u8(win, WIN_COLOR_D);
    color_e = win_u8(win, WIN_COLOR_E);
    for (i = 0; i < 16u; i++)
        colors[i] = color_d;
    colors[14] = color_e;
    colors[15] = color_c;

    /* tile：命中场景规则 → zone 行基址 + zone.off + 列偏移（确定性、重绘幂等）；
     * 否则高水位/相位复用 */
    {
        const struct V6SceneRule *rule =
            v6_scene_lookup((uint32_t)(uintptr_t)tpl);
        if (rule && rule->row_tab) {
            const struct V6Zone *z =
                v6_scene_zone(rule, win_u8(win, WIN_CURSOR_X));
            row_base = v6_scene_row_base(rule, z, win_u8(win, WIN_CURSOR_Y));
            row_base = (uint16_t)(row_base + z->off);
        }
    }
    if (row_base != 0u) {
        uint16_t col_off = (uint16_t)((px >> 3) * 2u);
        t0 = (uint16_t)(row_base + col_off);
        t1 = (w1 != 0u) ? (uint16_t)(row_base + col_off + 2u) : 0u;
    } else {
        /* 未命中静态表 → 动态分配器（读 tilemap 避让带 + 确定性绕开） */
        t0 = (phase == 0u) ? v7_alloc_tile(win) : chs_phase_cur_tile(win);
        t1 = (w1 != 0u) ? v7_alloc_tile(win) : 0u;
    }

    /* 第一段：源列 [0,w0) → t0 的 [phase, phase+w0) */
    extract_cols(g128, 0u, w0, up, lo);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)t0 << 5)),
                           0, up, w0, phase, colors);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(t0 + 1u) << 5)),
                           0, lo, w0, phase, colors);

    if (w1 != 0u) {
        /* 第二段：源列 [w0,ink) → t1 的 [0,w1)（phase!=0 时横跨 TL/TR，extract_cols 拼好） */
        extract_cols(g128, w0, w1, up, lo);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)t1 << 5)),
                               0, up, w1, 0u, colors);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(t1 + 1u) << 5)),
                               0, lo, w1, 0u, colors);
        /* 尾像素补齐：t1 剩余 [w1,8) 补底色（下一字 phase!=0 覆盖 / 行尾留净底） */
        chs_fill_bg(win, t1, w1, 8u);
    }

    /* tilemap：t0 列必写；第二段存在时 t1 列也写（表项位置走官方光标） */
    UpdateTilemap_PreserveCursorX(win, t0, (uint16_t)(t0 + 1u));
    if (w1 != 0u) {
        win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(tx0 + 1u));
        UpdateTilemap_PreserveCursorX(win, t1, (uint16_t)(t1 + 1u));
    }
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(tx0 + adv));

    chs_phase_advance(win, ink, (w1 != 0u) ? t1 : t0);
    return adv;
}

/* 半角不再交原生 FontFunc，统一走 draw_jp_glyph（下方），故相位补齐 flush
 * 不再需要：日文/半角也经 print_glyph_px 相位感知渲染，不会压字/留洞。 */
#endif /* CHS_ADVANCE_12 */

/* §V6 Stage3 单列写像素 + UTM（tile 号来自调用方 = 静态表或 v7 动态分配器）：
 *   tile_data[tile*32] 和 tile_data[(tile+lower_delta)*32] 各写一个 8x8 tile。
 *   UpdateTilemap_PreserveCursorX 用传入的 tile/lower 作表项**值**，表项**位置**
 *   由内部 cursorX/cursorTileX/cursorY/cursorTileY 算（必须保留官方语义）。
 *   cursorTileX += 1 保留——光标推进是"下一字屏幕列"，与 tile 号解耦。 */
static void chs_place_col(TextPrinter *win, uint16_t tile, uint16_t lower_delta,
                          const uint8_t *src_u, const uint8_t *src_l)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
    uint8_t fg_ov, color_c, color_d, color_e;
    uint8_t colors[16];
    uint16_t lower = (uint16_t)(tile + lower_delta);

    if (!tpl)
        return;
    tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!tile_data || tile == 0u)
        return;

    fg_ov   = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    color_c = fg_ov ? fg_ov : win_u8(win, WIN_COLOR_C);
    color_d = win_u8(win, WIN_COLOR_D);
    color_e = win_u8(win, WIN_COLOR_E);
    for (unsigned i = 0; i < 16u; i++)
        colors[i] = color_d;
    colors[14] = color_e;
    colors[15] = color_c;

    blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)tile << 5)),
                     0, src_u, 8u, 0u, colors);
    blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)lower << 5)),
                     0, src_l, 8u, 0u, colors);
    UpdateTilemap_PreserveCursorX(win, tile, lower);
    /* v5 blit_column_at_tile 末尾行为：每列推 cursorTileX += 1。
     * v6 重写时漏了此推进，导致 mode0/mode1 下一字落回同列 → 单字。 */
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
}

/* =====================================================================
 * §V6 日文/半角统一绘制（官方字库取字 + 统一分配）
 *   中文走中文字库 GetGlyph，日文/半角走官方字库 GetGlyphTilePointers，
 *   字形统一进 128B 4bpp 容器 → print_glyph_px / chs_place_col，共用
 *   静态表/v7 动态分配器领 tile，不再交回官方 FontFunc（官方 base+TILE_OFFSET
 *   每行清零 → 行间替换）。tm2 血条缓冲无像素/tilemap，仍交原生。
 * ===================================================================== */
static void jp_glyph_to_g128(uint8_t font_num, uint16_t glyph,
                             uint8_t g128[CHS_CELL_BYTES])
{
    uint8_t *up, *lo;
    unsigned i;

    GetGlyphTilePointers_Origin(font_num, glyph, &up, &lo);
    for (i = 0; i < CHS_CELL_BYTES; i++)
        g128[i] = 0u;

    if (FontIsShadowed(font_num)) {           /* font 3/4/5：4bpp 索引 0/14/15 */
        copy_tile32(g128 + 0x00u, up);        /* TL */
        copy_tile32(g128 + 0x20u, lo);        /* BL */
    } else {                                  /* font 0/1/2/6：1bpp → 索引 15/0 */
        CopyGlyph1bppTo4bpp_Origin(up, g128 + 0x00u, 15u, 0u);
        CopyGlyph1bppTo4bpp_Origin(lo, g128 + 0x20u, 15u, 0u);
    }
}

static int draw_jp_glyph(TextPrinter *win, uint8_t font_num, uint16_t glyph)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
    uint8_t g128[CHS_CELL_BYTES];

    if (tm != 0u && tm != 1u && tm != 3u)
        return 0;                             /* tm2 缓冲 / 未知：交原生 */
    if (font_num > 6u)
        font_num = 3u;

    jp_glyph_to_g128(font_num, glyph, g128);

#if CHS_ADVANCE_12
    {
        unsigned adv = print_glyph_px(win, g128, CHS_GLYPH_ADVANCE_JP_PX);
        if (tm == 0u || tm == 1u)
            win_set_u16(win, WIN_TILE_OFFSET,
                        (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + adv * 2u));
    }
#else
    {
        uint16_t tile = v7_alloc_tile(win);
        chs_place_col(win, tile, 1u, g128 + 0x00u, g128 + 0x20u);
        if (tm == 0u || tm == 1u)
            win_set_u16(win, WIN_TILE_OFFSET,
                        (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + 2u));
    }
#endif
    return 1;
}

/* =====================================================================
 * §V6 Stage3 落址：按 textMode 分派的 tile 分配器 + 写入。
 *   win/textMode/fontNum/fontSize 为 PrintNextChar 消费端统一入口传参。
 * ===================================================================== */
static void chs_place(TextPrinter *win, uint8_t textMode,
                      uint8_t fontNum, unsigned fontSize,
                      const uint8_t g128[CHS_CELL_BYTES])
{
    uint8_t tm = textMode & 7u;
    uint8_t buf[4][32];
    unsigned cols, col;
    const struct V6SceneRule *rule;
    uint16_t row_base = 0u;

    if (tm == 2u) {
        /* mode2 血条缓冲：无 VRAM 分配，推缓冲指针（8px 槽每列 +0x40） */
        uint32_t dst = win_u32(win, WIN_TILE_DATA);
        if (dst != 0u)
            win_set_u32(win, WIN_TILE_DATA,
                        dst + ((fontSize == 8u) ? 1u : 2u) * 0x40u);
        return;
    }
    if (tm != 0u && tm != 1u && tm != 3u)
        return;

    /* 场景规则：命中则用每行固定基址做确定性排列（zone 可覆盖基址表） */
    rule = v6_scene_lookup((uint32_t)(uintptr_t)win_template(win));
    if (rule && rule->row_tab) {
        const struct V6Zone *z =
            v6_scene_zone(rule, win_u8(win, WIN_CURSOR_X));
        row_base = v6_scene_row_base(rule, z, win_u8(win, WIN_CURSOR_Y));
        row_base = (uint16_t)(row_base + z->off);
    }

#if CHS_ADVANCE_12
    if (fontSize == 12u) {
        /* 12px 主字体：两段式 + 相位共享。命中规则 → 行基址+列偏移确定性；
         * 未命中 → v7 动态分配器（读 tilemap 避让带）。TILE_OFFSET 按 adv*2 推进。 */
        unsigned adv = print_glyph_px(win, g128, 12u);
        if (tm == 0u || tm == 1u)
            win_set_u16(win, WIN_TILE_OFFSET,
                        (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + adv * 2u));
        return;
    }
#endif

    cols = chs_rasterize(g128, fontSize, buf);
    if (cols == 0u)
        return;

#if CHS_ADVANCE_12
    if (fontSize == 16u && row_base != 0u) {
        /* 16px key（命中规则）：整格 2 列，tile = 行基址（已含 zone.off）+ 列偏移
         * (px>>3)*2，确定性、每字 4 tile；px += 16 保行内偏移连续。 */
        unsigned px = chs_phase_px(win);
        uint16_t col_off = (uint16_t)((px >> 3) * 2u);
        for (col = 0; col < cols; col++) {
            uint16_t tile = (uint16_t)(row_base + col_off + col * 2u);
            chs_place_col(win, tile, 1u, buf[col * 2u], buf[col * 2u + 1u]);
            if (tm == 0u || tm == 1u)
                win_set_u16(win, WIN_TILE_OFFSET,
                            (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + 2u));
        }
        chs_phase_advance(win, 16u, (uint16_t)(row_base + col_off + cols * 2u));
        return;
    }
#endif

    /* 8px / 16px 整格（未命中规则或 8px）：tile 号从动态分配器 v7_alloc_tile 领。
     * mode0/1 推 TILE_OFFSET += 2；mode3 只推 cursorTileX（chs_place_col 内）。 */
    for (col = 0; col < cols; col++) {
        uint16_t tile = v7_alloc_tile(win);
        chs_place_col(win, tile, 1u, buf[col * 2u], buf[col * 2u + 1u]);
        if (tm == 0u || tm == 1u)
            win_set_u16(win, WIN_TILE_OFFSET,
                        (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + 2u));
    }
}

/* =====================================================================
 * §V6 统一渲染入口（PrintNextChar / translater 消费端共调）：
 *   GetGlyph 解压 → chs_rasterize 栅格化 → chs_place 落址。
 *   fontNum==4 → 8px；否则 fontSize 形参（12/16，默认 12，12px 两段式相位）。 */
void chs_print(TextPrinter *win, uint32_t code, uint8_t fontSize)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
    uint8_t fn = win_u8(win, WIN_FONTNUM_REAL);
    uint8_t g128[CHS_CELL_BYTES];
    uint8_t w = 0;

    if (fn > 6u)
        fn = 3u;
    if (tm == 2u)
        fn = 4u;                 /* tm2 缓冲为原生 8px 槽 */
    if (fn == 4u) {
        fontSize = 8u;           /* font4 小字：fontSize 无效 */
    } else {
        /* 条件分字号：命中场景规则 → curX 分区字号（key 16 / value 12）；否则默认 12 */
        const struct V6SceneRule *rule =
            v6_scene_lookup((uint32_t)(uintptr_t)win_template(win));
        if (rule)
            fontSize = v6_scene_font(rule, win_u8(win, WIN_CURSOR_X));
        else if (fontSize != V6_PITCH12 && fontSize != V6_PITCH16)
            fontSize = V6_PITCH12;   /* 默认 12px（CHS_ADVANCE_12=1） */
    }

    if (!GetGlyph(win, code, g128, &w))
        return;
    chs_place(win, tm, fn, fontSize, g128);
}

/* =====================================================================
 * 半角 PCS 单字节渲染
 *   SYM 标点带（0x36-0x3E，tm0/tm3/tm1）→ 中文标点字库自绘一列 8px；
 *   其余半角（数字/拉丁/空格…）→ 交原生 FontFunc（DrawGlyph 内）。
 * 返回 1=已消费；0=未消费（交调用方原生分发）。
 * ===================================================================== */
int DrawHalfWidth(TextPrinter *win, uint32_t cur_char)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;

    if (cur_char >= SYM_GLYPH_BASE
        && cur_char < SYM_GLYPH_BASE + SYM_GLYPH_COUNT) {
        const uint8_t *sym =
            (const uint8_t *)ADDR_FONT_CHS_SYM + (cur_char - SYM_GLYPH_BASE) * 64u;
        uint8_t g128[CHS_CELL_BYTES];
        unsigned i;

        if (tm != 0u && tm != 3u && tm != 1u)
            return 0;
        for (i = 0; i < CHS_CELL_BYTES; i++)
            g128[i] = 0u;
        for (i = 0; i < 32u; i++) {
            g128[0x00 + i] = sym[i];
            g128[0x20 + i] = sym[32u + i];
        }
#if CHS_ADVANCE_12
        {
            /* 标点 8px 也走相位（ink=8 不改变 phase，但 phase!=0 时须跨列共享） */
            unsigned adv = print_glyph_px(win, g128, 8u);
            if (tm == 0u || tm == 1u)
                win_set_u16(win, WIN_TILE_OFFSET,
                            (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + adv * 2u));
        }
#else
        chs_place(win, tm, 0u, 8u, g128);   /* 标点按 8px 一列 */
#endif
        return 1;
    }

    /* tm1/tm2 半角：交原生 atlas，不碰动态区 */
    if (tm == 1u || tm == 2u)
        return 0;
    if (tm != 0u && tm != 3u)
        return 0;
    return 0;
}

/* PCS 单字节渲染入口（translater 替换流内消费）。恒返回 1=已消费。 */
int DrawGlyph(TextPrinter *win, uint32_t cur_char)
{
    if (cur_char >= 0xF7u)
        return 1;
    if (!DrawHalfWidth(win, cur_char)) {
        /* 数字/拉丁/假名：tm0/1/3 统一走 v6 分配器（官方字库取字 + 相位），
         * tm2 缓冲仍交原生。 */
        uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
        if (!draw_jp_glyph(win, win_u8(win, WIN_FONTNUM_REAL), cur_char))
            FontFunc_NativeDispatch(tm, win, cur_char);
    }
    return 1;
}

/* =====================================================================
 * 原生 FontFunc 分发（直调 Origin 地址常量；严禁经 FontFuncTable）。
 * ===================================================================== */
void FontFunc_NativeDispatch(uint8_t tm, TextPrinter *win, uint32_t c)
{
    typedef void (*fontfunc_t)(TextPrinter *, uint32_t);
    fontfunc_t fn;

    switch (tm & 7u) {
    case 0:
        fn = (fontfunc_t)(ADDR_FONT_FUNC_TM0_ORIGIN | 1u);
        break;
    case 1:
        fn = (fontfunc_t)(ADDR_PRINT_GLYPH_TM1_ORIGIN | 1u);
        break;
    case 2:
        fn = (fontfunc_t)(ADDR_FONT_FUNC_TM2_ORIGIN | 1u);
        break;
    case 3:
        fn = (fontfunc_t)(ADDR_FONT_FUNC_TM3_ORIGIN | 1u);
        break;
    default:
        return;
    }
    fn(win, c);
}

/* =====================================================================
 * PrintNextChar 唯一 hook：读编码 → 译（translater）→ 半角/回落。
 *   FA..FF：完整交还官方（含 index 推进）。
 *   F9 汉字/短语/slot：TranslateHandleChar（内部经 chs_print 渲染）。
 *   半角：DrawHalfWidth；未消费则原生 FontFunc。
 * ===================================================================== */
int PrintNextChar_Hook(TextPrinter *win)
{
    const uint8_t *text;
    uint16_t idx;
    uint8_t c;

    if (!win)
        return 0;

    /* 裸透传开关：ADDR_V6_BYPASS 非 0 时，啥都不处理直接消费当前字符
     * （return 1 = 不打印官方串，也不画中文）。用于：
     *   ① 验证「统一屏蔽输出」第 1 步是否干净（关掉后窗口只剩官方预渲染背景）
     *   ② 配合 gdb_patcher 观察 tilemap 活引用 = 导出避让带（画中文前的占用基线） */
    if (*(volatile uint8_t *)ADDR_V6_BYPASS != 0u)
        return 1;

    text = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    idx = win_u16(win, WIN_TEXT_INDEX);
    c = text[idx];

    if (c >= 0xFAu)
        return PrintNextChar_Origin(win);

    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx + 1u));

    if (TranslateHandleChar(win, c))
        return 1;
    if (c < 0xF7u && DrawHalfWidth(win, c))
        return 1;

    if (!draw_jp_glyph(win, win_u8(win, WIN_FONTNUM_REAL), c))
        FontFunc_NativeDispatch(win_u8(win, WIN_TEXTMODE), win, c);
    return 1;
}
