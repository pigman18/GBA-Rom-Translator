/* =====================================================================================
 * PrintNextChar_hook.c — AXVJ 12px 渲染器：纯函数 tile 网格（运行时唯一 C 模块）
 *
 * ── 为什么重写（2026-11-11 晚）────────────────────────────────────────
 * 串页方案把「12px 相位」整体前移到构建期，于是每列 64B 内容必须在运行时
 * 搬进某个 VRAM tile —— 反推出 PHYS 池 / 288 对槽 / 4.4MB 页表，
 * 也就是又回到了「管 tile」；而池子盖住原版场景图块，画面出现黑块碎片。
 *
 * 本文件回到 11-10 已实证的机制（TASKS.md §1.2 / POKEMON_RUBY §9.3.3）：
 *   tile = TILE_BASE + (row&7)*62 + col*2   ← 屏幕行列的**纯函数**
 *   12px 跨列共享由**运行时逐像素合成**：读回该列 64B，清本字墨迹盒，
 *   写墨迹，再 32bit 写回。共享列的前 4px 落在盒外，天然不被邻字擦掉。
 * 没有分配器、没有水位、没有回收、没有场景门控、没有页表、没有 EWRAM 相位表。
 * 全部 tile 落在原版自己的 [TB, TB+0x1F0) 预载字库区内，不碰 UI 图标。
 *
 * 重印清尾：cbc5ce5 的 clear_cols 在网格引擎 + 开始菜单同 printer 同 seg 下会
 * 把光标重绘误判成重印，洗掉整行菜单字并误伤备忘第二行；暂不在此层清尾。
 *
 * ── 协议（用户口径）───────────────────────────────────────────────────
 * 全局统一 `F7 00 hi lo`。流里只有：
 *   F7 00 hi lo   4B / 12px   → 0x09000000 字库，gidx = lead_adjust(hi)*256+lo
 *   PCS 单字节    1B / 8px    → 0x36..0x3E 走 CHS Sym@0x091E0000（64B/字）；
 *                               其余走原版 GetGlyphTilePointers 现场展开
 *   FA..FF 控制码             → 原版状态机
 *
 * ── hook 链与 lr 契约 ─────────────────────────────────────────────────
 * P01 @0x080032F8 → entry.s EngineEntry（bx）→ PrintNextChar_Hook（本文件唯一导出）。
 * P01 只盖 8B 且订址桩用 bx（非 bl），C 的 lr = 原版调用者返回地址；
 * 从 C 再 bl PrintNextChar_Origin 会多压一层 {r4,lr} → 栈失衡，
 * 故任何情况下都不回落原版 PrintNextChar（设计 §5.1 判断 D）。
 * ===================================================================================== */
#include "game.h"
#include "text_grid.h"

/* =====================================================================
 * §0 可选运行时诊断（-DGRID_DIAG 才启用；产品构建不带）
 *
 * 环形日志落 0x0203E000（docs §9.4.4 实证该区恒零、不被堆使用），
 * 128 条 × 24B；写指针在 +0x1000。bot 的 shot 会落 ram.bin，
 * 离线按 EWRAM 偏移 0x3E000 解码即可，无需 GDB。
 *
 * 24B/条：[0]tag [1..2]code [3]phase [4]cx [5]rel [6]col [7]flags
 *         [8..9]t0 [10]fg_used [11]bg_used
 *         [12]winC [13]winD [14]winE [15]palette
 *         [16]tpl5 [17]tpl6 [18]tpl7 [19]tpl8
 *         [20..23]textPtr
 * ===================================================================== */
typedef struct GridTarget GridTarget;   /* 定义见 §3，§0 的前置声明只需不完整类型 */
#ifdef GRID_DIAG
#define DIAG_BASE   0x0203E000u
#define DIAG_RECS   128u
#define DIAG_RECB   24u
#define DIAG_SEQP   0x1000u
static void diag_emit(unsigned tag, unsigned code, unsigned phase,
                      TextPrinter *win, const GridTarget *t, unsigned t0,
                      unsigned fg, unsigned bg);
static void diag_ctrl(unsigned tag, unsigned code, uint16_t index);
static void diag_store(unsigned t0, const uint8_t *p0);
#else
#define diag_emit(t,c,ph,w,gt,t0,fg,bg)          ((void)0)
#define diag_ctrl(t,c,i)                         ((void)0)
#define diag_store(t0,p0)                        ((void)0)
#endif

/* =====================================================================
 * §1 原版语义常量
 * ===================================================================== */
enum {
    AXV_STATE_END = 0,
    AXV_STATE_BEGIN,
    AXV_STATE_NORMAL,
    AXV_STATE_CHAR_DELAY,
    AXV_STATE_PAUSE,
    AXV_STATE_WAIT_BUTTON,
    AXV_STATE_NEWLINE,
    AXV_STATE_PLACEHOLDER,
    AXV_STATE_WAIT_CLEAR,
    AXV_STATE_WAIT_SCROLL,
    AXV_STATE_WAIT_SOUND
};

#define FC_FG            1u
#define FC_BG            2u
#define FC_SHADOW        3u
#define FC_ALLCOLORS     4u
#define FC_PALETTE       5u
#define FC_FONT          6u
#define FC_DEFAULTFONT   7u
#define FC_PAUSE         8u
#define FC_WAITBUTTON    9u
#define FC_WAITSOUND     10u
#define FC_PLAYBGM       11u
#define FC_PLAYSE        12u
#define FC_ESCAPE        13u
#define FC_SHIFT_TILE_X  14u
#define FC_SHIFT_TILE_Y  15u
#define FC_CLEARWINDOW   16u

#define TPL_TILE_DATA    0x0C
#define TPL_TILEMAP      0x10
#define TPL_DEFAULT_FONT 0x08

/* =====================================================================
 * §2 纯函数网格：行 / 列 / tile 号
 * ===================================================================== */
/* GetCursorTilemapPointer@0x08003708 里 (curY+curTY) 本身就是 tilemap 行号
 * （每行 32 项）；换行 CTY += 2（16px 字占上下两行）⇒ >>1 是连续文本行号。 */
static unsigned grid_row(TextPrinter *win)
{
    return ((unsigned)win_u8(win, WIN_CURSOR_Y)
            + (unsigned)win_u8(win, WIN_CURSOR_TILE_Y)) >> 1;
}

/* 行段存储列（BUG-B 2026-11-19，2026-11-23 按 BUG-9 收敛）。
 *
 * 公式只有 8 个 band，而图鉴列表要画 11 行（GDB 实测 curY 10..30 ⇒
 * row 5..15）。row 13 的 row&7 = 5，与 row 5 同 band 同列 ⇒ 同 tile，
 * 第 9 行字模直接覆盖第 1 行：顶行「No003 妙蛙花」变「No011 ------」。
 * tilemap 实测 0x15F..0x16E 被 (r10/r11) 与 (r26/r27) 双重引用。
 *
 * 修法（BUG-B）：回绕行把**存储列**翻到另半区（col ^ 16）——屏幕位置由
 * tilemap 表项决定，与存储 tile 号无关，所以画面不变。
 *
 * BUG-9 修正：无条件翻会制造新碰撞。存档框实测
 *   信息框第 1 行 row0 col1..8  → tile 5,7,9..（不翻）
 *   确认句第 2 行 row8 col16..19 → 16^16 = 0 → tile 3,5,9
 * 两句同 band0，确认句后画，把「118」覆盖成「里吗？」的残字。
 * 现改成**只有该 tile 真被本列别的行引用时才翻**：
 *   · 图鉴 row13 col1 展开后正是 row5 指着的 tile → 照旧翻，11 行不撞
 *   · 存档框确认句 col16 展开后本列无人引用 → 不翻 → 与信息框错开
 * 判据只扫「同一列」32 项，与 grid_tile_taken 同口径（排除本格自身）。 */
static int grid_col_claims_tile(TextPrinter *win, unsigned col, uint16_t t0);

static unsigned grid_store_col(TextPrinter *win, unsigned row, unsigned col)
{
    unsigned band = row & (GRID_SEG_COUNT - 1u);
    uint16_t unf;

    if (row < GRID_SEG_COUNT)
        return col;
    /* 只翻低 4 位：保证结果仍在 [0, GRID_COLS_PER_SEG) 内 */
    unf = (uint16_t)((unsigned)win_u16(win, WIN_TILE_BASE) + 2u
                     + band * GRID_SEG_TILES + 2u * col);
    return grid_col_claims_tile(win, col, unf) ? (col ^ 16u) : col;
}

static uint16_t grid_tile(TextPrinter *win, unsigned col)
{
    uint16_t tb = win_u16(win, WIN_TILE_BASE);
    unsigned row = grid_row(win);

    /* textMode3：GetBlankTileNum = TB+1。若 arena 从 TB 起算，band0/col0
     * 的 lower 正好是 TB+1 → 写汉字/▶ 时踩碎「空白」模板；开始菜单
     * RedrawMenuCursor 再 Blank 把格指回 TB+1，屏上冒灰影残墨
     *（bot：START 开→关→开→上下，残墨色 (74,74,74)=阴影灰）。
     * 存储列由 grid_store_col 决定（含 BUG-9 的按需翻半区）。 */
    return (uint16_t)((unsigned)tb + 2u
            + (row & (GRID_SEG_COUNT - 1u)) * GRID_SEG_TILES
            + 2u * grid_store_col(win, row, col));
}

