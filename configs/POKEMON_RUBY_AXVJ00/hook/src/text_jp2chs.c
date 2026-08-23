/* =====================================================================================
 * text_jp2chs.c — AXVJ 日版打印引擎全面接管版（jp2chs）
 *
 * 来源与地位：
 *   以 tools/pokeruby/src/text.c 的架构为骨架、以 configs/.../hook/src/text/ 多文件钩子的
 *   已验证实现为血肉重写而成。设计契约见 docs/ruby_jp_text.md（gdb 埋点 + 反汇编定案）。
 *   与 text.c 的行级对照关系在各节 banner 标注「[text.c Lxxx]」。
 *
 * 接管范围（零回落）：
 *   - 整函数替换原生 PrintNextChar @0x080032F8：取字符/index 推进 + FA–FF 控制码 +
 *     FC 子类型 1–16 + EF 菜单▶ + F9 协议 + SlotTable + 可印字形（VRAM 两趟 / 缓冲模式）。
 *   - 留原生：帧级状态机（延迟/等键节奏）、InitTextPrinter 窗口生命周期、
 *     DrawInitialDownArrow/Text_ClearWindow 执行体（本文件只调用）。
 *
 * 反汇编定案的运行时契约（2026-08-23，详见 docs/ruby_jp_text.md）：
 *   返回值：可印=1；FF=0 且 state←0；FA/FB/FD/FE=2；FC=子处理器返回值(1/2)。
 *   state 枚举与 pokeruby 同号：0=END 1=BEGIN 2=NORMAL 3=CHAR_DELAY 4=PAUSE
 *   5=WAIT_BUTTON 6=NEWLINE 7=PLACEHOLDER 8=WAIT_CLEAR 9=WAIT_SCROLL 10=WAIT_SOUND。
 *   缓冲行（仅 textMode==2）：当前为占位空实现（消费不绘制）；待完整实现
 *   win+0x20 指针缓冲语义（FontFunc[2]/RenderTextHandleBold@0x02CC0 定案：
 *   upper/lower 写指向处、步进 0x40）并解决 F9 汉字右半溢出后再纳入绘制。
 *   textMode==1（等宽表项驱动，如队伍名列表 FontFunc[1]+font4）走 Linear 两趟路径：
 *   动态上载 tile + 原生 UpdateTilemap 写表项，与原生 SubTable[4]@0x080035A0 同构。
 *
 * 订钉（Phase C，另改 main.asm）：P01 由 0x0800336E 上移至 0x080032F8 → 入口 ProcessCurrentChar_C；
 *   P02(Hook3)/P05(箭头相位同步)/P04(地名居中) 维持不变。
 *   本文件暂不接入 build.bat（独立编译验证），换装时需将 src/text/ 下旧钩子对象移出链接清单。
 * ===================================================================================== */
#include "game.h"

/* =====================================================================
 * §1 布局常量与状态枚举 [text.c L11-39 对应]
 * ===================================================================== */
#define PCS_CTRL_BASE        0xFAu   /* ≥ 此值进入控制码跳表（subs#0xFA; cmp#5） */
#define PCS_MENU_CURSOR      0xEFu

enum {                          /* 与 pokeruby WIN_STATE 同号（反汇编定案） */
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
    AXV_STATE_WAIT_SOUND,
};

/* FC 子类型（sub_8003110 跳表，语义 = pokeruby ExtCtrlCode* 家族 1..16） */
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

#define WIN_BUFFER_PTR   0x20    /* 缓冲模式写指针（u32，FontFunc[2] 定案） */

#define MAPNAME_FIELD_PX    80u  /* 地名弹窗文字区 10 列 × 8px */
#define MAPNAME_BUF_BYTES   20
#define MAPNAME_CELL_PX      8u

/* 一个 16×16 CHS 字模的四个 32B tile（TL/BL/TR/BR）。 */
struct ChsGlyphTiles {
    uint8_t *tl;
    uint8_t *bl;
    uint8_t *tr;
    uint8_t *br;
};

/* ---- 前置声明 ---- */
static int  lead_trail_ok(uint8_t lead, uint8_t trail);
static uint16_t pack_glyph_index(uint8_t lead, uint8_t trail);
static int  HandleExtCtrlCode(TextPrinter *win);
int  ProcessCurrentChar_C(TextPrinter *win);
void PrintGlyph_CHS_Adv(TextPrinter *win, uint32_t gidx, unsigned glyphWidth);
void PrintGlyph_Tiles_CHS_Adv(TextPrinter *win, const uint8_t *tiles128, unsigned glyphWidth);
int  DrawGlyph_CHS(TextPrinter *win, uint32_t cur_char);

/* =====================================================================
 * §2 协议原语 [角色 ≈ text.c L3451 GetExtCtrlCodeLength]
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
 * §3 相位槽 [text.c L183-189 静态状态区的现代版；8 槽 LRU @EWRAM]
 * ===================================================================== */
static uint8_t pitch_capture_base_tx(TextPrinter *win)
{
    return win_u8(win, WIN_CURSOR_TILE_X);
}

volatile struct ChineseTileState *chs_bind_pitch_slot(TextPrinter *win, int *out_is_new)
{
    volatile struct ChsPitchCtrl *ctrl =
        (volatile struct ChsPitchCtrl *)ADDR_CHS_PITCH_CTRL;
    volatile struct ChineseTileState *slots =
        (volatile struct ChineseTileState *)ADDR_CHS_PITCH_SLOTS;
    uint8_t *tpl = win_template(win);
    uint8_t char_base = tpl ? tpl[1] : 0;
    uint16_t key = chs_pitch_key(win);
    unsigned i;
    unsigned best;
    uint8_t best_age;
    uint8_t gen;

    if (out_is_new)
        *out_is_new = 0;

    for (i = 0; i < CHS_PITCH_SLOT_COUNT; i++) {
        if (slots[i].pitch_key == key && slots[i].char_base == char_base) {
            gen = (uint8_t)(ctrl->gen + 1u);
            ctrl->gen = gen;
            ctrl->age[i] = gen;
            ctrl->cur = (uint8_t)i;
            return &slots[i];
        }
    }

    best = 0;
    best_age = 255;
    for (i = 0; i < CHS_PITCH_SLOT_COUNT; i++) {
        if (ctrl->age[i] == 0) {
            best = i;
            break;
        }
        if (ctrl->age[i] < best_age) {
            best_age = ctrl->age[i];
            best = i;
        }
    }

    slots[best].char_base = char_base;
    slots[best].write_op = 0;
    slots[best].base_tx = pitch_capture_base_tx(win);
    slots[best].last_adv = (uint8_t)CHS_GLYPH_ADVANCE_PX;
    slots[best].pitch_key = key;
    slots[best].chs_px = 0;
    gen = (uint8_t)(ctrl->gen + 1u);
    ctrl->gen = gen;
    ctrl->age[best] = gen;
    ctrl->cur = (uint8_t)best;
    if (out_is_new)
        *out_is_new = 1;
    return &slots[best];
}

void Chinese_PitchReset(TextPrinter *win)
{
    volatile struct ChineseTileState *st = chs_bind_pitch_slot(win, 0);
    st->chs_px = 0;
    st->base_tx = pitch_capture_base_tx(win);
}

