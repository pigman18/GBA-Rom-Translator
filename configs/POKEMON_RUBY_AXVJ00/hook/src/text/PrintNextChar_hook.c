/* =====================================================================================
 * PrintNextChar_hook.c — v6 渲染层（唯一 hook 的消费端）
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
 * ===================================================================== */
struct V6Zone {
    uint8_t cx_hi;      /* curX < cx_hi 命中本区；末条 0xFF 兜底 */
    uint8_t font_px;    /* 16 = key 固定 / 12 = value 动态 */
    uint8_t off;        /* 行内 tile 偏移起点（独立打印会话分区，沿用 v4 实测） */
    const uint16_t *row_tab;  /* zone 级行基址表（NULL = 用主表 row_tab） */
};

struct V6SceneRule {
    uint32_t tpl;             /* win[0x00] 模板地址 = 唯一键 */
    uint8_t  row_y0;          /* 行 0 的 curY */
    uint8_t  row_shift;       /* r = (curY - y0) >> shift */
    const uint16_t *row_tab;  /* 每行 tile 基址（[1..row_n]） */
    uint8_t  row_n;
    const struct V6Zone *zones;
    uint8_t  zone_n;
    const uint16_t *avoid;    /* 官方引用字形/保留区 tile 清单（相对 charBase 偏移，各占 2 格） */
    uint8_t  avoid_n;         /* avoid 项数；0 = 无避让（默认） */
};

/* 设置菜单（模板 0x081BB874）：行基址避引用字形，标签列 / 候选列均 12px。
 * 方案 B（用户拍板 2026-09-02）：标签列降 12px、复用候选 kOptRowBase 行带，
 * 靠 12px 相位共享省连续空间，不再引入 v4 的 PTR 散碎槽机制。
 * 行带 32 tile，固定 off 分区（相位独立——cursorTileX 回退触发失配归零）：
 *   标签列  off=0   占 [0,12)   （4 字 = 12 tile，最长行）
 *   候选A   off=12  占 [12,18)  （cx<19：慢/看/替换/单声道/普通/类型，最宽 3 字 8 tile）
 *   候选B   off=18  占 [18,24)  （19≤cx<22：普通/不看/打到底/立体声）
 *   候选C   off=24  占 [24,32)  （cx≥22：快/打到底/L/7）
 * 最宽「对战规则」行 = 标签 4 字 12t + 替换 2 字 6t + 打到底 3 字 8t = 32t 到边界。 */
static const uint16_t kOptRowBase[7] = {
    0x033u, 0x08Du, 0x0ADu, 0x0CDu, 0x101u, 0x121u, 0x121u,
};
static const struct V6Zone kOptZones[] = {
    /* 标签列（key）：12px 相位共享，与候选共用行带，off=0。 */
    { .cx_hi = 8u,    .font_px = 12u, .off = 0u,  .row_tab = 0 },
    /* 候选列（value）：同一行多个候选是独立打印会话，按 curX 分区 + 固定 off 落址。 */
    { .cx_hi = 19u,   .font_px = 12u, .off = 12u, .row_tab = 0 },
    { .cx_hi = 22u,   .font_px = 12u, .off = 18u, .row_tab = 0 },
    { .cx_hi = 0xFFu, .font_px = 12u, .off = 24u, .row_tab = 0 },
};

/* 不得被中文占用的 tile（各占 2 格：t 与 t+1），相对 charBase 偏移。
 * ① gdb 实测被本窗口（cb=2 选项窗）引用的字形  ② 已知特殊保留区（▶/菜单光标）。
 * 沿用 v3/v4 kOptGlyphAvoid 实测清单（2026-08-25 采集）。
 * ⚠ 清单不完整是主要风险：发现新乱码字符 → 反推 tile（=1+PCS*2）→ 补进 → 重编。 */
static const uint16_t kOptGlyphAvoid[26] = {
    0x001u, 0x021u, 0x031u, 0x06Fu, 0x077u, 0x08Bu, 0x0FFu, /* 1 33 49 111 119 139 255 */
    0x143u, 0x145u, 0x147u, 0x149u, 0x14Bu, 0x14Du, 0x14Fu, /* 323 325 327 329 331 333 335 */
    0x151u, 0x153u, 0x159u, 0x15Du, 0x171u, 0x18Du, 0x199u, /* 337 339 345 349 369 397 409 */
    0x1B7u, 0x1BFu, 0x1C3u,                                  /* 439 447 451 */
    0x1DFu, 0x1E1u,                                          /* ② 479 ▶字形 / 481 菜单光标 */
};

static const struct V6SceneRule kV6Scenes[] = {
    { .tpl = 0x081BB874u, .row_y0 = 3u, .row_shift = 1u,
      .row_tab = kOptRowBase, .row_n = 7u,
      .zones = kOptZones, .zone_n = 4u,
      .avoid = kOptGlyphAvoid, .avoid_n = 26u },
};
#define V6_SCENE_N  (sizeof(kV6Scenes) / sizeof(kV6Scenes[0]))