/* =====================================================================
 * textMode 0 直写（BUG-C，2026-11-19 GDB + 反汇编定案）
 *
 * **只有 textMode 1 需要分配 tile**（原版按字形槽号 tile=TB+2*glyph，
 * 所以预载 UI 图形与文本永不互踩）。其余 textMode 全是**直写**：
 *
 *   textMode 0 — 累加器  tile = TILE_BASE + TILE_OFFSET
 *   textMode 2 — 写 win+0x20 缓冲（grid_setup 的 buffered 分支）
 *   textMode 3 — 屏幕行列 tile = TB + 2 + (curX+curTX) + 30*(curY+curTY)
 *                （反汇编 0x080034E0 逐条确认：adds #2 / lsls#4+subs / lsls#1
 *                  = row*30；注意是 row*30 不是 band*62）
 *
 * GDB 实测 origin 侧（battle_menu_audit 20261119T171208，**未打补丁** ROM，
 * 在 PrintNextChar@0x080032F8 入口逐字采样 win）：
 *
 *   菜单窗 TB=0x190 curX=19：
 *     index  TILE_OFF  curTX  curTY
 *       0      0x00      0      0    ← 串首
 *      17      0x12      9      0
 *      18      0x12      0      2    ← 换行：TILE_OFF 不变，curTX 归零
 *      27      0x24      9      2
 *
 * ⇒ textMode 0 三铁律：
 *   ① tile = TILE_BASE + TILE_OFFSET
 *   ② 每印一个字 TILE_OFFSET += 2（行内恒有 TILE_OFFSET = 2*cursorTileX）
 *   ③ 换行时 TILE_OFFSET **不清零**，只有 curTX 归零、curTY += 2
 *   且**没有冲突规避、没有 0x1F0 上限**。
 *
 * 旧实现把 textMode 0 也套网格 TB+2+band*62+2*col：
 *   TB=0x1B8 row=17 → band=1 → 0x1F8 > 0x1F0 ⇒ 越界分支 return，
 *   整个战斗对话框一字不写（BUG-C 症状）；冲突规避还会把相邻两字
 *   迁到同一空闲 tile（实测 x20/x21 同指 0x1A4 → 「宝可梦」和「逃跑」
 *   之间冒残字）。
 * ===================================================================== */

/* textMode 0 的 tile 号 = TB + TILE_OFFSET（铁律 ①）。 */
static uint16_t grid_tile_linear(TextPrinter *win)
{
    return (uint16_t)((unsigned)win_u16(win, WIN_TILE_BASE)
                    + (unsigned)win_u16(win, WIN_TILE_OFFSET));
}

/* ---------------------------------------------------------------------
 * tile 冲突规避（2026-11-13 实测定案）
 *
 * 原版 tm1 按**字形槽号**分配（tile = TB + 2*glyph），所以预载的 UI 图形
 * 与文本永远不会互踩。本引擎按**屏幕位置**分配（row/col 纯函数），于是
 * 「窗口 charBase 里同时躺着别的图形」时必然撞车：
 *
 *   队伍菜单 row5 段 = 0x137..0x175；游戏把「麻痹」椭圆预载在 tile
 *   0x156..0x159（tilemap (5..8,6)，pal 11）。右侧列表第 4 格的昵称
 *   落在 col 16..19 → 正好是 0x157/0x159/0x15B/0x15D，把椭圆三个 tile
 *   改写成汉字笔画，实机表现为「黄竖条 + 红碎字、椭圆整段消失」。
 *
 * 判据（不是地址白名单）：写之前扫一遍**本窗口自己的 tilemap**，
 * 若目标 tile 已被「不属于本格」的格子引用 ⇒ 换一对没人引用的 tile
 * 承载，并把本格指向它。没有状态、没有分配器水位；只有「这一格现在
 * 能不能用」的即时判断，所以图形没了自然又回到纯函数 tile。
 * ------------------------------------------------------------------- */
/* 本窗字库基址（与 grid_setup 同一口径：tpl+0x0C 或 tm2 缓冲）。 */
static uint32_t grid_tile_base(TextPrinter *win)
{
    const uint8_t *tpl = win_template(win);

    if (win_u8(win, WIN_TEXTMODE) == 2u
        || (tpl != 0 && win_u32(tpl, TPL_TILEMAP) == 0u))
        return win_u32(win, WIN_TILE_DATA);
    return tpl ? *(const uint32_t *)(const void *)(tpl + TPL_TILE_DATA) : 0u;
}

static uint16_t grid_tilemap_entry(const uint16_t *map, unsigned x, unsigned y)
{
    return (uint16_t)(map[y * GRID_TILEMAP_W + x] & 0x3FFu);
}

/* 只改低 10 位 tile 号，保留调色板/翻转等高位（与 grid_tilemap_entry 对称）。
 * BUG-11 清行尾用。 */
static void grid_tilemap_set(uint16_t *map, unsigned x, unsigned y,
                             uint16_t tile)
{
    uint16_t *p = &map[y * GRID_TILEMAP_W + x];
    *p = (uint16_t)((*p & 0xFC00u) | (tile & 0x3FFu));
}

/* 光标所在 tilemap 行（与 UpdateTilemap 同口径）。
 * 禁止用 (row&7)*2：row≥8 时会把「本格」误判到 y=0/1（背包图一带），
 * 规避/占用扫描与真实写点错位 → 底行/切页撞 UI。 */
static unsigned grid_cursor_ty(TextPrinter *win)
{
    return (unsigned)win_u8(win, WIN_CURSOR_Y)
         + (unsigned)win_u8(win, WIN_CURSOR_TILE_Y);
}

/* 本格自己的两个表项（上/下 tile 行）；这两项不算「别人在用」。 */
static int grid_cell_own(TextPrinter *win, unsigned col,
                         unsigned x, unsigned y)
{
    unsigned ty = grid_cursor_ty(win);

    if (x != col)
        return 0;
    return y == ty || y == ty + 1u;
}

/* 本列里除本格（上/下两行）之外，是否已有格子指向 t0（或 t0+1）。
 * 只扫同一列 32 项：撞车必然发生在「同 band 同列」上，跨列由 band 公式
 * 天然分开。判据与 grid_tile_taken 同口径（排除本格自身）。 */
static int grid_col_claims_tile(TextPrinter *win, unsigned col, uint16_t t0)
{
    const uint8_t *tpl = win_template(win);
    const uint16_t *map;
    unsigned y;

    if (!tpl || col >= GRID_TILEMAP_W)
        return 0;
    map = (const uint16_t *)(const void *)(uintptr_t)win_u32(tpl, TPL_TILEMAP);
    if (!map)
        return 0;
    for (y = 0u; y < GRID_TILEMAP_W; ++y) {
        unsigned v;
        if (grid_cell_own(win, col, col, y))
            continue;
        v = grid_tilemap_entry(map, col, y);
        if (v == t0 || v == (unsigned)t0 + 1u)
            return 1;
    }
    return 0;
}

/* 收集本窗 tilemap 已被占用的 tile（排除本格自身）。返回 1 表示 t0/t0+1
   已被别人引用。 */
static int grid_tile_taken(TextPrinter *win, unsigned col,
                           uint16_t t0, uint32_t *used)
{
    const uint8_t *tpl = win_template(win);
    const uint16_t *map;
    unsigned x, y, i;

    for (i = 0u; i < GRID_TILE_BITS / 32u; ++i)
        used[i] = 0u;
    if (!tpl)
        return 0;
    map = (const uint16_t *)(const void *)(uintptr_t)win_u32(tpl, TPL_TILEMAP);
    if (!map)
        return 0;

    for (y = 0u; y < GRID_TILEMAP_W; ++y) {
        for (x = 0u; x < GRID_TILEMAP_W; ++x) {
            unsigned v;
            if (grid_cell_own(win, col, x, y))
                continue;
            v = grid_tilemap_entry(map, x, y);
            if (v < GRID_TILE_BITS)
                used[v >> 5] |= 1u << (v & 31u);
        }
    }
    if (t0 >= GRID_TILE_BITS)
        return 0;
    if (used[t0 >> 5] & (1u << (t0 & 31u)))
        return 1;
    if (t0 + 1u < GRID_TILE_BITS &&
        (used[(t0 + 1u) >> 5] & (1u << ((t0 + 1u) & 31u))))
        return 1;
    return 0;
}

static int grid_tile_free(const uint32_t *used, unsigned n)
{
    if (n + 1u >= GRID_TILE_LIMIT || n + 1u >= GRID_TILE_BITS)
        return 0;
    if (used[n >> 5] & (1u << (n & 31u)))
        return 0;
    if (used[(n + 1u) >> 5] & (1u << ((n + 1u) & 31u)))
        return 0;
    return 1;
}

/* 预载图形判定：VRAM 里这一对 tile 已经**有内容**，而本格 tilemap 还
 * 没指向它 ⇒ 它是游戏预载的图形（如麻痹椭圆的 0x15A..0x15E）。
 * 这些 tile 在 tilemap 里暂时没有引用项（图形是在文本之后才挂上去的），
 * 单靠「被引用」判不出来，必须看 VRAM 本体。
 *
 * 反例（2026-11-13 第一次修复只查 tilemap）：0x157/0x158/0x159 因为
 * 椭圆已挂表而被避开，但同段 0x15B/0x15D 还没挂表，被当成空闲拿走，
 * 结果椭圆右半仍是汉字碎笔画。 */
static int grid_tile_vram_blank(uint32_t base, unsigned n)
{
    const volatile uint32_t *p =
        (const volatile uint32_t *)(uintptr_t)(base + 32u * n);
    unsigned i;

    for (i = 0u; i < 8u; ++i) {
        if (p[i] != 0u)
            return 0;
    }
    return 1;
}

/* 本格 tilemap 的两个表项是否已经指向 n（说明这对 tile 就是本格上次
 * 写的，可以原地重用，不算「别人的」）。 */
static int grid_cell_points_to(TextPrinter *win, unsigned col, unsigned n)
{
    const uint8_t *tpl = win_template(win);
    const uint16_t *map;
    unsigned ty;

    if (!tpl)
        return 0;
    map = (const uint16_t *)(const void *)(uintptr_t)win_u32(tpl, TPL_TILEMAP);
    if (!map || col >= GRID_TILEMAP_W)
        return 0;
    ty = grid_cursor_ty(win);
    if (ty + 1u >= GRID_TILEMAP_W)
        return 0;
    if (grid_tilemap_entry(map, col, ty) != n)
        return 0;
    if (grid_tilemap_entry(map, col, ty + 1u) != n + 1u)
        return 0;
    return 1;
}