/* =====================================================================
 * §4 像素件 [text.c L2717 GetCursorTilemapPointer 位 / 原 ShiftGlyphTile_* 区]
 * ===================================================================== */
static void copy_tile32(void *dst_vram, const void *src_iwram)
{
    const uint32_t *s = (const uint32_t *)src_iwram;
    uint32_t *d = (uint32_t *)dst_vram;
    d[0] = s[0];
    d[1] = s[1];
    d[2] = s[2];
    d[3] = s[3];
    d[4] = s[4];
    d[5] = s[5];
    d[6] = s[6];
    d[7] = s[7];
}

uint8_t *vram_tile(TextPrinter *win, uint16_t tile)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, 0x0C);
    return tile_data + ((uint32_t)tile << 5);
}

static uint8_t get_px(const uint8_t *tile, unsigned x, unsigned y)
{
    unsigned bi = y * 4u + x / 2u;
    if (x & 1u)
        return (uint8_t)(tile[bi] & 0x0Fu);
    return (uint8_t)(tile[bi] >> 4);
}

static void put_px(uint8_t *tile, unsigned x, unsigned y, uint8_t ink)
{
    unsigned bi = y * 4u + x / 2u;
    if (x & 1u)
        tile[bi] = (uint8_t)((tile[bi] & 0xF0u) | (ink & 0x0Fu));
    else
        tile[bi] = (uint8_t)((tile[bi] & 0x0Fu) | ((ink & 0x0Fu) << 4));
}

/* =====================================================================
 * §4b 场景布局门控 [text.c 无对应——WindowTemplate 常量区的运行时替身；
 *     A/B 实测确认必要（docs/ruby_jp_text.md），实现逐字继承旧钩子]
 * ===================================================================== */
int scene_is_battle_text_window(TextPrinter *win)
{
    uint16_t tb = win_u16(win, WIN_TILE_BASE);

    if (tb == CHS_BATTLE_DIALOG_BASE_LO)
        return 1;
    if (tb >= CHS_BATTLE_TEXT_BASE_LO && tb < CHS_BATTLE_TEXT_BASE_HI)
        return 1;
    return tb >= CHS_BATTLE_FIXED_BASE;
}

int scene_battle_force_linear(TextPrinter *win)
{
    return scene_is_battle_text_window(win);
}

int scene_is_party_footer(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint8_t left;
    uint8_t top;

    if (!tpl || tpl[1] != 2)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    left = win_u8(win, WIN_CURSOR_X);
    if (left >= CHS_SHOP_LIST_LEFT)
        return 0;
    top = win_u8(win, WIN_CURSOR_Y);
    return (top == CHS_PARTY_FOOTER_TOP_TILE || top == CHS_PARTY_FOOTER_TOP_PX);
}

int scene_is_shop_desc(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint8_t left;
    uint8_t top;

    if (!tpl || tpl[1] != 2)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    left = win_u8(win, WIN_CURSOR_X);
    if (left >= CHS_SHOP_LIST_LEFT)
        return 0;
    if (scene_is_party_footer(win))
        return 0;
    top = win_u8(win, WIN_CURSOR_Y);
    return (top == CHS_SHOP_DESC_TOP_PX || top == CHS_SHOP_DESC_TOP_TILE);
}

int scene_menu_wants_mode2(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint8_t char_base;

    if (!tpl)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    char_base = tpl[1];
    if (char_base != 0 && char_base != 2)
        return 0;
    if (scene_is_shop_desc(win))
        return 0;
    if (scene_is_shop_bag_list(win))
        return 0;
    return 1;
}

int scene_is_shop_bag_list(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    const uint8_t *gmenu;
    uint8_t left;
    uint16_t tile_base;

    if (!tpl || tpl[1] != 2)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    if (scene_is_shop_desc(win) || scene_is_party_footer(win))
        return 0;

    left = win_u8(win, WIN_CURSOR_X);
    tile_base = win_u16(win, WIN_TILE_BASE);

    /* 背包物品名：TILE_BASE = 0x8A + 14*row */
    if (left == 2u && tile_base >= 0x80u && tile_base < 0x120u)
        return 1;
    /* 背包数量行 */
    if (left == 7u && tile_base >= 0x60u && tile_base < 0x90u)
        return 1;

    gmenu = (const uint8_t *)ADDR_GMENU;
    if (gmenu[GMENU_LEFT] == 1u && gmenu[GMENU_TOP] == 1u
        && gmenu[GMENU_MAX_MINUS_1] >= 6u) {
        if (left == 2u || left == 7u)
            return 1;
    }
    return 0;
}

/* =====================================================================
 * §5 单 tile 盖章 [text.c L3877/L4090 DrawGlyphTile_Unshadowed/Shadowed 合一；
 *    CopyGlyph 统一色映射后两者无差。原 Unshadowed 版删除。]
 * ===================================================================== */
void DrawGlyphTile_CHS(
    TextPrinter *win, struct GlyphTileInfo *info, uint8_t *spillTile)
{
    uint32_t temp_words[8];
    uint32_t dest_words[8];
    uint32_t spill_words[8];
    uint8_t *temp = (uint8_t *)temp_words;
    uint8_t *dest_l = (uint8_t *)dest_words;
    uint8_t *spill_l = (uint8_t *)spill_words;
    uint8_t *dest = (uint8_t *)info->dest;
    const uint8_t *src32 = info->src;
    unsigned startPixel = info->startPixel;
    unsigned width = info->width;
    unsigned r, c;
    unsigned gw_end = startPixel + width;
    uint8_t fg_ov = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    uint8_t color_c = (fg_ov != 0u) ? fg_ov : win_u8(win, WIN_COLOR_C);
    uint8_t color_d = win_u8(win, WIN_COLOR_D);
    uint8_t color_e = win_u8(win, WIN_COLOR_E);
    int need_spill = (spillTile != 0) && (gw_end > 8u);

    /* 着色在渲染层（对齐 pokeruby ApplyColors 位于渲染侧）：
     * CopyGlyph(C,E,D): 15→ink, 14→shadow, 0→bg */
    chs_copy_glyph_2bpp_to_4bpp(src32, temp, color_c, color_e, color_d);

    if (spillTile == 0 && startPixel == 0u && width == 8u) {
        copy_tile32(dest, temp);
        return;
    }

    {
        const uint32_t *dv = (const uint32_t *)dest;
        for (c = 0; c < 8u; c++)
            dest_words[c] = dv[c];
    }
    if (need_spill) {
        const uint32_t *sv = (const uint32_t *)spillTile;
        for (c = 0; c < 8u; c++)
            spill_words[c] = sv[c];
    }

    for (r = 0; r < 8; r++) {
        for (c = startPixel; c < gw_end && c < 8u; c++)
            put_px(dest_l, c, r, color_d);
        if (need_spill) {
            unsigned from = (startPixel > 8u) ? (startPixel - 8u) : 0u;
            unsigned to = gw_end - 8u;
            for (c = from; c < to && c < 8u; c++)
                put_px(spill_l, c, r, color_d);
        }
        for (c = 0; c < width; c++) {
            unsigned dc = startPixel + c;
            if (dc < 8u)
                put_px(dest_l, dc, r, get_px(temp, c, r));
            else if (need_spill)
                put_px(spill_l, dc - 8u, r, get_px(temp, c, r));
        }
        if (gw_end < 8u) {
            for (c = gw_end; c < 8u; c++)
                put_px(dest_l, c, r, color_d);
        }
        if (need_spill && gw_end > 8u) {
            for (c = gw_end - 8u; c < 8u; c++)
                put_px(spill_l, c, r, color_d);
        }
    }

    copy_tile32(dest, dest_l);
    if (need_spill)
        copy_tile32(spillTile, spill_l);
}