static const struct V6SceneRule *v6_scene_lookup(uint32_t tpl)
{
    unsigned i;
    for (i = 0; i < V6_SCENE_N; i++)
        if (kV6Scenes[i].tpl == tpl)
            return &kV6Scenes[i];
    return 0;
}

static const struct V6Zone *v6_scene_zone(const struct V6SceneRule *r, uint8_t cx)
{
    unsigned i;
    for (i = 0; i < r->zone_n; i++)
        if (cx < r->zones[i].cx_hi)
            return &r->zones[i];
    return &r->zones[r->zone_n - 1u];
}

static uint8_t v6_scene_font(const struct V6SceneRule *r, uint8_t cx)
{
    return v6_scene_zone(r, cx)->font_px;
}

/* 两个 curX 是否落在同一 zone（off 相同 ⇒ 同一并列区，共享同一段行带）。
 * 续接判据用：同 zone + curX 右移 = 同行后继块（「类型」→「8」），续接相位；
 * 异 zone（「慢」→「普通」）各占 off 分区，不续接。 */
static int v6_same_zone(const struct V6SceneRule *r, uint8_t cx_a, uint8_t cx_b)
{
    return v6_scene_zone(r, cx_a)->off == v6_scene_zone(r, cx_b)->off;
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

/* 行基址：zone 有独立 row_tab 则用 zone 表，否则用主表。 */
static uint16_t v6_scene_row_base(const struct V6SceneRule *r, const struct V6Zone *z,
                                  uint8_t cy)
{
    const uint16_t *tab = (z && z->row_tab) ? z->row_tab : r->row_tab;
    return tab[v6_scene_row_index(r, cy)];
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
 *   **tile 号从自家高水位领，与官方 TILE_BASE+TILE_OFFSET/cursorTileX 解耦**。
 *   屏幕光标继续走官方语义（mode0 推 TILE_OFFSET += 2、mode3 推 cursorTileX
 *   += 1），因为 UpdateTilemap_PreserveCursorX 内部用 cursor 算 tilemap 表项
 *   **位置**——这是必要的（否则字错位）。但**表项值**和 tile_data 索引不再
 *   用官方算出的 tile 号（多窗并发时该值被多个 win 的 InitTextPrinter 重置
 *   成 0，必然互撞），而是从 v6_alloc_tile() 领一个唯一递增的相对号。
 *   区间 [0x100, 0x1C8)：据 docs/场景特征与偏移量表.md 四，cb=2 自由带
 *   [0x100,0x1C8]，[0x1C9,0x1F7] 是详情页原生「场景映射」，[0x1E0,0x1FF]
 *   是 UI 光标/图标章——一律避开。跨 charBase 物理地址不同天然不撞；同
 *   charBase 多窗单线程顺序领 tile 天然防撞。满了回卷到起点（覆盖最早的
 *   旧中文——属于"撞自家"，不影响官方图标）。TODO：cb=1 自由带更窄
 *   [0x102,0x14B]、cb=0 [0x101,0x1AB]，单全局高水位对 cb=1 偏宽，可后续
 *   按 charBase 分桶；当前各窗中文量少，实践中够用。
 * ===================================================================== */
#define V6_TILE_HW_LO       0x100u
#define V6_TILE_HW_HI       0x1C8u
#define V6_TILE_HW_RSV      0x08u     /* 接近上界回卷，留半行余量 */

static uint16_t v6_alloc_tile(void)
{
    volatile uint16_t *hw = (volatile uint16_t *)ADDR_V6_TILE_HW;
    uint16_t t = *hw;

    if (t < V6_TILE_HW_LO || t >= V6_TILE_HW_HI - V6_TILE_HW_RSV)
        t = V6_TILE_HW_LO;
    *hw = (uint16_t)(t + 2u);
    return t;
}

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

/* 用 InitTextPrinter 的参数直接构造「新块」行指纹 key（不读 win 字段——
 * hook 时 win[0x16]/[0x1C]/[0x1D] 还是旧值，本体尚未写入）。
 * 新块 CURSOR_TILE_Y 必然被 InitTextPrinter 归零 ⇒ 该项恒 0。 */
static uint16_t chs_phase_key_from(uint8_t *tpl, uint16_t tile_base, uint8_t cur_y)
{
    uint16_t w = tpl ? (uint16_t)(((uintptr_t)tpl >> 2) & 0xFFFFu) : 0;

    return (uint16_t)((tile_base
                       ^ ((uint16_t)cur_y << 8)
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
 * §V6 块边界相位复位（InitTextPrinter hook，2026-09-02 半透明空格 BUG）
 * ── 根因 ────────────────────────────────────────────────────────
 *  ChsPhase 是全局 8×8 槽表，靠行指纹 key 区分，但**没有文本块生命周期**——
 *  块结束/窗口重建后旧 px 赖在表里。主菜单「新游戏」每次进入 curX/tpl/TILE_BASE
 *  相同 ⇒ key 命中同一 slot、px 停在上一轮非零值(phase=4) ⇒ 第一字左 4px 既没
 *  画字也没补底色，露出 tile 脏数据 = 半透明空格。
 *  旧 `tx==0` 判据是**事后间接信号**（依赖 PrintNextChar 首字时 cursorTileX 恰
 *  为 0），在窗口复用/未重走 InitTextPrinter 的场景下不可靠 ⇒ 用户定夺必须
 *  **hook InitTextPrinter**：块边界是文本生命周期最权威的直接证据。
 * ── 续接保留 ────────────────────────────────────────────────────
 *  类型7「类型」(curX=15) →「8」(curX=18) 是两个独立文本块（两次 InitTextPrinter），
 *  但属同一候选值的顺序衔接，须续接 px（否则「8」落回行首覆盖「类」）。
 *  判据：scene 规则命中 + 新 curX 严格变大 + 同 zone（off 相同）⇒ 续接；
 *  否则（重进同一块 / 换行 / 换 zone / 非 scene 窗口）⇒ 复位 px。
 *  非 scene 窗口（主菜单等）恒复位——它们没有「同行后继块」场景，复位即消空格。
 * ===================================================================== */
static void chs_init_phase(TextPrinter *win, uint16_t tile_base,
                           uint8_t cur_x, uint8_t cur_y)
{
    uint8_t *tpl = win_template(win);
    uint16_t key = chs_phase_key_from(tpl, tile_base, cur_y);
    volatile struct ChsPhase *tab = (volatile struct ChsPhase *)ADDR_CHS_PHASE;
    volatile struct ChsPhase *s = 0;
    const struct V6SceneRule *rule =
        v6_scene_lookup((uint32_t)(uintptr_t)tpl);
    unsigned i;

    for (i = 0; i < CHS_PHASE_COUNT; i++) {
        if (tab[i].key == key) {
            s = &tab[i];
            break;
        }
    }
    if (!s) {
        for (i = 0; i < CHS_PHASE_COUNT; i++) {
            if (tab[i].key == 0u) {
                s = &tab[i];
                break;
            }
        }
        if (!s)
            s = &tab[0];
        s->key = key;
        s->px  = 0;
        s->tx0 = 0;
        s->last_cx = cur_x;
        s->cur_tile = 0;
        return;                       /* 新分配：恒复位 */
    }

    /* 命中既有槽：同行后继块续接，否则复位 */
    if (rule && cur_x > s->last_cx && v6_same_zone(rule, cur_x, s->last_cx)) {
        s->tx0 = 0u;                  /* 续接：仅重锚块内游标锚点，px 保留 */
        s->last_cx = cur_x;
    } else {
        s->px  = 0u;
        s->tx0 = 0u;
        s->cur_tile = 0u;
        s->last_cx = cur_x;
    }
}

/* InitTextPrinter 入口钩（entry.s 跳板已重放前 8B、保 r0-r3、重排参数）。
 * 参数：win / tile_base(r2) / cur_x(r3) / cur_y(第5参数，栈)。只读不改 win。 */
void InitTextPrinter_hook_C(TextPrinter *win, uint16_t tile_base,
                            uint8_t cur_x, uint8_t cur_y)
{
    chs_init_phase(win, tile_base, cur_x, cur_y);
}

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
        t0 = (phase == 0u) ? v6_alloc_tile() : chs_phase_cur_tile(win);
        t1 = (w1 != 0u) ? v6_alloc_tile() : 0u;
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

/* §V6 Stage3 单列写像素 + UTM（tile 号来自调用方 = v6_alloc_tile 领的）：
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
 * §V6 日文/半角统一绘制（官方字库取字 + v6_alloc_tile 统一分配）
 *   中文走中文字库 GetGlyph，日文/半角走官方字库 GetGlyphTilePointers，
 *   字形统一进 128B 4bpp 容器 → print_glyph_px / chs_place_col，共用
 *   v6_alloc_tile 分配 tile，不再交回官方 FontFunc（官方 base+TILE_OFFSET
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
        uint16_t tile = v6_alloc_tile();
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
         * 未命中 → v6_alloc_tile 高水位。TILE_OFFSET 按 adv*2 推进。 */
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

    /* 8px / 16px 整格（未命中规则或 8px）：tile 号从 v6_alloc_tile() 领。
     * mode0/1 推 TILE_OFFSET += 2；mode3 只推 cursorTileX（chs_place_col 内）。 */
    for (col = 0; col < cols; col++) {
        uint16_t tile = v6_alloc_tile();
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