/* n 是否为**任一 band**里「别的列」的纯函数本征 tile。
 *
 * 图鉴：同 band 内编号（8px 规避）抢名字列本征 →「No00妙」。
 * 背包：只禁同 band 时，× 会迁到其它行 band 的本征槽；该行 12px 再按
 * 公式写回同一 tile → 数量位撞字（docs/research/BAG_LIST_TILE_COLLISION.md）。
 *
 * 公式区 [TB+2, TB+2+8*62) 内每个偶对都是某 (band,col) 的本征槽；
 * 8px 规避不得占用「非本格」的本征对。规避失败则回退本征（见 resolved 末尾）。 */
static int grid_tile_is_other_col_natural(TextPrinter *win, unsigned n,
                                          unsigned except_col)
{
    uint16_t tb = win_u16(win, WIN_TILE_BASE);
    unsigned arena = (unsigned)tb + 2u;
    unsigned off, band, rem, nat_col, cur_band;

    if (n < arena || (unsigned)n + 1u >= GRID_TILE_LIMIT)
        return 0;
    off = (unsigned)n - arena;
    if ((off & 1u) != 0u)
        return 0;
    if (off >= GRID_SEG_COUNT * GRID_SEG_TILES)
        return 0;
    /* 62 非整幂：用减代除，避免链入 __aeabi_uidiv */
    band = 0u;
    rem = off;
    while (rem >= GRID_SEG_TILES) {
        rem -= GRID_SEG_TILES;
        band++;
    }
    nat_col = rem >> 1;
    if (nat_col >= GRID_COLS_PER_SEG)
        return 0;
    cur_band = grid_row(win) & (GRID_SEG_COUNT - 1u);
    /* 本格本征的**存储**列（回绕行按需翻半区，见 grid_store_col） */
    if (band == cur_band
        && nat_col == grid_store_col(win, grid_row(win), except_col))
        return 0;                    /* 本格本征，允许 */
    return 1;
}

/* 在 used 位图里找一对空闲 tile（不抢其它列本征、优先 VRAM 空白）。
 * 找不到返回 0xFFFF。used 须已由 grid_tile_taken 填好。
 * 从 grid_tile_resolved 内联循环拆出，供 grid_emit 的对话分支复用
 * （训练家列表 12px 本征被占时迁址；2026-11-17 bd8540c 的一部分）。 */
static uint16_t grid_tile_find_free(TextPrinter *win, unsigned col,
                                    const uint32_t *used)
{
    unsigned n;
    uint32_t base = grid_tile_base(win);

    for (n = (unsigned)win_u16(win, WIN_TILE_BASE) + 2u; n < GRID_TILE_LIMIT;
         n += 2u) {
        if (!grid_tile_free(used, n))
            continue;
        if (grid_tile_is_other_col_natural(win, n, col))
            continue;                    /* 勿抢其它 (band,col) 本征 tile */
        if (grid_cell_points_to(win, col, n))
            return (uint16_t)n;
        if (grid_tile_vram_blank(base, n))
            return (uint16_t)n;
    }
    return 0xFFFFu;
}

/* 解析本字真正要写的 tile。ncols>1（12px 跨列、phase=4 共享列）不迁移：
   共享列左 4px 属于前一个字，换 tile 会把它丢掉。Small 字库步进 8px，
   phase 恒为 0，所以队伍/战斗等 Small 窗口全部走得到规避。 */
static uint16_t grid_tile_resolved(TextPrinter *win, unsigned col, unsigned ncols)
{
    uint32_t used[GRID_TILE_BITS / 32u];
    uint16_t t0 = grid_tile(win, col);
    uint16_t alt;

    if (ncols != 1u || win_u8(win, WIN_TEXTMODE) == 2u)
        return t0;
    if (grid_cell_points_to(win, col, t0))
        return t0;                       /* 本格自己的旧 tile，可重用 */
    if (!grid_tile_taken(win, col, t0, used) &&
        grid_tile_vram_blank(grid_tile_base(win), t0))
        return t0;
    alt = grid_tile_find_free(win, col, used);
    return (alt != 0xFFFFu) ? alt : t0;   /* 整段都满：退回纯函数 tile */
}

/* 12px 相位：从串首（或最近换行 / 清窗口）到 index 累计像素，取低 3 位。
 * 零 EWRAM 状态 —— 原版 tm0 用 TILE_OFFSET 累加器，这里连累加器都不要。
 * FC 参数必须按类型跳过，否则颜色/字体号字节会被误当成 PCS 或 F7 前缀。 */
static unsigned fc_arg_count(uint8_t type)
{
    switch (type) {
    case FC_FG:
    case FC_BG:
    case FC_SHADOW:
    case FC_PALETTE:
    case FC_FONT:
    case FC_PAUSE:
    case FC_SHIFT_TILE_X:
    case FC_SHIFT_TILE_Y:
        return 1u;
    case FC_ALLCOLORS:
        return 3u;
    case FC_PLAYBGM:
    case FC_PLAYSE:
        return 2u;
    default:
        return 0u;   /* FC_ESCAPE 的被转义字节留给下一轮当普通 token 计宽 */
    }
}

static unsigned grid_phase_adv(const uint8_t *text, uint16_t index, unsigned adv)
{
    unsigned w = 0u;
    uint16_t i = 0u;

    if (!text)
        return 0u;
    while (i < index) {
        uint8_t c = text[i];
        if (c == 0xFFu)
            break;
        if (c == 0xFEu || c == 0xFBu) {       /* 换行 / 等待清屏：相位归零 */
            w = 0u;
            ++i;
            continue;
        }
        if (c == 0xFCu) {
            uint8_t type = (i + 1u < index) ? text[i + 1u] : 0u;
            if (type == FC_CLEARWINDOW)
                w = 0u;
            i = (uint16_t)(i + 2u + fc_arg_count(type));
            continue;
        }
        if (c == 0xF7u && i + 1u < index && text[i + 1u] == 0u) {
            w += adv;
            i = (uint16_t)(i + 4u);
            continue;
        }
        if (c >= PCS_CTRL_BASE) {              /* FA / FD 等控制码：0px */
            ++i;
            continue;
        }
        w += CHS_GLYPH_ADVANCE_JP_PX;
        ++i;
    }
    return w & 7u;
}

/* 按窗口字体号选宽度算相位（Small 窗必须用 8，否则整行错位）。 */
static unsigned grid_phase_for(TextPrinter *win, const uint8_t *text, uint16_t index)
{
    uint8_t fn = win_u8(win, WIN_FONTNUM_REAL);
    return grid_phase_adv(text, index,
                          (fn == 2u || fn == 4u) ? CHS_GLYPH_ADVANCE_SMALL
                                                 : CHS_GLYPH_ADVANCE_PX);
}

/* GBA VRAM 禁止 byte 写：一列 64B 一律 32bit 读写。 */
static void grid_pair_load(uint8_t *p, uint32_t addr)
{
    uint32_t *d = (uint32_t *)(void *)p;
    const uint32_t *s = (const uint32_t *)(const void *)(uintptr_t)addr;
    unsigned i;
    for (i = 0u; i < GRID_PAIR_BYTES / 4u; ++i)
        d[i] = s[i];
}

static void grid_pair_store(const uint8_t *p, uint32_t addr)
{
    uint32_t *d = (uint32_t *)(void *)(uintptr_t)addr;
    const uint32_t *s = (const uint32_t *)(const void *)p;
    unsigned i;
    for (i = 0u; i < GRID_PAIR_BYTES / 4u; ++i)
        d[i] = s[i];
}

/* 4bpp 低半字节 = 左像素（字库与 VRAM 同口径）。 */
static uint8_t grid_pair_px(const uint8_t *p, unsigned x, unsigned y)
{
    unsigned off = ((y >= 8u) ? 32u : 0u)
                 + (y & 7u) * 4u + ((x & 7u) >> 1);
    uint8_t b = p[off];
    return (x & 1u) ? (uint8_t)(b >> 4) : (uint8_t)(b & 0xFu);
}

static void grid_pair_set(uint8_t *p, unsigned x, unsigned y, uint8_t v)
{
    unsigned off = ((y >= 8u) ? 32u : 0u)
                 + (y & 7u) * 4u + ((x & 7u) >> 1);
    uint8_t b = p[off];
    if (x & 1u)
        p[off] = (uint8_t)((b & 0x0Fu) | (uint8_t)(v << 4));
    else
        p[off] = (uint8_t)((b & 0xF0u) | (uint8_t)(v & 0xFu));
}

/* 字库 128B = TL(0) BL(32) TR(64) BR(96)，16×16 槽。 */
static uint8_t grid_glyph_px(const uint8_t *g, unsigned x, unsigned y)
{
    unsigned tile = (x >> 3) * 2u + (y >> 3);
    unsigned off = tile * 32u + (y & 7u) * 4u + ((x & 7u) >> 1);
    uint8_t b = g[off];
    return (x & 1u) ? (uint8_t)(b >> 4) : (uint8_t)(b & 0xFu);
}

static void grid_copy32(uint8_t *dst, const uint8_t *src)
{
    uint32_t *d = (uint32_t *)(void *)dst;
    const uint32_t *s = (const uint32_t *)(const void *)src;
    unsigned i;
    for (i = 0u; i < 8u; ++i)
        d[i] = s[i];
}

/* =====================================================================
 * §3 目标格与发射
 * ===================================================================== */