/* =====================================================================
 * §7 tile 编号 [text.c L4380 GetCursorTileNum 两分支；UI 保护带/场景几何内联]
 * ===================================================================== */
/* pokeruby GetCursorTileNum 的 Linear 分支；内含 UI 图标保护带（原 avoid_dex_ui_tile）。 */
static uint16_t GetCursorTileNum_Linear(
    TextPrinter *win, unsigned xOffset, unsigned yOffset)
{
    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    uint16_t tile = (uint16_t)(tile_base + off + 2u * xOffset + yOffset);

    /* 战斗文本窗不重映射（FillWindow 底色依赖原 tile）＝ 原 scene_is_battle_text_window */
    if (!scene_is_battle_text_window(win)) {
        if (tile >= CHS_MENU_CURSOR_TILE && tile <= CHS_MENU_CURSOR_TILE_HI)
            tile = (uint16_t)(CHS_MENU_CURSOR_TILE_ALT + (tile - CHS_MENU_CURSOR_TILE));
        else if (tile >= CHS_UI_ICON_TILE_LO && tile <= CHS_UI_ICON_TILE_HI)
            tile = (uint16_t)(CHS_UI_ICON_TILE_ALT + (tile - CHS_UI_ICON_TILE_LO));
    }
    return tile;
}

/* pokeruby GetCursorTileNum 的 UNKNOWN2 分支（y*30+x 网格）；队尾/队伍选项几何内联
 * （＝ 原 scene_mode2_apply：shop origin+2、PARTY_FOOTER_BAND、MENU_BAND）。 */
static void GetCursorTileNum_Mode2(
    TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower)
{
    int x = (int)win_u8(win, WIN_CURSOR_X) + tile_x;
    int y = (int)win_u8(win, WIN_CURSOR_Y) + (int)win_u8(win, WIN_CURSOR_TILE_Y);
    int band = 0;
    int origin = CHS_MODE2_ORIGIN_SHOP;
    uint8_t *tpl = win_template(win);
    volatile struct ChineseTileState *st = chs_bind_pitch_slot(win, 0);
    uint8_t op = st->write_op;
    uint8_t left = win_u8(win, WIN_CURSOR_X);

    if (!tpl || tpl[1] != 2)
        origin = 0;

    /* ---- 原 scene_mode2_apply 内联 ---- */
    if (scene_is_party_footer(win)) {
        if (y >= CHS_PARTY_FOOTER_TOP_PX)
            y /= 8;
        if (y >= 16) {
            y -= 16;
            band = CHS_MODE2_PARTY_FOOTER_BAND;
        }
    } else if (op == 0) {
        if (!(y <= 20 && (y & 1) == 0)) {
            if (left >= CHS_PARTY_MENU_LEFT && y >= CHS_PARTY_MENU_TOP) {
                x++;
                y -= CHS_PARTY_MENU_TOP;
                band = CHS_MODE2_MENU_BAND;
                origin = CHS_MODE2_ORIGIN_MENU;
            }
        }
    }

    {
        uint32_t idx = (uint32_t)(y * CHS_TILE_GRID_W + x + band);
        idx += win_u16(win, WIN_TILE_BASE);
        idx += (uint32_t)origin;
        {
            uint16_t up = (uint16_t)idx;
            uint16_t lo = (uint16_t)(idx + CHS_TILE_GRID_W);
            /* UI 保护带（＝ 原 avoid_dex_ui_tile；战斗窗不重映射） */
            if (!scene_is_battle_text_window(win)) {
                if (up >= CHS_MENU_CURSOR_TILE && up <= CHS_MENU_CURSOR_TILE_HI)
                    up = (uint16_t)(CHS_MENU_CURSOR_TILE_ALT + (up - CHS_MENU_CURSOR_TILE));
                else if (up >= CHS_UI_ICON_TILE_LO && up <= CHS_UI_ICON_TILE_HI)
                    up = (uint16_t)(CHS_UI_ICON_TILE_ALT + (up - CHS_UI_ICON_TILE_LO));
                if (lo >= CHS_MENU_CURSOR_TILE && lo <= CHS_MENU_CURSOR_TILE_HI)
                    lo = (uint16_t)(CHS_MENU_CURSOR_TILE_ALT + (lo - CHS_MENU_CURSOR_TILE));
                else if (lo >= CHS_UI_ICON_TILE_LO && lo <= CHS_UI_ICON_TILE_HI)
                    lo = (uint16_t)(CHS_UI_ICON_TILE_ALT + (lo - CHS_UI_ICON_TILE_LO));
            }
            *upper = up;
            *lower = lo;
        }
    }
}

static void map_at(TextPrinter *win, uint8_t tx, uint16_t abs_u, uint16_t abs_l)
{
    win_set_u8(win, WIN_CURSOR_TILE_X, tx);
    chs_update_tilemap(win, abs_u, abs_l);
}

/* =====================================================================
 * §8 两趟绘制核心 [text.c L4321 DrawGlyphTiles 对应；Linear/Mode2 选择内联]
 * ===================================================================== */
static void DrawGlyphTiles_CHS_Core(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, int linear,
    unsigned glyphWidth)
{
    volatile struct ChineseTileState *st = chs_bind_pitch_slot(win, 0);
    unsigned startPixel;
    unsigned pass2_w;
    uint16_t off, abs_u, abs_l, su, sl;
    uint8_t *du, *dl, *du_sp, *dl_sp;
    uint8_t map_tx;
    int spilled;
    struct GlyphTileInfo info;
    if (glyphWidth < 8u)
        glyphWidth = 8u;
    if (glyphWidth > 12u)
        glyphWidth = 12u;
    pass2_w = glyphWidth - 8u;
    spilled = 0;
    su = 0;
    sl = 0;

    if (st->chs_px == 0)
        st->base_tx = pitch_capture_base_tx(win);

    startPixel = (unsigned)(st->chs_px & 7u);
    map_tx = (uint8_t)(st->base_tx + (st->chs_px >> 3));

    info.startPixel = (uint8_t)startPixel;
    info.textMode = 0;
    info.colors = 0;

    if (linear) {
        if (st->chs_px == 0) {
            /* 线性池下限（原 ensure_linear_dest_floor 内联）：party 尾/商店描述/
             * 商店背包列表/菜单各有 floor，其余 4。 */
            uint8_t *tpl = win_template(win);
            uint16_t fl_off = win_u16(win, WIN_TILE_OFFSET);
            uint16_t floor;
            if (scene_is_party_footer(win))
                floor = CHS_PARTY_FOOTER_LINEAR_FLOOR;
            else if (scene_is_shop_desc(win))
                floor = CHS_SHOP_DESC_LINEAR_FLOOR;
            else if (tpl && tpl[1] == 2)
                floor = CHS_MENU_LINEAR_FLOOR;
            else
                floor = 4;
            if (fl_off < floor)
                win_set_u16(win, WIN_TILE_OFFSET, floor);
        }
        off = win_u16(win, WIN_TILE_OFFSET);
        abs_u = GetCursorTileNum_Linear(win, 0, 0);
        abs_l = GetCursorTileNum_Linear(win, 0, 1);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + 8u > 8u) {
            su = GetCursorTileNum_Linear(win, 1, 0);
            sl = GetCursorTileNum_Linear(win, 1, 1);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
            spilled = 1;
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        info.src = tiles->tl;
        info.dest = (uint32_t *)(uintptr_t)du;
        info.width = 8;
        DrawGlyphTile_CHS(win, &info, du_sp);
        info.src = tiles->bl;
        info.dest = (uint32_t *)(uintptr_t)dl;
        DrawGlyphTile_CHS(win, &info, dl_sp);
        map_at(win, map_tx, abs_u, abs_l);
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
    } else {
        GetCursorTileNum_Mode2(win, (int)map_tx, &abs_u, &abs_l);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + 8u > 8u) {
            GetCursorTileNum_Mode2(win, (int)map_tx + 1, &su, &sl);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
            spilled = 1;
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        info.src = tiles->tl;
        info.dest = (uint32_t *)(uintptr_t)du;
        info.width = 8;
        DrawGlyphTile_CHS(win, &info, du_sp);
        info.src = tiles->bl;
        info.dest = (uint32_t *)(uintptr_t)dl;
        DrawGlyphTile_CHS(win, &info, dl_sp);
        map_at(win, map_tx, abs_u, abs_l);
    }

    st->chs_px = (uint16_t)(st->chs_px + 8u);
    if (pass2_w == 0u) {
        if (spilled)
            map_at(win, (uint8_t)(map_tx + 1u), su, sl);
        st->last_adv = (uint8_t)glyphWidth;
        win_set_u8(win, WIN_CURSOR_TILE_X,
            (uint8_t)(st->base_tx + ((st->chs_px + glyphWidth - 1) >> 3)));
        return;
    }

    map_tx = (uint8_t)(st->base_tx + (st->chs_px >> 3));

    if (linear) {
        off = win_u16(win, WIN_TILE_OFFSET);
        abs_u = GetCursorTileNum_Linear(win, 0, 0);
        abs_l = GetCursorTileNum_Linear(win, 0, 1);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + pass2_w > 8u) {
            su = GetCursorTileNum_Linear(win, 1, 0);
            sl = GetCursorTileNum_Linear(win, 1, 1);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        info.src = tiles->tr;
        info.dest = (uint32_t *)(uintptr_t)du;
        info.width = (uint8_t)pass2_w;
        DrawGlyphTile_CHS(win, &info, du_sp);
        info.src = tiles->br;
        info.dest = (uint32_t *)(uintptr_t)dl;
        DrawGlyphTile_CHS(win, &info, dl_sp);
        map_at(win, map_tx, abs_u, abs_l);
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + (startPixel == 0u ? 0u : 2u)));
    } else {
        GetCursorTileNum_Mode2(win, (int)map_tx, &abs_u, &abs_l);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + pass2_w > 8u) {
            GetCursorTileNum_Mode2(win, (int)map_tx + 1, &su, &sl);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        info.src = tiles->tr;
        info.dest = (uint32_t *)(uintptr_t)du;
        info.width = (uint8_t)pass2_w;
        DrawGlyphTile_CHS(win, &info, du_sp);
        info.src = tiles->br;
        info.dest = (uint32_t *)(uintptr_t)dl;
        DrawGlyphTile_CHS(win, &info, dl_sp);
        map_at(win, map_tx, abs_u, abs_l);
    }

    st->chs_px = (uint16_t)(st->chs_px + pass2_w);
    st->last_adv = (uint8_t)glyphWidth;
    win_set_u8(win, WIN_CURSOR_TILE_X,
        (uint8_t)(st->base_tx + ((st->chs_px + glyphWidth - 1) >> 3)));
}

/* =====================================================================
 * §8b GetGlyph —— 字形源统一解析（「下标查字库瓦片」的唯一入口）
 * 职责边界：只负责取址与【格式归一】，不做着色/不读窗口颜色——
 * 着色（C/E/D + OPT_FG_COLOR）属渲染层（对齐 pokeruby：ApplyColors 在
 * DrawGlyphTile 渲染侧）。输出为归一化的 128B（TL,BL,TR,BR）：
 *   统一 4bpp 索引布局、墨水/阴影/背景落在 15/14/0 标准索引位；
 *   CHS 右半列 ≥CHS_GLYPH_ADVANCE_PX 处清零（步进规格化）。
 * 来源（分支序即优先级）：
 *   GLYPH_SRC_CHS|gidx → CHS 汉库 FontChsNormal（128B/字）
 *   0x00               → 空白格（全零）
 *   0x36..0x3E         → Sym 标点带（64B/字：上排+下排，右列置空）
 *   其余可印 PCS       → 日文 fontNum 字库（官方 GetGlyphTilePointers；
 *                        3/4/5 原样 4bpp，0/1/2/6 以 fg15/bg0 展开）
 * 返回 0=该码不可绘制。
 * ===================================================================== */
#define GLYPH_SRC_CHS 0x01000000u

static int GetGlyph(TextPrinter *win, uint32_t code, uint8_t *out128)
{
    /* ---- CHS 汉库（全局 8px 小字：FontChsSmall 与 Normal 同 128B 容器，
     *      仅切换基址；字形沉底配比与原生 font4 节奏一致） ---- */
    if (code & GLYPH_SRC_CHS) {
        const uint8_t *base = (const uint8_t *)ADDR_FONT_CHS_SMALL
            + ((uint32_t)(code & CHS_GLYPH_IDX_MASK) << 7);
        unsigned x, y;
        copy_tile32(out128 + 0x00, base + 0x00);
        copy_tile32(out128 + 0x20, base + 0x20);
        copy_tile32(out128 + 0x40, base + 0x40);
        copy_tile32(out128 + 0x60, base + 0x60);
        /* 步进规格化：12px 之外的列清到索引 0（背景位） */
        for (y = 0; y < 8u; y++)
            for (x = CHS_GLYPH_ADVANCE_PX - 8u; x < 8u; x++) {
                put_px(out128 + 0x40, x, y, 0);
                put_px(out128 + 0x60, x, y, 0);
            }
        return 1;
    }

    /* ---- 空白 ---- */
    if (code == 0) {
        unsigned i;
        for (i = 0; i < 128u; i++)
            out128[i] = 0;
        return 1;
    }

    /* ---- Sym 标点带 ---- */
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
        return 1;
    }

    /* ---- 日文 fontNum 字库 ---- */
    {
        uint8_t *upper = 0;
        uint8_t *lower = 0;
        uint8_t font;

        if (code >= 0xF7)
            return 0;
        font = win_u8(win, WIN_FONTNUM_REAL);
        if (font > 6u)
            font = FONT_NORMAL_SHADOWED;
        chs_get_glyph_tile_pointers(font, (uint16_t)code, &upper, &lower);
        if (!upper || !lower)
            return 0;

        for (unsigned i = 0; i < 64u; i++)
            out128[0x40 + i] = 0;
        if (chs_font_is_shadowed(font)) {
            copy_tile32(out128 + 0x00, upper);
            copy_tile32(out128 + 0x20, lower);
        } else {
            chs_copy_glyph_1bpp_to_4bpp(upper, (uint32_t *)(uintptr_t)(out128 + 0x00), 0xFu, 0x0u);
            chs_copy_glyph_1bpp_to_4bpp(lower, (uint32_t *)(uintptr_t)(out128 + 0x20), 0xFu, 0x0u);
        }
        return 1;
    }
}