struct GridTarget {
    uint32_t base;      /* VRAM 字库区基址（tpl+0x0C）或 tm2 缓冲（win+0x20） */
    unsigned cx;        /* 窗左缘列 curX */
    unsigned col;       /* 绝对列 = cx + cursorTileX */
    unsigned rel;       /* 初始 cursorTileX（tm2 缓冲按它线性排布） */
    int buffered;       /* 缓冲直绘：不写 tilemap */
};

static int grid_setup(TextPrinter *win, GridTarget *t)
{
    const uint8_t *tpl = win_template(win);

    t->cx  = win_u8(win, WIN_CURSOR_X);
    t->rel = win_u8(win, WIN_CURSOR_TILE_X);
    t->col = t->cx + t->rel;
    t->buffered = (win_u8(win, WIN_TEXTMODE) == 2u)
               || (tpl != 0 && win_u32(tpl, TPL_TILEMAP) == 0u);
    t->base = t->buffered ? win_u32(win, WIN_TILE_DATA)
                          : (tpl ? *(const uint32_t *)(const void *)(tpl + TPL_TILE_DATA) : 0u);
    return t->base != 0u && t->col < GRID_COLS_PER_SEG;
}

/* 与 grid_setup 的 buffered 判定同口径（textMode 2，或模板无 tilemap）。 */
static int grid_is_buffered(TextPrinter *win)
{
    const uint8_t *tpl = win_template(win);

    return (win_u8(win, WIN_TEXTMODE) == 2u)
        || (tpl != 0 && win_u32(tpl, TPL_TILEMAP) == 0u);
}

/* 前向声明：grid_fill_blank_cell 需要它（定义在 §3 末尾） */
static uint8_t grid_bg(TextPrinter *win);

/* buffered 窗的空白格：把当前光标那一格的缓冲字节刷成背景色并推进一格。
 *
 * 只用于 8px 单列字（fontNum 2/4）的 buffered 窗，例如战斗血条的 HP 数字。
 * 为什么必须刷（BUG-5）：HP 串首字符是空格 0x00，若不刷就保留上一条串
 * （等级）留在同一位置的字模 → 等级 36 的首位「3」变成 HP 的 377。
 * 为什么刷满 GRID_PAIR_BYTES 是安全的：buffered 不写 tilemap，8px 字只占
 * 一个 tile 列，不存在 12px 跨列共享左 4px 的问题（见 grid_load 注释）。 */
static void grid_fill_blank_cell(TextPrinter *win)
{
    uint32_t addr = win_u32(win, WIN_TILE_DATA)
                  + (uint32_t)win_u8(win, WIN_CURSOR_TILE_X) * GRID_PAIR_BYTES;
    uint8_t bg = grid_bg(win);
    uint32_t v = (uint32_t)bg * 0x11111111u;
    uint32_t *d = (uint32_t *)(uintptr_t)addr;
    unsigned i;

    for (i = 0u; i < GRID_PAIR_BYTES / 4u; ++i)
        d[i] = v;
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
}

/* =====================================================================
 * 行尾残留清理（BUG-11，2026-11-23）
 *
 * 现象：存档确认框第一行「要把至今为止的活跃表现」右侧多出一串半截假名，
 *   而 origin 同位置是空白。
 *
 * 根因（动态实测）：原版这句日文更长，第一行占满 col4..25；汉化后 12px
 *   汉字各占 2 列，同样的 12 个字只排到 col20。col21..25 这 5 个格子的
 *   tilemap 表项是**原版那一轮打印留下的**（`474..478`），我们这轮既没
 *   覆盖它们、也没清掉。而「现」字占的 `0x1DB/0x1DC`（band7 col19 本征）
 *   正好等于 col22/23 指着的那两项 ⇒ 那两格也显示「现」。
 *
 * 为什么不能靠「迁址」绕开：`grid_tile_find_free` 只肯用「非本征」空位，
 *   而公式区 3..498 被 8 band × 31 列正好占满，全被
 *   grid_tile_is_other_col_natural 禁掉 ⇒ 永远 0xFFFF（实测 alt=65535）。
 *
 * ── 判据（三次实测收敛，前两版都有严重副作用）──────────────────
 *   ① 在 0xFF 清 → 开始菜单 8 项全消失（菜单是「一项一次独立打印」，
 *      每项以 0xFF 结束且光标已回行首，整行被抹平）。
 *   ② 在 0xFE 清、从光标列清到表宽 → 背包列表第 6/7 项被削
 *      （y=104..119 实测）。背包列表行内也带 0xFE，光标右侧还有
 *      **同一行尚未打印**的列。
 *
 *   最终判据：从光标列往右，只清**连续指向公式区**（TB+2 .. TB+2+8*62）
 *   的格子；遇到非公式区（空白 tile / 框体装饰 / UI 图标）立刻停。
 *   实测依据：
 *     · 存档框 col21..25 = 474..478 全在公式区 → 清掉，残字消失；
 *       col26 起 = 623/625/622 是框体装饰（原版也有）→ 停，装饰不受损。
 *     · 背包列表 col20 起就是空白 tile 1 → 立刻停，列表不被误削
 *       （第二版「从光标清到表宽」曾把滚动帧削掉 822 px）。
 * ===================================================================== */
static void grid_clear_row_tail(TextPrinter *win)
{
    const uint8_t *tpl = win_template(win);
    uint16_t *map;
    unsigned ty, x, blank, arena, arena_end, start;
    uint16_t tb;

    if (!tpl || grid_is_buffered(win))
        return;
    map = (uint16_t *)(void *)(uintptr_t)win_u32(tpl, TPL_TILEMAP);
    if (!map)
        return;

    tb = win_u16(win, WIN_TILE_BASE);
    blank = (unsigned)tb + 1u;
    arena = (unsigned)tb + 2u;
    arena_end = arena + GRID_SEG_COUNT * GRID_SEG_TILES;
    ty = grid_cursor_ty(win);
    start = (unsigned)win_u8(win, WIN_CURSOR_X)
          + (unsigned)win_u8(win, WIN_CURSOR_TILE_X);
    /* 从光标格的**下一格**开始清：光标格可能正是本行最后一个字
     * （12px 的第二列），碰它会把字削掉（实测 col20 被清成空白，
     * 正是「现」的右半列）。 */
    if (start + 1u < GRID_TILEMAP_W)
        start += 1u;

    /* 光标右侧：只清「指向公式区」的连续段；遇到非公式区（空白 tile、
     * 框体装饰 tile、UI 图标）就停。这一条是三次实测收敛出来的：
     *   · 存档框：col21..25 = 474..478（都在公式区）→ 清；
     *             col26 起 = 623/625/622（框体装饰）→ 停，装饰不受损。
     *   · 背包列表：col20 起就是空白 tile 1 → 立刻停，列表不再被误削。 */
    for (x = start; x < GRID_TILEMAP_W; ++x) {
        unsigned v0 = grid_tilemap_entry(map, x, ty);
        unsigned v1 = grid_tilemap_entry(map, x, ty + 1u);

        /* 只用上半行（ty）判停：12px 字的**离屏副本**落在 ty+1 行，
         * 那里的表项会指向公式区之外（实测存档框 r16 col21 = 504），
         * 拿它判停会导致一格都清不掉。 */
        if (v0 < arena || v0 >= arena_end)
            break;                    /* 非公式区：属于框体/UI，停手 */

        grid_tilemap_set(map, x, ty, (uint16_t)blank);
        /* 下半行只在它确实指向公式区时才一并清，避免误伤离屏副本。 */
        if (v1 >= arena && v1 < arena_end)
            grid_tilemap_set(map, x, ty + 1u, (uint16_t)blank);
    }
}

#ifdef GRID_DIAG
static void diag_write(unsigned slot, const uint8_t *r)
{
    volatile uint8_t *p =
        (volatile uint8_t *)(uintptr_t)(DIAG_BASE + slot * DIAG_RECB);
    unsigned i;
    for (i = 0u; i < DIAG_RECB; ++i)
        p[i] = r[i];
}

static unsigned diag_slot(void)
{
    volatile uint32_t *seqp =
        (volatile uint32_t *)(uintptr_t)(DIAG_BASE + DIAG_SEQP);
    uint32_t seq = *seqp;
    *seqp = seq + 1u;
    return (unsigned)(seq & (DIAG_RECS - 1u));
}

static void diag_emit(unsigned tag, unsigned code, unsigned phase,
                      TextPrinter *win, const GridTarget *t, unsigned t0,
                      unsigned fg, unsigned bg)
{
    const uint8_t *tpl = win_template(win);
    uint32_t textptr = win_u32(win, WIN_TEXT_PTR);
    uint8_t r[DIAG_RECB];
    unsigned i;
    for (i = 0u; i < DIAG_RECB; ++i)
        r[i] = 0u;
    r[0] = (uint8_t)tag;
    r[1] = (uint8_t)(code & 0xFFu);
    r[2] = (uint8_t)((code >> 8) & 0xFFu);
    r[3] = (uint8_t)phase;
    r[4] = (uint8_t)t->cx;
    r[5] = (uint8_t)t->rel;
    r[6] = (uint8_t)t->col;
    r[7] = (uint8_t)((win_u8(win, WIN_FONTNUM_REAL) & 0x7Fu)
                     | (t->buffered ? 0x80u : 0u));   /* 低7位 = fontNum */
    r[8] = (uint8_t)(t0 & 0xFFu);
    r[9] = (uint8_t)((t0 >> 8) & 0xFFu);
    r[10] = (uint8_t)fg;
    r[11] = (uint8_t)bg;
    r[12] = win_u8(win, WIN_COLOR_C);
    r[13] = win_u8(win, WIN_COLOR_D);
    r[14] = win_u8(win, WIN_COLOR_E);
    r[15] = win_u8(win, WIN_PALETTE);
    if (tpl) {
        r[16] = tpl[5];
        r[17] = tpl[6];
        r[18] = tpl[7];
        r[19] = tpl[8];
    }
    r[20] = (uint8_t)(textptr & 0xFFu);
    r[21] = (uint8_t)((textptr >> 8) & 0xFFu);
    r[22] = (uint8_t)((textptr >> 16) & 0xFFu);
    r[23] = (uint8_t)((textptr >> 24) & 0xFFu);
    /* BUG-11 诊断：把撞车规避的判定输入一起记下来。
     *   r[7] bit7 = buffered；这里借用 t->buffered 之后的空闲位不现实，
     *   改用 r[19]（tpl[8]，本就在 BUG-11 排查中无用）存标志：
     *     bit0 = dialogue 判据是否成立
     *     bit1 = grid_tile_taken 是否判「t0/t0+1 被别人引用」
     *   只在 GRID_DIAG 构建里存在。 */
    {
        int _dlg = (grid_cursor_ty(win) >= 14u
                    && win_u8(win, WIN_CURSOR_X) < 20u);
        uint32_t _used[GRID_TILE_BITS / 32u];
        int _tk = grid_tile_taken(win, t->col,
                                  grid_tile(win, t->col), _used);
        r[19] = (uint8_t)((_dlg ? 1u : 0u) | (_tk ? 2u : 0u));
    }
    diag_write(diag_slot(), r);
}