/* =====================================================================
 * §9 打印家族 [text.c L357/L368 分发结构原样保留]
 *   sPrintGlyphFuncs[win->textMode]        ← 打印方式分发（text.c:359）
 *   sWriteGlyphTilemapFuncs[win->fontNum]  ← 表项写入分发（text.c:368，mode1 用）
 * 全面接管后原生 FontFuncTable 不再被查询，这两张表即唯一分发器。
 * 行为差异对照：AXVJ 的 FontFuncTable(0..6) 按 textMode 索引，其中 [2]=缓冲、
 * [1]=等宽（内部再按 fontNum 查 SubTable）——语义并入下表对应行；pokeruby 的
 * mode2(UNKNOWN2 连续变宽) 在日版由 mode0/3 承担，故本表 3+ 行复用 TextMode0。
 * ===================================================================== */

typedef void (*PrintGlyphFunc)(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth);

static void PrintGlyph_TextMode0(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth);
static void PrintGlyph_TextMode1(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth);
static void PrintGlyph_TextMode2(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth);

/* 打印方式表（索引=win->textMode；越界回落 TextMode0＝对话主路径） */
static const PrintGlyphFunc sPrintGlyphFuncs[8] = {
    PrintGlyph_TextMode0,   /* 0：变宽像素直绘 */
    PrintGlyph_TextMode1,   /* 1：等宽表项驱动（MONOSPACE） */
    PrintGlyph_TextMode2,   /* 2：win+0x20 指针缓冲（AXVJ 血条/加粗） */
    PrintGlyph_TextMode0,   /* 3：对话主窗（埋点分布最高） */
    PrintGlyph_TextMode0,   /* 4+：预留——新组合直接在此挂函数/追加行 */
    PrintGlyph_TextMode0,   /* 5 */
    PrintGlyph_TextMode0,   /* 6 */
    PrintGlyph_TextMode0,   /* 7 */
};
#define PRINT_GLYPH_MODES 8u

/* 表项写入表（索引=win->fontNum）。当前各字体共用通用写法（CHS 动态槽位，
 * upper/lower 由调用方算好）；保留按 fontNum 分叉的扩展位——对齐 pokeruby
 * WriteGlyphTilemap_Font0_Font3/_Font1_Font4/_Font2_Font5/Font6 的分叉点。 */
typedef void (*WriteGlyphTilemapFunc)(TextPrinter *, uint16_t, uint16_t);
static const WriteGlyphTilemapFunc sWriteGlyphTilemapFuncs[8] = {
    chs_update_tilemap, chs_update_tilemap,
    chs_update_tilemap, chs_update_tilemap,
    chs_update_tilemap, chs_update_tilemap,
    chs_update_tilemap, chs_update_tilemap,
};

/*
 * PrintGlyph_TextMode0 — 官方 PrintGlyph_TextMode0/3 系合流：
 * 相位槽绑定、FE 后重置、TILE_OFFSET 补偿，然后进两趟核心
 * （Linear 动态 tile + 原生 UpdateTilemap 写表项；
 *  Linear/Mode2 公式选择内联于下方条件链，对应各场景模板差异）。
 */
static void PrintGlyph_TextMode0(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    int slot_new = 0;
    volatile struct ChineseTileState *st;
    uint8_t cur_tx;
    unsigned last;
    int linear;
    int newline_reset = 0;

    st = chs_bind_pitch_slot(win, &slot_new);
    cur_tx = win_u8(win, WIN_CURSOR_TILE_X);

    if (slot_new && st->chs_px == 0)
        newline_reset = 1;

    if (st->chs_px != 0 && cur_tx <= st->base_tx) {
        st->chs_px = 0;
        st->base_tx = pitch_capture_base_tx(win);
        newline_reset = 1;
    } else if (st->chs_px != 0) {
        last = st->last_adv ? st->last_adv : CHS_GLYPH_ADVANCE_PX;
        {
            uint8_t expect = (uint8_t)(st->base_tx + ((st->chs_px + last - 1) >> 3));
            if (cur_tx != expect) {
                st->chs_px = 0;
                st->base_tx = pitch_capture_base_tx(win);
                newline_reset = 1;
            }
        }
    } else {
        st->base_tx = pitch_capture_base_tx(win);
    }

    /* ---- Linear/Mode2 选择（＝ 原 DrawGlyph_ShouldUseLinear / 场景门控内联）----
     * 战斗文本窗强制 Linear；商店描述/背包列表 Linear；
     * menu wants mode2（fontNum==3 且 charBase 0/2，非商店）走 Mode2；
     * 其余 Font3 也 Mode2（同原生 Font3）；其他字体默认 Linear。 */
    if (scene_battle_force_linear(win)) {
        linear = 1;
    } else if (scene_is_shop_desc(win) || scene_is_shop_bag_list(win)) {
        linear = 1;
    } else if (scene_menu_wants_mode2(win)) {
        linear = 0;
    } else if (win_u8(win, WIN_FONTNUM_REAL) == FONT_NORMAL_SHADOWED) {
        linear = 0;
    } else {
        linear = 1;
    }

    if (newline_reset && linear) {
        uint16_t off = win_u16(win, WIN_TILE_OFFSET);
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
    }

    DrawGlyphTiles_CHS_Core(win, tiles, linear, glyphWidth);
}

/*
 * 动态槽位分配（mode1 用）。原生 font4 的字形像素来自场景初始化预渲染的
 * 静态块 [TILE_BASE .. TILE_BASE+255]，打印只查 sFontType1Map 写表项；
 * CHS 字形无法预渲染，改为占用块尾之后的空闲区。分配游标用引擎静态量而非
 * WIN_TILE_OFFSET——InitTextPrinter 每次调用清零 TILE_OFFSET，共享静态窗
 * 逐行复用时若用它分配会导致各行互相覆盖（实测六行同名＋首字缺左半）。
 */
/* 分配游标存固定 EWRAM（ADDR_GLYPH_ALLOC_NEXT=0x0203FFF8，遗留单槽位）。
 * ⚠️ 不能用 C 静态变量：game.bin 无运行时加载器，静态变量落 BSS——写 ROM 被
 * 忽略、读为垃圾（实测症状：每字形都分配到同一对 tile → 全屏显示最后字形）。 */