/* 控制码 / 越界保护只占一条记录，code 塞 t0 或控制码。 */
static void diag_ctrl(unsigned tag, unsigned code, uint16_t index)
{
    uint8_t r[DIAG_RECB];
    unsigned i;
    for (i = 0u; i < DIAG_RECB; ++i)
        r[i] = 0u;
    r[0] = (uint8_t)tag;
    r[1] = (uint8_t)(code & 0xFFu);
    r[2] = (uint8_t)((code >> 8) & 0xFFu);
    r[14] = (uint8_t)(index & 0xFFu);
    r[15] = (uint8_t)((index >> 8) & 0xFFu);
    diag_write(diag_slot(), r);
}

/* tag=2：真正写进 VRAM 前一刻的快照。r[1..2]=t0，r[8..11]=p0 第 0 行，
 * r[12..15]=p0 第 3 行，r[16..19]=p0 第 4 行（用于确认「写的是不是这个字」）。 */
static void diag_store(unsigned t0, const uint8_t *p0)
{
    uint8_t r[DIAG_RECB];
    unsigned i;
    for (i = 0u; i < DIAG_RECB; ++i)
        r[i] = 0u;
    r[0] = 2u;
    r[1] = (uint8_t)(t0 & 0xFFu);
    r[2] = (uint8_t)((t0 >> 8) & 0xFFu);
    for (i = 0u; i < 4u; ++i) {
        r[8u + i] = p0[i];
        r[12u + i] = p0[12u + i];
        r[16u + i] = p0[16u + i];
    }
    diag_write(diag_slot(), r);
}
#endif

/* 背包列表 tpl（GDB）；列表内底在 tile Y=16/17，Y≥18 是框底/箭头带。 */
#define BAG_LIST_TEMPLATE 0x081BB544u

static int grid_is_bag_list(TextPrinter *win)
{
    const uint8_t *tpl = win_template(win);

    return tpl != 0
        && (((uintptr_t)tpl & ~1u) == (uintptr_t)BAG_LIST_TEMPLATE);
}

/* 把两列 64B 写回 VRAM/缓冲，并给每列写一次 tilemap 表项。
 * 非缓冲时若 tile 号会越过 0x1F0（UI 图标段）→ 整字不写，只推进游标。
 *
 * 12px（ncols>1）不能迁 tile（phase=4 共享列）；若本征对已被**其它
 * tilemap 格**占用（典型：row&7 别名让 y=18 与 y=2 抢 band1），再写会
 * 把上一行墨迹踩成「钢翼机关枪 / 闭背包」类串行。此时只推进游标、不写
 * VRAM/表项 —— 溢出行宁可缺字，也不毁已占用行。
 *
 * 背包列表 Y≥18：原版列表底在 16；写到 18 会渗黄框外并踩背包图 tile
 *（切招式页再切回撞 UI）。只推进、不写。 */
static void grid_emit(TextPrinter *win, GridTarget *t,
                      const uint8_t *p0, const uint8_t *p1,
                      unsigned ncols, unsigned delta)
{
    unsigned c;
    uint16_t t0;
    uint32_t used[GRID_TILE_BITS / 32u];
    int bag = grid_is_bag_list(win);
    int dialogue = (grid_cursor_ty(win) >= 14u
                    && win_u8(win, WIN_CURSOR_X) < 20u);

    if (!t->buffered) {
        /* === textMode 0：直写 TB+TILE_OFFSET，完全绕开网格与冲突规避 ===
         * 依据见 grid_tile_linear 上方 GDB 实测表与反汇编。
         * 只有 textMode 1 需要分配 tile；textMode 0 是纯累加器直写。 */
        if (win_u8(win, WIN_TEXTMODE) == 0u) {
            uint16_t lt = grid_tile_linear(win);

            /* 只做 10-bit tile 号硬边界保护，不迁址、不找空位。
             * 越界说明模板 TB 本身配错，不该由渲染层兜。 */
            if ((unsigned)lt + 2u * ncols > GRID_TILE_BITS) {
                diag_ctrl(3u, (uint32_t)lt, 0u);
                win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(t->rel + delta));
                return;
            }
            grid_pair_store(p0, t->base + 32u * lt);
            if (ncols > 1u)
                grid_pair_store(p1, t->base + 32u * (lt + 2u));
            for (c = 0u; c < ncols; ++c) {
                /* 屏幕列与 tile 严格同步：第 c 列写到 col+c、指向 lt+2c */
                win_set_u8(win, WIN_CURSOR_TILE_X,
                           (uint8_t)(t->rel + c));
                UpdateTilemap_PreserveCursorX(win,
                    (uint16_t)(lt + 2u * c), (uint16_t)(lt + 2u * c + 1u));
            }
            /* 推进：TILE_OFFSET += 2*delta（铁律 ②，换行时游戏不清零，
             * 所以累加即正确，与 origin 逐字一致）。 */
            win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(t->rel + delta));
            win_set_u16(win, WIN_TILE_OFFSET,
                        (uint16_t)(win_u16(win, WIN_TILE_OFFSET)
                                   + 2u * delta));
            return;
        }

        if (bag
            && (grid_cursor_ty(win) >= 18u
                || (ncols > 1u
                    && t->col + (ncols - 1u) >= 26u))) {
            win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(t->rel + delta));
            return;
        }
        t0 = grid_tile_resolved(win, t->col, ncols);
        if ((unsigned)t0 + 2u * (ncols - 1u) + 2u > GRID_TILE_LIMIT) {
            diag_ctrl(3u, (uint32_t)t0, 0u);
            win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(t->rel + delta));
            return;                                   /* 保护 UI 图标，宁可不显示 */
        }
        if (ncols > 1u
            && !grid_cell_points_to(win, t->col, t0)
            && grid_tile_taken(win, t->col, t0, used)) {
            if (bag) {
                diag_ctrl(6u, (uint32_t)t0, 1u);   /* BUG-11：bag 分支拦截 */
                win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(t->rel + delta));
                return;
            }
            if (dialogue) {
                uint16_t alt = grid_tile_find_free(win, t->col, used);
                diag_ctrl(6u, (uint32_t)alt, 2u);  /* BUG-11：记录 alt */
                if (alt != 0xFFFFu
                    && (unsigned)alt + 2u * (ncols - 1u) + 2u
                       <= GRID_TILE_LIMIT)
                    t0 = alt;
            } else {
                diag_ctrl(6u, (uint32_t)t0, 3u);   /* BUG-11：非对话，写本征 */
            }
            /* 非对话：写本征 */
        }
        diag_store(t0, p0);
        grid_pair_store(p0, t->base + 32u * t0);
        if (ncols > 1u)
            grid_pair_store(p1, t->base + 32u * (t0 + 2u));
        for (c = 0u; c < ncols; ++c) {
            /* UpdateTilemap 按 (curX+curTX) 找表项；两列要分别写。
             * PreserveCursorX 防止原生函数把窗左缘 curX 推歪。 */
            win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(t->col + c - t->cx));
            UpdateTilemap_PreserveCursorX(win,
                (uint16_t)(t0 + 2u * c), (uint16_t)(t0 + 2u * c + 1u));
        }
    } else {
        uint32_t addr = t->base + (uint32_t)t->rel * GRID_PAIR_BYTES;
        grid_pair_store(p0, addr);
        if (ncols > 1u)
            grid_pair_store(p1, addr + GRID_PAIR_BYTES);
    }
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(t->rel + delta));
}

/* §3 末尾定义（grid_bg 之后），此处前置声明供 grid_load 使用。 */
static void grid_pair_fill(uint8_t *p, uint8_t bg);

/* 两列一律先铺成「窗口背景色」，不继承 VRAM 里的旧内容。
 *
 * 盒外像素若是读回的日文字库预渲染背景、或游戏别处载入的图形（彩色
 * nibble），会当成字缝里的白块/绿蓝条纹显示（V1 实证）。
 * 只有 phase=4 时第 0 列的左 4px 属于**前一个字**，需把它刚写下的墨迹
 * 挑回来，其余一律是背景色。 */
static void grid_load(TextPrinter *win, GridTarget *t,
                      uint8_t *p0, uint8_t *p1,
                      unsigned ncols, unsigned phase, uint8_t bg)
{
    unsigned x, y;
    uint32_t tmp[GRID_PAIR_BYTES / 4u];
    uint8_t *q = (uint8_t *)(void *)tmp;
    uint32_t addr;

    grid_pair_fill(p0, bg);
    grid_pair_fill(p1, bg);
    if (phase == 0u)
        return;

    if (!t->buffered) {
        /* phase>0：左 4px 属上一字右缘；上一字可能已迁离本征，读 tilemap 实指。 */
        const uint8_t *tpl = win_template(win);
        const uint16_t *map;
        uint16_t t0 = (win_u8(win, WIN_TEXTMODE) == 0u)
                    ? grid_tile_linear(win)
                    : grid_tile(win, t->col);
        unsigned ty = grid_cursor_ty(win);
        unsigned hi = (win_u8(win, WIN_TEXTMODE) == 0u)
                    ? GRID_TILE_BITS : GRID_TILE_LIMIT;

        if (tpl) {
            map = (const uint16_t *)(const void *)
                (uintptr_t)win_u32(tpl, TPL_TILEMAP);
            if (map && t->col < GRID_TILEMAP_W && ty < GRID_TILEMAP_W) {
                unsigned v = grid_tilemap_entry(map, t->col, ty);
                if (v != 0u && v < hi)
                    t0 = (uint16_t)v;
            }
        }
        if ((unsigned)t0 + 2u * (ncols - 1u) + 2u > hi)
            return;
        addr = t->base + 32u * t0;
    } else {
        addr = t->base + (uint32_t)t->rel * GRID_PAIR_BYTES;
    }
    grid_pair_load(q, addr);
    for (y = 0u; y < 16u; ++y) {
        for (x = 0u; x < 4u; ++x) {
            uint8_t v = grid_pair_px(q, x, y);
            if (v != 0u && v != bg)
                grid_pair_set(p0, x, y, v);
        }
    }
}

static uint8_t grid_fg(TextPrinter *win)
{
    /* C = win[0x0C]：前景（主墨）。FC 01 可动态改，InitTextPrinter 从
     * tpl[5] 拷入，六场景 DIAG 实测常态 C=1。
     * 反例：开始菜单玩家名一行 C=14（FC 01 0E），旧实现
     *   `FontIsShadowed(fn) ? 1 : tpl[5]`
     * 把动态改色整段吞掉，那 9 个字全被画成 1 —— 正是「继续游戏菜单
     * 颜色不对」的根因。字模里 15 号 nibble 对应 C，见 FONT_12PX_DRAW.md。 */
    return win_u8(win, WIN_COLOR_C);
}

static uint8_t grid_shadow(TextPrinter *win)
{
    /* E = win[0x0E]：阴影。六场景 DIAG 实测恒为 8，tpl[7]=8。
     * origin 预载字模是 {15 背景 / 1 主墨 / 8 阴影} 三色；V1~V5 的
     * ink-only 重映射把 14/15 一律折成 fg，阴影层整片消失，日文假名
     * 与玩家名因此变粗发黑（「1井」）、菜单整体比 origin 暗一档。 */
    return win_u8(win, WIN_COLOR_E);
}

/* 空白像素必须写**窗口背景色索引**，不能写 0（透明）。
 * 依据 FONT_12PX_DRAW.md：原版 CopyGlyph2bppTo4bpp 的映射是
 * 「15→C(主墨) 14→E(阴影) 0→D(背景)」—— 0 被映射成背景色，
 * 预渲染字模整体不透明。写 0 会让文字 tile 透出下层 BG：
 *   V2 实证：对话「欢迎」变黑底（palette0=#000000）；
 *   V1 实证：字缝里露出地图绿/蓝条纹与残留白块。
 * win[0x0D] = backgroundColor（FC 02 可改），InitTextPrinter 从 tpl[6] 拷入。
 *
 * 训练家之眼左侧 tpl@0x081BB7B4（id 0x25）的 tpl[6]=0xF，映成浅粉≠面板粉；
 * 仅该模板返回透明 0。禁止用 .bss 锁：game.ld 无 RAM，bss 落 ROM 读到 0xFF
 * 会变成「全局永远 bg=0」（标题/开始菜单透底回归）。 */
#define TPL_POKENAV_TRAINER_EYE_LEFT  0x081BB7B4u

static uint8_t grid_bg(TextPrinter *win)
{
    const uint8_t *tpl = win_template(win);

    if ((uintptr_t)tpl == TPL_POKENAV_TRAINER_EYE_LEFT)
        return 0u;

    /* textMode 0（战斗对话/主菜单/招式）：用 win[0x0D] = D = 背景色。
     *
     * GDB 实测 origin 侧（battle_menu_audit 20261119T171208）三个战斗窗的
     * 真实配色（只统计「真正打印文字」时的样本）：
     *
     *   对话窗 TB=0x1B8  27 次  色 C/D/E=1/15/8   pal=0
     *   菜单窗 TB=0x190  42 次  色 C/D/E=13/14/15 pal=5
     *   招式窗 TB=0x2C0  18 次  色 C/D/E=13/14/15 pal=5
     *
     * 而「白底」在各自调色板里的索引：
     *   pal0 → 15 是白（idx1/idx5 也白，但 D 取 15）
     *   pal5 → 14 是白（15 是 (213,213,205) 灰！）
     *
     * ⇒ **D 就是背景色**，两个窗各自都对；照搬 tpl[6] 在菜单/招式窗会拿到
     *   15 = 灰，屏幕上就是「菜单项背后一块灰」（用户截图 2026-11-19）。
     *
     * 为什么不影响其他 textMode：图鉴滚动时 FC 会把 win[0x0D] 临时改成 2(红)
     * 画高亮，若拿它铺整列 64B 会把 12px 共享列里前一字的右半染红
     * （VRAM 实证 tile 16B..171 主色 nibble=2）。所以只有 textMode 0 用它，
     * 其余仍认模板背景。 */
    if (win_u8(win, WIN_TEXTMODE) == 0u)
        return win_u8(win, WIN_COLOR_D);

    /* textMode 2（buffered 缓冲直绘）：必须用运行时 win[0x0D]，不能用 tpl[6]。
     *
     * 血条模板 0x081BB40C 的 tpl[6]=0（透明），但运行时字符串以
     * `fc 01 01 fc 02 02` 开头，把 C 设为 1、**D 设为 2**：
     *   GDB 实测 origin 侧 win=0x020231CC：42 次 色C/D/E=1/2/3，
     *   另有 17 次 1/0/3（未设色的短串）。
     * 若这里返回 tpl[6]=0，空格刷成「透明 0」等于没清，BUG-5 修不掉。
     * buffered 窗不写 tilemap、8px 字不跨列共享，所以用 win[0x0D] 安全
     * （没有图鉴那种「共享列被染红」的风险）。 */
    if (win_u8(win, WIN_TEXTMODE) == 2u)
        return win_u8(win, WIN_COLOR_D);

    /* 预载字模的背景是**窗口模板的固定色**，不是当前绘制色。
     * GRID_DIAG 六场景实测：对话/选项/导航/开始菜单 tpl[6]=0xF(白)，
     * 图鉴/背包 tpl[6]=0(透明，露出下层气泡)，且除 FC 临时改色外
     * win[0x0D] 恒等于 tpl[6]。
     * 图鉴滚动时 FC 会把 win[0x0D] 改成 2(红) 画一小段高亮；若拿它铺
     * 整列 64B，会把 12px 共享列里前一个汉字的右半整片染成纯红方块
     * （VRAM 实证：tile 16B..171 主色 nibble=2）。故只认模板背景。 */
    if (tpl)
        return tpl[6];
    return win_u8(win, WIN_COLOR_D);
}

static void grid_pair_fill(uint8_t *p, uint8_t bg)
{
    uint32_t *d = (uint32_t *)(void *)p;
    uint32_t v = (uint32_t)bg * 0x11111111u;
    unsigned i;
    for (i = 0u; i < GRID_PAIR_BYTES / 4u; ++i)
        d[i] = v;
}

/* =====================================================================
 * §4 两个绘制入口
 * ===================================================================== */
/* 按 fontNum 选中文 BDF 字库。
 *
 * 为什么必须分（2026-11-12 实测）：队伍列表 / 战斗名走 fontNum=4（Small），
 * 窗口排版按 8px/格算好，而 Normal 是 12px 墨迹。旧代码无条件用 Normal +
 * 12px 推进，等于把 12px 字硬塞进 8px 格排版里 —— 实机就是名字散架、
 * 笔画错位、并覆盖邻格（party 场景 y96 带 origin 与 translated 差异成片）。
 *
 * fontNum 语义（game.h FontIsShadowed + FontSubTable）：
 *   0/1/2/6 → 1bpp 普通；3/4/5 → shadowed 4bpp。
 *   其中 2/4 是「小字」档（Small 字库，8px 步进），其余用 Normal。
 * MIDDLE（大字号）当前没有 fontNum 映射到它，保留常量备用。
 */
static const uint8_t *grid_font_for(uint8_t font_num, unsigned *advance)
{
    if (font_num == 2u || font_num == 4u) {
        *advance = CHS_GLYPH_ADVANCE_SMALL;          /* 8px */
        return (const uint8_t *)(uintptr_t)ADDR_FONT_CHS_SMALL;
    }
    *advance = CHS_GLYPH_ADVANCE_PX;                 /* 12px */
    return (const uint8_t *)(uintptr_t)GRID_FONT_NORMAL;
}

/* 汉字：墨迹按 phase 铺到 1~2 个 tile 列。
 * 盒内像素先清 0 再写墨迹 —— 既去掉重印残留，又天然保留共享列邻字的余量。 */