#define MONO_TILE_NEXT  (*(volatile uint16_t *)ADDR_GLYPH_ALLOC_NEXT)

static uint16_t AllocGlyphTiles(uint16_t base, unsigned n)
{
    uint16_t lo = (uint16_t)(base + 0x100u);            /* 跳过预渲染块 */
    if (MONO_TILE_NEXT < lo || MONO_TILE_NEXT > (uint16_t)(base + 0x200u - n))
        MONO_TILE_NEXT = lo;
    {
        uint16_t ret = MONO_TILE_NEXT;
        MONO_TILE_NEXT = (uint16_t)(MONO_TILE_NEXT + n);
        return ret;
    }
}

/*
 * PrintGlyph_TextMode1 — 等宽表项驱动（MONOSPACE）。
 * 对齐 pokeruby PrintGlyph_TextMode1（text.c:2586）：字形上载后经
 * sWriteGlyphTilemapFuncs[fontNum] 写表项；尾部游标推进对齐原生
 * FontFunc[1]（cursorTileX++，位置由 cursor 字段进 UpdateTilemap）。
 * 宽字形（12px 汉字）占两列：先右移一列写第二对表项再回推，与原生逐格步进自洽。
 */
static void PrintGlyph_TextMode1(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    uint16_t base = win_u16(win, WIN_TILE_BASE);
    uint8_t fontNum = win_u8(win, WIN_FONTNUM_REAL) & 7u;
    unsigned two_col = (glyphWidth > 8u);
    uint16_t t = AllocGlyphTiles(base, two_col ? 4u : 2u);
    struct GlyphTileInfo info;

    /* 着色在渲染层：DrawGlyphTile_CHS 按窗口 C/E/D 重映射后写入 VRAM。
     * 宽字形第二列的 TR/BR 已由 GetGlyph 规格化（≥advance 列清零），整 tile
     * 按 8px 渲染即可得到「墨+背景」的正确列。 */
    info.textMode = 0;
    info.colors = 0;
    info.startPixel = 0;
    info.width = 8;

    info.src = tiles->tl;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, t);
    DrawGlyphTile_CHS(win, &info, 0);
    info.src = tiles->bl;
    info.dest = (uint32_t *)(uintptr_t)vram_tile(win, t + 1);
    DrawGlyphTile_CHS(win, &info, 0);
    if (two_col) {
        info.src = tiles->tr;
        info.dest = (uint32_t *)(uintptr_t)vram_tile(win, t + 2);
        DrawGlyphTile_CHS(win, &info, 0);
        info.src = tiles->br;
        info.dest = (uint32_t *)(uintptr_t)vram_tile(win, t + 3);
        DrawGlyphTile_CHS(win, &info, 0);
    }

    sWriteGlyphTilemapFuncs[fontNum](win, t, (uint16_t)(t + 1));
    if (two_col) {
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
        sWriteGlyphTilemapFuncs[fontNum](win, (uint16_t)(t + 2), (uint16_t)(t + 3));
    }
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
}

/* 缓冲行（textMode==2）：当前为占位空实现——正常进入分发、消费字符但不绘制。
 * 待办（未来纳入绘制）：按 win+0x20 指针缓冲语义完整实现（FontFunc[2] /
 * RenderTextHandleBold@0x02CC0 定案：upper/lower 写指向处、步进 0x40），并先解决
 * F9 汉字右半溢出（槽宽 0x40 只容 TL/BL）再启用，避免左半汉字这类半成品输出。 */
static void PrintGlyph_TextMode2(
    TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    (void)win;
    (void)tiles;
    (void)glyphWidth;
}

/* F9 汉字：gidx 经 GetGlyph（CHS 汉库）产出组色 128B 后进分发。 */
void PrintGlyph_CHS_Adv(TextPrinter *win, uint32_t gidx, unsigned glyphWidth)
{
    uint8_t buf[128];
    struct ChsGlyphTiles t;

    if (!GetGlyph(win, GLYPH_SRC_CHS | (gidx & CHS_GLYPH_IDX_MASK), buf))
        return;
    t.tl = buf + 0x00;
    t.bl = buf + 0x20;
    t.tr = buf + 0x40;
    t.br = buf + 0x60;
    {
        unsigned m = win_u8(win, WIN_TEXTMODE);
        if (m >= PRINT_GLYPH_MODES)
            m = 0;
        sPrintGlyphFuncs[m](win, &t, glyphWidth);
    }
}

/* Sym 标点 / JP 组合缓冲（128B TL,BL,TR,BR 连续）入口。 */
void PrintGlyph_Tiles_CHS_Adv(
    TextPrinter *win, const uint8_t *tiles128, unsigned glyphWidth)
{
    struct ChsGlyphTiles t;
    t.tl = (uint8_t *)tiles128 + 0x00;
    t.bl = (uint8_t *)tiles128 + 0x20;
    t.tr = (uint8_t *)tiles128 + 0x40;
    t.br = (uint8_t *)tiles128 + 0x60;
    {
        unsigned m = win_u8(win, WIN_TEXTMODE);
        if (m >= PRINT_GLYPH_MODES)
            m = 0;
        sPrintGlyphFuncs[m](win, &t, glyphWidth);
    }
}

/* =====================================================================
 * §10 字库取址分发 [text.c L2676 GetGlyphTilePointers；bit15 门控，
 *      跳板 GetGlyphTilePointers_Hook/_Orig 仍在 text/entry.s]
 * ===================================================================== */
void GetGlyphTilePointers_CHS(uint32_t fontNum, uint32_t glyph,
                              uint8_t **upperTilePtr, uint8_t **lowerTilePtr)
{
    uint32_t gidx = glyph & CHS_GLYPH_IDX_MASK;
    uint8_t *base = (uint8_t *)(ADDR_FONT_CHS_NORMAL + (gidx << 7));

    (void)fontNum;
    if (glyph & CHS_GLYPH_HALF_BIT)
        base += 64u;
    *upperTilePtr = base;
    *lowerTilePtr = base + 32u;
}

void GetGlyphTilePointers_C(uint32_t fontNum, uint32_t glyph,
                            uint8_t **upperTilePtr, uint8_t **lowerTilePtr)
{
    if (glyph & CHS_GLYPH_HALF_BIT)
        GetGlyphTilePointers_CHS(fontNum, glyph, upperTilePtr, lowerTilePtr);
    else
        GetGlyphTilePointers_Orig(fontNum, glyph, upperTilePtr, lowerTilePtr);
}

/* =====================================================================
 * §11 单字节分发 [text.c L357 sPrintGlyphFuncs 表位的单函数替代]
 * 字形产出统一走 GetGlyph（含空白/Sym/JP/不可印判定）；本函数只做
 * 「取制 → 组装 → 分发」。返回恒 1（引擎零回落：不可印位直接消费）。
 * ===================================================================== */
int DrawGlyph_CHS(TextPrinter *win, uint32_t cur_char)
{
    uint8_t buf[128];
    struct ChsGlyphTiles t;

    if (!GetGlyph(win, cur_char, buf))
        return 1;
    t.tl = buf + 0x00;
    t.bl = buf + 0x20;
    t.tr = buf + 0x40;
    t.br = buf + 0x60;
    {
        unsigned m = win_u8(win, WIN_TEXTMODE);
        if (m >= PRINT_GLYPH_MODES)
            m = 0;
        sPrintGlyphFuncs[m](win, &t, CHS_GLYPH_ADVANCE_JP_PX);
    }
    return 1;
}