static void grid_draw_chs(TextPrinter *win, uint16_t gidx, unsigned phase)
{
    GridTarget t;
    uint32_t buf[(2u * GRID_PAIR_BYTES) / 4u];
    uint8_t *p0 = (uint8_t *)(void *)buf;
    uint8_t *p1 = p0 + GRID_PAIR_BYTES;
    unsigned sx, sy, ncols, delta;
    uint8_t fg, bg, sh;
    const uint8_t *g;
    unsigned adv;
    const uint8_t *font = grid_font_for(win_u8(win, WIN_FONTNUM_REAL), &adv);

    ncols = (phase + adv + 7u) >> 3;                     /* 1 或 2 列承载 */
    delta = (phase + adv) >> 3;                          /* Small: 恒 1 */
    if (!grid_setup(win, &t) || gidx >= GRID_GLYPH_SLOTS) {
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + delta));
        return;
    }
    g = font + (uint32_t)gidx * GRID_GLYPH_BYTES;
    fg = grid_fg(win);
    bg = grid_bg(win);
    sh = grid_shadow(win);
    diag_emit(0u, gidx, phase, win, &t, grid_tile(win, t.col), fg, bg);

    grid_load(win, &t, p0, p1, ncols, phase, bg);
    /* 阴影层：origin 的 tm1 预载字模是「C 主墨 + E 右下 1px 阴影 + D 背景」
     * 三色预渲染（pal9/pal15 实测 1/8/15）。12px 汉字字库只有 0/15 单色，
     * 若只写 C，整屏汉字比 origin 少一整层墨迹 → 菜单发灰、发细、颜色对不上。
     * 按同一语义程序化补影：墨迹右下 1px 先铺 E，再写 C 压在上面。
     * 不是 DONT.md §9 禁止的 `colors[0]=bg+OR`（那会把背景混进墨色糊成重影），
     * 这里是显式三色独立像素。 */
    for (sy = 0u; sy + 1u < 16u; ++sy) {
        for (sx = 0u; sx < GRID_INK_W; ++sx) {
            unsigned dx = phase + sx + 1u;
            uint8_t *p;
            if (!grid_glyph_px(g, sx, sy) || dx >= ncols * 8u)
                continue;
            p = (dx >> 3) ? p1 : p0;
            grid_pair_set(p, dx & 7u, sy + 1u, sh);
        }
    }
    for (sy = 0u; sy < 16u; ++sy) {
        for (sx = 0u; sx < GRID_INK_W; ++sx) {
            unsigned dx = phase + sx;
            uint8_t *p = (dx >> 3) ? p1 : p0;
            uint8_t v = grid_glyph_px(g, sx, sy);
            /* 背景已由 grid_pair_fill 铺满；此处不能再写 bg，否则会把上一步
             * 刚补的阴影层整片洗掉。只在主墨像素上写 C。 */
            if (v)
                grid_pair_set(p, dx & 7u, sy, fg);
        }
    }
    grid_emit(win, &t, p0, p1, ncols, delta);
}

/* PCS 单字节：句读 0x36..0x3E 读 CHS Sym（与 Wokann 增益版同构）；
 * 其余从原版 Font 取模展开到栈上 64B（不引用预载日文字库区，
 * 因为 [TB, TB+512) 已被本引擎按屏幕列接管），再按 phase 贴进网格。 */
static int grid_pcs_is_sym(uint8_t glyph)
{
    return glyph >= SYM_GLYPH_BASE
        && (unsigned)(glyph - SYM_GLYPH_BASE) < SYM_GLYPH_COUNT;
}

static void grid_draw_pcs(TextPrinter *win, uint8_t glyph, unsigned phase)
{
    GridTarget t;
    uint32_t tmp[GRID_PAIR_BYTES / 4u];
    uint32_t buf[(2u * GRID_PAIR_BYTES) / 4u];
    uint8_t *gp = (uint8_t *)(void *)tmp;
    uint8_t *p0 = (uint8_t *)(void *)buf;
    uint8_t *p1 = p0 + GRID_PAIR_BYTES;
    uint8_t *up = 0;
    uint8_t *lo = 0;
    uint8_t fn;
    uint8_t fg, bg, sh;
    int shadowed;
    int from_sym;
    unsigned sx, sy, ncols, delta;

    ncols = (phase + CHS_GLYPH_ADVANCE_JP_PX + 7u) >> 3;  /* 1 或 2 */
    delta = (phase + CHS_GLYPH_ADVANCE_JP_PX) >> 3;       /* 恒为 1 */
    /* 菜单光标 ▶(0xEF) **就是普通 PCS 字模**：ROM 实证 font3 0xEF 的
     * upper/lower 是三角墨迹，font0 0xEF 的 lower 是 `00 60 70 78 7c
     * 78 70 60`。origin 开始菜单把它画在 BG tile 0x128（三色预渲染）。
     * V1~V5 却特判成「固定 tile 对 0x1F0/0x1F1」并只写 tilemap，而
     * 0x1F0/0x1F1 在新引擎里从未被写入内容（VRAM 实测全 0）→ 光标整块
     * 消失。删掉特判，与其它 PCS 一样取字模展开即可。
     *
     * ★ 0x01..0x1F 绝不能再当控制码吞掉（2026-11-12 实测定案）：
     * 日版 PCS 这个区段是正常假名（`0x0A` = こ）。旧代码 `if (glyph < 0x20)
     * return;` 把它们整个跳过不画，那一格保留上次打印的残留内容 ——
     * 继续游戏菜单「55 こ」「5 こ」的计数词正是 0x0A，屏幕上就显示成
     * 箭头/ザ 等残影（用户点名的「个→箭头、只→箭头」）。
     * 官方 PrintGlyph_TextMode1 @0x0800360C 反汇编：对任何 glyph 都直接
     * 调 FontSubTable[fontNum](win,glyph) 再 cursorTileX+=1，没有任何
     * 低码位特判。这里照官方行为走，让 0x01..0x1F 正常取字模。
     * 只有 0x00（空格）保持「只推进不重绘」，与官方空白 tile 语义一致。
     * 图鉴分类行的问号擦除改在 UnusedPrintMonName 侧处理，禁止在此对
     * 0x00 整格铺背景（会削 12px 共享列 → 列表 № 与名字之间残笔）。 */
    if (glyph == 0x00u) {
        /* 空格：推进一格，textMode 0 同步 TILE_OFFSET（见下）。
         *
         * ★ textMode 2（buffered 缓冲直绘）必须**真的把这一格刷成背景**，
         * 不能只推进游标 —— BUG-5「HP 显示 377/115」的根因就在这里。
         *
         * GDB 实测 origin 侧（battle_menu_audit 20261119T180131，win=0x020231CC
         * textMode=2 fontNum=4，字节流逐字采样）：
         *
         *   第 1 串：fc 01 01 fc 02 02 a4 a7 ff     ← 等级「36」(a4=3, a7=6)
         *   第 2 串：fc 01 01 fc 02 02 00 a8 a8 ff  ← HP「 77」(00=空格, a8=7)
         *
         * 两串写进**同一块缓冲的同一段位置**。第 2 串首字符是空格 0x00，
         * 旧实现只把 cursorTileX +1、不重绘那一格 ⇒ 第 1 串等级的首位
         * 字模留在原地：Lv10 残留「1」→ HP 显示 126；Lv36 残留「3」→ 377。
         * 用户实机截图 2026-11-19 18:34 两张图正好对应这两种情况。
         *
         * 为什么这里可以整格铺背景、而 12px 汉字窗不行：
         * buffered 窗 fontNum=4 是 8px 单列字（GRID_PAIR_BYTES=64 但只占 1 列），
         * 不存在 12px 跨列共享左 4px 的问题；且 buffered 不写 tilemap，
         * 只改缓冲字节，不会削掉邻字。12px 的约束见 grid_load 注释。 */
        if (grid_is_buffered(win)) {
            grid_fill_blank_cell(win);
            return;
        }
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
        /* textMode 0 直写：空格也占一格，TILE_OFFSET 必须同步 +2。
         * origin 实证（菜单窗第 2 行 x23=0x1AA、x25=0x1AE，中间 0x1AC
         * 无人引用）—— 那正是空格消耗掉的编号。不推进的话后一字会落回
         * 前字的 tile（实测 x23/x25 同指 0x1A4，两字叠出残字）。 */
        if (win_u8(win, WIN_TEXTMODE) == 0u)
            win_set_u16(win, WIN_TILE_OFFSET,
                        (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + 2u));
        return;
    }
    if (!grid_setup(win, &t)) {
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + delta));
        return;
    }
    fn = win_u8(win, WIN_FONTNUM_REAL);
    fg = grid_fg(win);
    bg = grid_bg(win);
    sh = grid_shadow(win);
    from_sym = grid_pcs_is_sym(glyph);
    if (from_sym) {
        /* Sym：8×16 4bpp 连续 64B（上 32 + 下 32），墨迹 nibble=15。
         * 与 Font3 阴影字模不同，无 14 号阴影层 → 按非 shadowed 重映射。 */
        const uint8_t *sym = (const uint8_t *)(uintptr_t)(
            ADDR_FONT_CHS_SYM
            + (uint32_t)(glyph - SYM_GLYPH_BASE) * GRID_PAIR_BYTES);
        shadowed = 0;
        grid_copy32(gp, sym);
        grid_copy32(gp + 32u, sym + 32u);
    } else {
        shadowed = FontIsShadowed(fn);
        GetGlyphTilePointers_Origin(fn, glyph, &up, &lo);
        if (!up || !lo) {
            win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(t.rel + delta));
            return;
        }
        if (shadowed) {
            /* font3/4/5：32B/tile 的 4bpp-index 字模，nibble 语义
             *   0 = 背景(D) / 14 = 阴影(E) / 15 = 主墨(C)  ← FONT_12PX_DRAW.md
             * 原样保留，交给下面的三色重映射，绝不 ink-only 归一。 */
            grid_copy32(gp, up);
            grid_copy32(gp + 32u, lo);
        } else {
            /* font0/1/2/6：1bpp 8B/tile，原版展开函数 r2=「1 时色」r3=「0 时色」。
             * 传 (1,0) 只作墨迹标记，颜色由重映射统一决定。 */
            CopyGlyph1bppTo4bpp_Origin(up, gp, 1u, 0u);
            CopyGlyph1bppTo4bpp_Origin(lo, gp + 32u, 1u, 0u);
        }
    }
    /* 空白/填充字形：原版 tm1 只把表项指到预载的空白 tile，**不重绘 VRAM**。
     * 本引擎若照常整列铺背景，会把 phase=4 共享列里前一个 12px 汉字的
     * 右半擦掉 —— 图鉴滚动时游戏会在名字后面补打 0x20/0x80 填充字，
     * 实证把「妙蛙种子」后两字削成残笔。无墨迹 ⇒ 只推进游标。 */
    {
        unsigned i;
        int blank = 1;
        for (i = 0u; i < GRID_PAIR_BYTES; ++i) {
            uint8_t byte = gp[i];
            if ((byte & 0x0Fu) != 0u || (byte >> 4) != 0u) {
                blank = 0;
                break;
            }
        }
        if (blank) {
            win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(t.rel + delta));
            return;
        }
    }
    diag_emit(1u, glyph, phase, win, &t, grid_tile(win, t.col), fg, bg);

    grid_load(win, &t, p0, p1, ncols, phase, bg);
    for (sy = 0u; sy < 16u; ++sy) {
        for (sx = 0u; sx < 8u; ++sx) {
            unsigned dx = phase + sx;
            uint8_t *p = (dx >> 3) ? p1 : p0;
            uint8_t v = grid_pair_px(gp, sx, sy);
            /* origin 预载字模是 {15 背景 / C 主墨 / E 阴影} 三色：
             *   options  pal9  → 15 白 / 1 橙黄 / 8 深橙
             *   start_menu pal15 → 15 白 / 1 深灰 / 8 浅米
             * V1~V5 的 ink-only `v ? fg : bg` 把阴影 14 也折成主墨，
             * 笔画膨胀粘连（玩家名「ユウキ」糊成粗黑「1井」），且整片
             * 阴影丢失让菜单比 origin 暗一档。按 nibble 语义精确还原：
             *   0 → 窗口背景(tpl[6])；14 → E；其余(15/1) → C。
             * 字模里绝不会出现调色板彩色 nibble，故不会重现 V1 的
             * 蓝绿方块。 */
            uint8_t nv = (v == 0u) ? bg
                       : ((shadowed && v == 14u) ? sh : fg);
            grid_pair_set(p, dx & 7u, sy, nv);
        }
    }
    grid_emit(win, &t, p0, p1, ncols, delta);
}

/* =====================================================================
 * §5 流宽度（导出给 MapNamePopup_hook.c 做居中；协议一致）
 * ===================================================================== */
uint32_t GetStringWidth(const uint8_t *buf, uint32_t max_bytes)
{
    uint32_t w = 0u;
    uint32_t i = 0u;

    if (!buf)
        return 0u;
    while (i < max_bytes && buf[i] != 0xFFu) {
        if (buf[i] == 0xF7u && i + 3u < max_bytes && buf[i + 1u] == 0u) {
            w += CHS_GLYPH_ADVANCE_PX;
            i += 4u;
        } else if (buf[i] >= PCS_CTRL_BASE) {
            i += 1u;
        } else {
            w += CHS_GLYPH_ADVANCE_JP_PX;
            i += 1u;
        }
    }
    return w;
}

/* =====================================================================
 * §6 控制码状态机（原版语义，绘制部分不涉及）
 * ===================================================================== */
typedef void (*axv_fn1)(uint32_t);
typedef void (*axv_win_fn)(TextPrinter *);

static void grid_down_arrow(TextPrinter *win)
{
    win_set_u16(win, WIN_DOWN_ARROW_COUNTER, 0u);
    ((axv_win_fn)(ADDR_DRAW_INITIAL_DOWN_ARROW_BODY | 1u))(win);
}

static int grid_ext_ctrl(TextPrinter *win, const uint8_t *text, uint16_t next)
{
    uint8_t type = text[next];
    uint16_t p = (uint16_t)(next + 1u);

    switch (type) {
    case FC_FG:
        win_set_u8(win, WIN_COLOR_C, text[p]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(p + 1u));
        return 2;
    case FC_BG:
        win_set_u8(win, WIN_COLOR_D, text[p]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(p + 1u));
        return 2;
    case FC_SHADOW:
        win_set_u8(win, WIN_COLOR_E, text[p]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(p + 1u));
        return 2;
    case FC_ALLCOLORS:
        win_set_u8(win, WIN_COLOR_C, text[p]);
        win_set_u8(win, WIN_COLOR_D, text[p + 1u]);
        win_set_u8(win, WIN_COLOR_E, text[p + 2u]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(p + 3u));
        return 2;
    case FC_PALETTE:
        win_set_u8(win, WIN_PALETTE, text[p]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(p + 1u));
        return 2;
    case FC_FONT:
        win_set_u8(win, WIN_FONTNUM_REAL, text[p]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(p + 1u));
        return 2;
    case FC_DEFAULTFONT: {
        const uint8_t *tpl = win_template(win);
        win_set_u8(win, WIN_FONTNUM_REAL, tpl ? tpl[TPL_DEFAULT_FONT] : 0u);
        win_set_u16(win, WIN_TEXT_INDEX, p);
        return 2;
    }
    case FC_PAUSE:
        win_set_u8(win, WIN_DELAY, text[p]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(p + 1u));
        win_set_u16(win, WIN_STATE, AXV_STATE_PAUSE);
        return 2;
    case FC_WAITBUTTON:
        win_set_u16(win, WIN_TEXT_INDEX, p);
        win_set_u16(win, WIN_STATE, AXV_STATE_WAIT_BUTTON);
        return 2;
    case FC_WAITSOUND:
        win_set_u16(win, WIN_TEXT_INDEX, p);
        win_set_u16(win, WIN_STATE, AXV_STATE_WAIT_SOUND);
        return 2;
    case FC_PLAYBGM:
        ((axv_fn1)(ADDR_PLAY_BGM | 1u))(
            (uint32_t)text[p] | ((uint32_t)text[p + 1u] << 8));
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(p + 2u));
        return 2;
    case FC_PLAYSE:
        ((axv_fn1)(ADDR_PLAY_SE | 1u))(
            (uint32_t)text[p] | ((uint32_t)text[p + 1u] << 8));
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(p + 2u));
        return 2;
    case FC_ESCAPE:
        win_set_u16(win, WIN_TEXT_INDEX, p);
        return 1;
    case FC_SHIFT_TILE_X:
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + text[p]));
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(p + 1u));
        return 1;
    case FC_SHIFT_TILE_Y:
        win_set_u8(win, WIN_CURSOR_TILE_Y,
                   (uint8_t)(win_u8(win, WIN_CURSOR_TILE_Y) + text[p]));
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(p + 1u));
        return 1;
    case FC_CLEARWINDOW:
        ((axv_win_fn)(ADDR_TEXT_CLEAR_WINDOW | 1u))(win);
        win_set_u16(win, WIN_TEXT_INDEX, p);
        return 2;
    default:
        win_set_u16(win, WIN_TEXT_INDEX, p);
        return 2;
    }
}

static int grid_control(TextPrinter *win, uint8_t c, uint16_t next)
{
    switch (c) {
    case 0xFA:
        grid_down_arrow(win);
        win_set_u16(win, WIN_STATE, AXV_STATE_WAIT_SCROLL);
        return 2;
    case 0xFB:
        grid_down_arrow(win);
        win_set_u16(win, WIN_STATE, AXV_STATE_WAIT_CLEAR);
        return 2;
    case 0xFC: {
        const uint8_t *text =
            (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
        return grid_ext_ctrl(win, text, next);
    }
    case 0xFD:
        win_set_u16(win, WIN_STATE, AXV_STATE_PLACEHOLDER);
        return 2;
    case 0xFE:
        /* BUG-11：换行前把本行剩余列的表项清成空白 tile。
         * 必须在设置 STATE 之前清 —— 换行后 cursorY 会移动，
         * grid_cursor_ty 就指向下一行了。
         * ⚠ 只在 0xFE 清，绝不在 0xFF 清：菜单类是「一项一次独立打印」，
         *   每项都以 0xFF 结束且光标已回到行首，在 0xFF 清会把整行菜单
         *   抹掉（2026-11-23 实测：开始菜单 8 项全消失）。带 0xFE 的
         *   多行文本才是本函数要处理的场景。 */
        grid_clear_row_tail(win);
        win_set_u16(win, WIN_STATE, AXV_STATE_NEWLINE);
        return 2;
    case 0xFF:
        win_set_u16(win, WIN_STATE, AXV_STATE_END);
        return 0;
    default:
        return 1;
    }
}

/* =====================================================================
 * §7 唯一导出
 * ===================================================================== */
int PrintNextChar_Hook(TextPrinter *win)
{
    uint16_t index;
    const uint8_t *text;
    const uint8_t *p;
    uint8_t c;
    uint16_t gidx;

    if (!win)
        return 0;
    index = win_u16(win, WIN_TEXT_INDEX);
    text  = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    if (!text)
        return 0;
    p = text + index;
    c = *p;

    /* 复刻原版「读一字节、index+1」；后续分支一律设置最终值，不累加。 */
    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 1u));

    /* ★ 控制码必须先于任何流位置判断：EWRAM/IWRAM 动态串里的 0xFF
     * 若被吞掉，WIN_STATE 到不了 END → RenderText 无限调用 → 输入停摆。 */
    if (c >= PCS_CTRL_BASE) {
        diag_ctrl(2u, c, index);
        return grid_control(win, c, (uint16_t)(index + 1u));
    }

    /* 中文编码：全局唯一 `F7 00 hi lo`。
     * 产物里出现 F9 就是流水线的 bug，应在生成端修，不在这里加分支。 */
    if (c == 0xF7u && p[1] == 0u) {
        gidx = (uint16_t)(GRID_LEAD_ADJUST(p[2]) * 256u + (unsigned)p[3]);
        grid_draw_chs(win, gidx, grid_phase_for(win, text, index));
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 4u));
        return 1;
    }

    grid_draw_pcs(win, c, grid_phase_for(win, text, index));
    return 1;
}