/* =====================================================================
 * §12 F9 协议 [text.c 无对应；短语表 PhraseOffsets/Table @0x08810000/08820000]
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
                PrintGlyph_CHS_Adv(win, gidx, CHS_GLYPH_ADVANCE_PX);
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

/* =====================================================================
 * §13 SlotTable 查找族 [text.c 无对应；'SLT2' 分桶 / legacy 平铺]
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
                    PrintGlyph_CHS_Adv(win, gidx, CHS_GLYPH_ADVANCE_PX);
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

static int slot_lookup_legacy(TextPrinter *win, uint32_t cur_char,
                              const uint8_t *text, uint16_t index)
{
    const uint8_t *table = (const uint8_t *)ADDR_SLOT_TABLE;
    unsigned i = 0;
    uint8_t stream_buf[256];
    uint8_t stream_len = 0;
    unsigned k;

    /* cnt 必须 int：uint8_t 对 sizeof 比较恒真会被编译器删边界 → 回绕死循环。 */
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

    if (slot_rd_le32(table) == SLOT_TABLE_MAGIC_V2)
        return slot_lookup_v2(win, cur_char, table, text, index);

    return slot_lookup_legacy(win, cur_char, text, index);
}

/* =====================================================================
 * §14 控制码处理器 [text.c L2080-2331 对应：PrintNextChar switch +
 *      HandleExtCtrlCode 家族；语义全部由 0x080032F8/0x08003110 反汇编定案]
 * ===================================================================== */
typedef void (*axv_fn1)(uint32_t a0);
static void axv_play_bgm(uint16_t id) { ((axv_fn1)(ADDR_PLAY_BGM | 1u))(id); }
static void axv_play_se(uint16_t id)  { ((axv_fn1)(ADDR_PLAY_SE | 1u))(id); }
typedef void (*axv_win_fn)(TextPrinter *);
static void axv_draw_down_arrow(TextPrinter *win) { ((axv_win_fn)(ADDR_DRAW_INITIAL_DOWN_ARROW | 1u))(win); }
static void axv_clear_window(TextPrinter *win)    { ((axv_win_fn)(ADDR_TEXT_CLEAR_WINDOW | 1u))(win); }

/*
 * HandleExtCtrlCode — FC 子类型分派（对应 sub_8003110）。
 * 读参约定与原生一致：先取 text[index] 再 index++（单参）/连取（多参）。
 */
static int HandleExtCtrlCode(TextPrinter *win)
{
    const uint8_t *text = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    uint16_t index = win_u16(win, WIN_TEXT_INDEX);
    uint8_t type;
    uint8_t a1;

    if (index >= 0xFFFF)
        return 2;
    type = text[index];
    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 1));

    switch (type) {
    case FC_FG:
        win_set_u8(win, WIN_COLOR_C, text[win_u16(win, WIN_TEXT_INDEX)]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 2;
    case FC_BG:
        win_set_u8(win, WIN_COLOR_D, text[win_u16(win, WIN_TEXT_INDEX)]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 2;
    case FC_SHADOW:
        win_set_u8(win, WIN_COLOR_E, text[win_u16(win, WIN_TEXT_INDEX)]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 2;
    case FC_ALLCOLORS:
        a1 = text[win_u16(win, WIN_TEXT_INDEX)];
        win_set_u8(win, WIN_COLOR_C, a1);
        win_set_u8(win, WIN_COLOR_D, text[win_u16(win, WIN_TEXT_INDEX) + 1]);
        win_set_u8(win, WIN_COLOR_E, text[win_u16(win, WIN_TEXT_INDEX) + 2]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 3));
        return 2;
    case FC_PALETTE:
        win_set_u8(win, WIN_PALETTE, text[win_u16(win, WIN_TEXT_INDEX)]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 2;
    case FC_FONT:
        win_set_u8(win, WIN_FONTNUM_REAL, text[win_u16(win, WIN_TEXT_INDEX)]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 2;
    case FC_DEFAULTFONT: {
        uint8_t *tpl = win_template(win);
        win_set_u8(win, WIN_FONTNUM_REAL, tpl ? tpl[8] : 0);
        return 2;
    }
    case FC_PAUSE:
        win_set_u8(win, WIN_DELAY, text[win_u16(win, WIN_TEXT_INDEX)]);
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        win_set_u16(win, WIN_STATE, AXV_STATE_PAUSE);
        return 2;
    case FC_WAITBUTTON:
        win_set_u16(win, WIN_STATE, AXV_STATE_WAIT_BUTTON);
        return 2;
    case FC_WAITSOUND:
        win_set_u16(win, WIN_STATE, AXV_STATE_WAIT_SOUND);
        return 2;
    case FC_PLAYBGM: {
        uint8_t lo = text[win_u16(win, WIN_TEXT_INDEX)];
        uint8_t hi = text[win_u16(win, WIN_TEXT_INDEX) + 1];
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 2));
        axv_play_bgm((uint16_t)(lo | (hi << 8)));
        return 2;
    }
    case FC_PLAYSE: {
        uint8_t lo = text[win_u16(win, WIN_TEXT_INDEX)];
        uint8_t hi = text[win_u16(win, WIN_TEXT_INDEX) + 1];
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 2));
        axv_play_se((uint16_t)(lo | (hi << 8)));
        return 2;
    }
    case FC_ESCAPE: {
        uint8_t c = text[win_u16(win, WIN_TEXT_INDEX)];
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        DrawGlyph_CHS(win, c);
        return 1;
    }
    case FC_SHIFT_TILE_X:
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X)
                             + text[win_u16(win, WIN_TEXT_INDEX)]));
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 1;
    case FC_SHIFT_TILE_Y:
        win_set_u8(win, WIN_CURSOR_TILE_Y,
                   (uint8_t)(win_u8(win, WIN_CURSOR_TILE_Y)
                             + text[win_u16(win, WIN_TEXT_INDEX)]));
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(win_u16(win, WIN_TEXT_INDEX) + 1));
        return 1;
    case FC_CLEARWINDOW:
        axv_clear_window(win);
        return 2;
    default:
        return 2;
    }
}

/* =====================================================================
 * §15 主入口 [text.c L2080 PrintNextChar 整函数替换]
 * 订钉：main.asm .org 0x080032F8 → 本函数（Phase C 接线）。
 * ===================================================================== */
int ProcessCurrentChar_C(TextPrinter *win)
{
    uint32_t tptr;
    uint16_t index;
    uint8_t c;

    /* -- 复刻原生前 8 条指令：u16 回绕推进 + 取字符 -- */
    index = win_u16(win, WIN_TEXT_INDEX);
    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 1));
    tptr = win_u32(win, WIN_TEXT_PTR);
    c = *(const uint8_t *)(uintptr_t)(tptr + index);

    if (c >= PCS_CTRL_BASE) {
        switch (c) {
        case 0xFA:  /* 等 A 后滚动翻页（▼ 不清屏） */
            axv_draw_down_arrow(win);
            win_set_u16(win, WIN_STATE, AXV_STATE_WAIT_SCROLL);
            return 2;
        case 0xFB:  /* 等 A 后清屏（▼） */
            axv_draw_down_arrow(win);
            win_set_u16(win, WIN_STATE, AXV_STATE_WAIT_CLEAR);
            return 2;
        case 0xFC:
            return HandleExtCtrlCode(win);
        case 0xFD:  /* 占位符（展开由帧驱动在 PLACEHOLDER 态完成） */
            win_set_u16(win, WIN_STATE, AXV_STATE_PLACEHOLDER);
            return 2;
        case 0xFE:  /* 换行 */
            win_set_u16(win, WIN_STATE, AXV_STATE_NEWLINE);
            return 2;
        case 0xFF:  /* EOS */
            win_set_u16(win, WIN_STATE, AXV_STATE_END);
            return 0;
        default:    /* 0xFA..0xFF 之外不会到达 */
            break;
        }
    }

    if (c == PCS_MENU_CURSOR && win_u8(win, WIN_TEXTMODE) != 2u) {
        if (DrawMenuCursorEF(win))
            return 1;
        /* 未画出则按可印字符继续（引擎零回落） */
    }

    /* ---- F9 协议优先 ---- */
    if (c == CHS_ESCAPE) {
        const uint8_t *text =
            (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
        uint16_t idx2 = win_u16(win, WIN_TEXT_INDEX);
        const uint8_t *p = text + idx2;
        uint8_t op = p[0];

        if (op == 0) {
            uint32_t tp = win_u32(win, WIN_TEXT_PTR);
            if (idx2 == 1
                && (tp < ADDR_PHRASE_TABLE || tp >= ADDR_FONT_CHS_NORMAL))
                chs_bind_pitch_slot(win, 0)->write_op = 0;
            {
                uint8_t lead = p[1];
                uint8_t trail = p[2];
                uint16_t gidx;
                if (!lead_trail_ok(lead, trail)) {
                    /* 引擎零回落：坏编码消费掉并画空白（原为交原生画乱 tile） */
                    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx2 + 3));
                    return 1;
                }
                win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx2 + 3));
                gidx = pack_glyph_index(lead, trail);
                if (gidx >= CHS_FONT_GLYPH_MAX)
                    return 1;
                PrintGlyph_CHS_Adv(win, gidx, CHS_GLYPH_ADVANCE_PX);
                return 1;
            }
        }

        {
            volatile struct ChineseTileState *st = chs_bind_pitch_slot(win, 0);
            uint16_t code = (uint16_t)((p[1] << 8) | p[2]);
            int parent_cont = phrase_parent_continues(text, idx2);

            if (op == CHS_PHRASE_DEFAULT || parent_cont)
                st->write_op = 0;
            else
                st->write_op = op;

            if (parent_cont && inline_phrase_no_controls(win, idx2, code))
                return 1;

            redirect_phrase_stream(win, code);
            return 1;
        }
    }

    /* ---- type=slot：JP hex → 中文替换查找表 ---- */
    if (slot_lookup_and_draw(win, c))
        return 1;

    /* ---- 普通 JP PCS / Sym / 空白：CHS 同池 ---- */
    DrawGlyph_CHS(win, c);
    return 1;
}

/* =====================================================================
 * §16 过渡出口（订钉维持不变的三个外部钩 + 宽度工具）
 * ===================================================================== */

/* [P05] FA/FB 箭头前置相位同步（entry.s WaitArrow_Prepare 订钉不变）。
 * 注意：接管后 FA/FB 已由 §15 自绘路径处理，本钩仍服务于原生其它调用方。 */
void WaitArrow_Prepare_C(TextPrinter *win)
{
    volatile struct ChineseTileState *st;
    uint16_t cols;
    uint16_t off;
    uint8_t want;
    uint8_t cur_tx;

    if (!win)
        return;
    st = chs_bind_pitch_slot(win, 0);
    if (!st->chs_px)
        return;

    cols = (uint16_t)((st->chs_px + 7u) >> 3);
    want = (uint8_t)(st->base_tx + cols);
    cur_tx = win_u8(win, WIN_CURSOR_TILE_X);

    if (cur_tx == 0u && want > 0u) {
        off = win_u16(win, WIN_TILE_OFFSET);
        if (st->chs_px & 7u)
            win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
        Chinese_PitchReset(win);
        return;
    }

    win_set_u8(win, WIN_CURSOR_TILE_X, want);
    off = win_u16(win, WIN_TILE_OFFSET);
    if (st->chs_px & 7u)
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
    Chinese_PitchReset(win);
}

/* PCS 0xEF ► → CHS_MENU_CURSOR_TILE 固定对（InitMenu ▶）。 */
int DrawMenuCursorEF(TextPrinter *win)
{
    uint8_t buf[128];
    uint8_t *du;
    uint8_t *dl;
    struct GlyphTileInfo info;

    if (!win)
        return 0;
    if (!chs_font_is_shadowed(win_u8(win, WIN_FONTNUM_REAL)))
        return 0;

    /* ▶ 字形取制统一走 GetGlyph（归一化源），着色在渲染层 */
    if (!GetGlyph(win, PCS_MENU_CURSOR, buf))
        return 0;

    du = vram_tile(win, CHS_MENU_CURSOR_TILE);
    dl = vram_tile(win, CHS_MENU_CURSOR_TILE_HI);
    info.textMode = 0;
    info.colors = 0;
    info.startPixel = 0;
    info.width = 8;
    info.dest = (uint32_t *)(uintptr_t)du;
    info.src = buf + 0x00;
    DrawGlyphTile_CHS(win, &info, 0);
    info.dest = (uint32_t *)(uintptr_t)dl;
    info.src = buf + 0x20;
    DrawGlyphTile_CHS(win, &info, 0);
    chs_update_tilemap(win, CHS_MENU_CURSOR_TILE, CHS_MENU_CURSOR_TILE_HI);
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
    return 1;
}

/* [P04] 地名弹窗居中（对应 text.c Text_InitWindow_Centered 语义）。 */
uint32_t MapNamePopup_CalcLeftPx(const uint8_t *buf)
{
    uint32_t width_px = GetStringWidth_PCS(buf, MAPNAME_BUF_BYTES);

    if (width_px == 0 || width_px >= MAPNAME_FIELD_PX)
        return 0;
    return (((MAPNAME_FIELD_PX - width_px) / 2u) + (MAPNAME_CELL_PX / 2u))
           / MAPNAME_CELL_PX;
}

/* ---- CHS 文本流像素宽度 [text.c L3609 GetStringWidth 对应] ---- */
#define GETSTR_PHRASE_WALK_MAX 256u

static uint32_t phrase_width_px(const uint8_t *stream)
{
    uint32_t w = 0;
    uint32_t i = 0;

    if (!stream)
        return CHS_GLYPH_ADVANCE_PX;
    while (i < GETSTR_PHRASE_WALK_MAX && stream[i] != 0xFF) {
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

uint32_t GetStringWidth_PCS(const uint8_t *buf, uint32_t max_bytes)
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
