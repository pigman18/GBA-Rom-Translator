/* ============================================================================
 * text_scene.c — 窗口落址配置（声明式，一窗一条，键 = 窗口模板地址）
 *
 * ⚠ 本文件 = 配置 + 查表求值（合而为一，控制在 ~300 行）。
 *   改布局动本文件；渲染/相位在 text_render.c（bak 原样，勿动）。
 *
 * 新增一个 tm1/tm3 窗口的步骤：
 *   1. gdb 采该窗口 curY/curX 集合、每会话字数、引用字形 tile（=1+PCS*2）。
 *      **几何必须以日志为准，勿凭印象。**
 *   2. 排行基址/搬位带，改翻译后重跑 scripts/gen_tm1_slots.py。
 *   3. 本文件加一组 static 数据（指定初始化器）+ 追加进 kWindows[]。
 *   4. 跑 scripts/check_tm1_scene.py 自检。
 * ==========================================================================*/

#include "text_scene.h"
#include "text_render.h"        /* chs_pitch_write_op（mode2 默认路径用） */
#include "tile_alloc.h"

/* ---- 汉字固定槽表（PTR 区，scripts/gen_tm1_slots.py 生成，勿手改）--------
 * chs_slots.inc     —— 未选中态（普通色）
 * chs_slots_sel.inc —— 选中态（高亮色）；标签列不吃高亮，表为空（1 条哨兵）。
 * ⚠ 改翻译（增删汉字）后必须重新生成，否则新汉字查不到槽 → 回退 DYN。 */
#include "chs_slots.inc"
#include "chs_slots_sel.inc"

/* ============================================================================
 * §1 PTR 固定槽查询
 * ==========================================================================*/

static uint16_t chs_slot_of(uint32_t glyph)
{
    uint16_t g = (uint16_t)(glyph & 0xFFFFu);
    unsigned i;

    for (i = 0u; i < sizeof(kOptChsSlots) / sizeof(kOptChsSlots[0]); i++) {
        if (kOptChsSlots[i].glyph == g)
            return kOptChsSlots[i].slot;
    }
    return 0u;                       /* 未登记 → 调用方回退 DYN */
}

static uint16_t chs_sel_slot_of(uint32_t glyph)
{
    uint16_t g = (uint16_t)(glyph & 0xFFFFu);
    unsigned i;

    for (i = 0u; i < sizeof(kOptChsSelSlots) / sizeof(kOptChsSelSlots[0]); i++) {
        if (kOptChsSelSlots[i].glyph == g)
            return kOptChsSelSlots[i].slot;
    }
    return 0u;
}

/* PTR 取槽：选中态用红色镜像槽（DrawOptionMenuChoice 写 OPT_FG_COLOR），
 * 未登记汉字退回普通槽——只会被染成选中色，不会顶掉别的字。 */
static uint16_t chs_ptr_base(uint32_t glyph)
{
    uint8_t fg_ov = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;

    if (fg_ov == (uint8_t)OPT_FG_SELECTED) {
        uint16_t sel = chs_sel_slot_of(glyph);

        if (sel != 0u)
            return sel;
    }
    return chs_slot_of(glyph);
}

/* ============================================================================
 * §2 窗口配置（数据）
 * ==========================================================================*/

/* ---- 设置（选项）窗口 — 模板 0x081BB874 ----------------------------------
 * 几何（gdb [CFF] 实测）：标题 curY=1；菜单行 curY=5..17（步 2）。
 * 候选 curX：慢@15 普通@19 快@23 ｜ 看@15 不看@23 ｜ 替换@15 打到底@22
 *            ｜ 单声道@15 立体声@22 ｜ 普通@15 LR/L(原生) ｜ 类型/7(原生)。
 * 行基址整段避开引用字形 33/49/111/139/255/323。
 * ⚠ r1..r6 全有中文候选，span 不能给 0（span=0 ⇒ win[0x18] 不复位 ⇒ 越界写，
 *   2026-08-29 实证）。r7(关闭) 无候选。 */
static const uint16_t kOptRows[7] = {
    0x033u,  /*  51  r1 对话速度   慢/普通/快 */
    0x08Du,  /* 141  r2 战斗动画   看/不看 */
    0x0ADu,  /* 173  r3 对战规则   替换/打到底 */
    0x0CDu,  /* 205  r4 声音       单声道/立体声 */
    0x101u,  /* 257  r5 按键模式   普通/LR/L ← "普通"是中文 */
    0x121u,  /* 289  r6 窗口       类型/7 */
    0x121u,  /* 289  r7 关闭       不用（无候选项） */
};

static const uint8_t kOptRowSpans[7] = {
    32u, 32u, 32u, 32u, 32u, 32u, 0u,
};

/* 容量算法：12px n 字最大 off = 4n-2，占 4n tile。
 * 同一行多个候选是独立打印会话，必须按 curX 分区，共用一段会互覆。
 * ⚠ "打到底/立体声"（3 字）在 cx=22：off=22、span=10 才收得进 32-tile 行界。 */
static const struct Tm1Zone kOptZones[] = {
    /* 标签列：固定槽 + 12px 字模 ⇒ 16px 步进。
     * ⚠ 别用 8px 小字库（FontChsSmall）画标签：字形有误（"战"→"対"实测）。 */
    { .cx_hi = 8u,   .strategy = TM1_ZONE_PTR, .font = 0u },
    { .cx_hi = 19u,  .strategy = TM1_ZONE_DYN, .font = 0u, .off = 0u,  .span = 12u },
    { .cx_hi = 22u,  .strategy = TM1_ZONE_DYN, .font = 0u, .off = 12u, .span = 10u },
    { .cx_hi = 0xFFu,.strategy = TM1_ZONE_DYN, .font = 0u, .off = 22u, .span = 10u },
};

/* ---- 图鉴条目屏 — 模板 0x081BB5BC（GRID：图标/盒子带需搬位）--------------*/
static const struct TileRemap kSummaryRemaps[] = {
    { .lo = CHS_UI_ICON_TILE_LO, .hi = CHS_UI_ICON_TILE_HI, .alt = CHS_UI_ICON_TILE_ALT },
    { .lo = CHS_PSS_B_VRAM_LO,   .hi = CHS_PSS_B_VRAM_HI,   .alt = CHS_PSS_B_VRAM_ALT },
};

/* ============================================================================
 * §2b gdb 采集登记（2026-08-30，来源 work/gdb_patcher_log.log）
 * 场景归属以 [InitTextPrinter] 日志的打印内容为准，不是猜的。
 * ==========================================================================*/

/* ---- 开始菜单 / 主菜单 — 模板 0x081BB46C（tm3 GRID，fn3）------------------
 * 日志实证：'ずかん/宝可梦/背包/领航员/保存/设置/退出/►'（开始菜单 8 项，
 * 左列 x=0..）+ '\CC010E继续游戏'（主菜单续档窗，右侧 x≥21：冒险时间/图鉴数）。
 * bak 的 mode2 menu 分支（CHS_MODE2_MENU_BAND=0x17A / ORIGIN_MENU=0x20 /
 * CHS_PARTY_MENU_LEFT=20 / TOP=13）只对本窗 x≥20 的深列生效 → 配置为 region。 */
static const struct Mode2Region kStartMenuRegions[] = {
    { .x_min = 20u, .y_min = 13u, .x_add = 1u, .y_sub = 13u,
      .band = CHS_MODE2_MENU_BAND, .origin = CHS_MODE2_ORIGIN_MENU },
};

/* ---- 对战菜单/选项窗 — 模板 0x081BB484（tm1 GRID，fn3）--------------------
 * 日志实证：'请选择/要做什么/查看能力/排序/携带物品/攀瀑/潜水'，候选列
 * x=0..1 与 21..22（右列），奇数行 curY=7..17。无搬位（官方公式+origin2）。 */

/* ---- 战斗对话窗 — 模板 0x081BB3F4（tm0，fn3）------------------------------
 * 日志实证：'野生的…跳出来了/ゆけっ！/怎么办/战斗 背包'，TILE_BASE 0x90/0x190
 * （高区，自带安全距离）→ floor 必须为 0（bak 对 battle 直接跳过 floor；
 * 未登记 fallback 的 floor=4 会把战斗对话首字推右 4 tile）。 */

/* ---- 队伍名单窗 — 模板 0x081BB43C（tm1，fn4 8px 小字）---------------------
 * 日志实证：'ＭＥＷ/ＥＸＰＬＯ/ジグザグマ/ラグラージ'，charBase=1、
 * tileData=0x06004000 独立区 → 线性直写安全，无需地板。 */

static const struct WinCfg kOptWindow = {
    .name         = "OPTION",
    .tpl          = 0x081BB874u,
    .use_linear   = 1u,
    .row_tab      = kOptRows,
    .row_span_tab = kOptRowSpans,
    .row_tab_n    = 7u,
    .row_y0       = 3u,          /* r = (curY-3)>>1 → curY 5..17 ⇒ 行 1..7 */
    .row_shift    = 1u,
    .floor        = 0u,          /* 行内偏移由 zones 复位，不需要地板 */
    .zones        = kOptZones,
    .zone_n       = sizeof(kOptZones) / sizeof(kOptZones[0]),
};

static const struct WinCfg kSummaryWindow = {
    .name       = "SUMMARY",
    .tpl        = CHS_SUMMARY_TEMPLATE,
    .use_linear = 0u,              /* GRID */
    .remaps     = kSummaryRemaps,
    .remap_n    = sizeof(kSummaryRemaps) / sizeof(kSummaryRemaps[0]),
};

static const struct WinCfg kStartMenuWindow = {
    .name       = "START_MENU",    /* 开始菜单 + 主菜单续档窗（同一模板） */
    .tpl        = 0x081BB46Cu,
    .use_linear = 0u,              /* GRID */
    .regions    = kStartMenuRegions,
    .region_n   = sizeof(kStartMenuRegions) / sizeof(kStartMenuRegions[0]),
};

static const struct WinCfg kChoiceMenuWindow = {
    .name       = "CHOICE_MENU",   /* 对战/队伍的操作选项窗 */
    .tpl        = 0x081BB484u,
    .use_linear = 0u,              /* GRID，无搬位 */
};

static const struct WinCfg kBattleDialogWindow = {
    .name       = "BATTLE_DIALOG",
    .tpl        = 0x081BB3F4u,
    .use_linear = 1u,              /* tm0 本就线性；登记为的是 floor=0 */
    .floor      = 0u,
};

static const struct WinCfg kPartyNameWindow = {
    .name       = "PARTY_NAME",
    .tpl        = 0x081BB43Cu,
    .use_linear = 1u,              /* fn4 小字，charBase=1 独立 tile 区 */
    .floor      = 0u,
};

static const struct WinCfg kNamingConfirmWindow = {
    .name       = "NAMING_CONFIRM",
    .tpl        = 0x081BB694u,
    .use_linear = 0u,              /* GRID，默认路径（'你的名字是'） */
};

const struct WinCfg *const kWindows[] = {
    &kOptWindow,
    &kSummaryWindow,
    &kStartMenuWindow,
    &kChoiceMenuWindow,
    &kBattleDialogWindow,
    &kPartyNameWindow,
    &kNamingConfirmWindow,
};

const unsigned kWindowN = sizeof(kWindows) / sizeof(kWindows[0]);

const struct WinCfg *scene_lookup(uint32_t tpl)
{
    unsigned i;

    for (i = 0u; i < kWindowN; i++) {
        if (kWindows[i]->tpl == tpl)
            return kWindows[i];
    }
    return 0;                    /* 未登记 → NULL，官方字段兜底，禁止猜场景 */
}

/* ============================================================================
 * §3 行基址 / 分区选择（PTR+DYN 的 per-glyph 绑定）
 * ==========================================================================*/

/* 行基址：r = (curY - row_y0) >> row_shift，clamp 到 [1, row_tab_n]。 */
static uint16_t cfg_row_base(const struct WinCfg *cfg, uint8_t cur_y)
{
    unsigned r;

    if (cur_y <= cfg->row_y0) {
        r = 1u;
    } else {
        r = (unsigned)(cur_y - cfg->row_y0) >> cfg->row_shift;
        if (r < 1u)
            r = 1u;
        if (r > cfg->row_tab_n)
            r = cfg->row_tab_n;
    }
    return cfg->row_tab[r - 1u];
}

/* ---- 当前字的 PTR 绑定（note_glyph 填写，gctn_linear / floor 消费）------
 *
 * ⚠⚠ 必须落 **RAM 绝对地址**，**不能**用文件级 static（2026-08-30 根因实证）：
 *   link/game.ld 只声明了 ROM 段，SECTIONS 里也没有 .data/.bss 规则 ⇒
 *   链接器把 .bss 当孤儿段塞进 ROM（out/game.map：.bss 0x08803DB0，8 字节，
 *   全部来自 text_scene.o）⇒ 对它的 strh **写不进**（ROM 只读）⇒ 读回恒为
 *   打包时该地址的内容（实测 00 00 00 00 00 00 00 00）⇒ s_ptr_base 恒 0
 *   ⇒ PTR 永不激活、DYN 区复位也永不执行 ⇒ "左 16px 右 12px"整体失效。
 *   （那是 v4 把"渲染层感知 PTR"改成"static 变量传递"时踩的坑：v3 用局部
 *   值传递所以没事，v4 的 static 一律落 ROM。）
 *   → 与 CHS_LAST_OFF_ADDR(0x0203FF82) 同一路子：显式 EWRAM 绝对地址。
 *   落 0x0203FF8E：PITCH_CTRL(FF80..FF8B) 与 PITCH_SLOTS(FF90..FFCF) 之间的
 *   4B 空隙，在实证安全区 0x0203FF80-FFCF 之内。
 *   （2026-08-30 从 FF8C 下移 2B：FF8C 让给 CHS_LAST_ROW_KEY 行键。）
 *
 * 只需跨函数传 **一个** u16，其余现算：
 *   ptr_delta → gctn_linear 里算（= ptr_base-(tileBase+off)）；
 *   dyn_off/span → floor 里用 scene_zone_of() 重算（zone 只依赖 curX，
 *                  不依赖 glyph，所以 floor 不需要 glyph_id）。
 * 既省 RAM，也顺带根除"delta 在 off 被改写后过期"这一类时序问题。
 *
 * ⚠ PTR 落址**必须**走 base+off+delta 形式：bak 渲染核的 pass2 仍传 xOff=0，
 *   它靠 pass1 后无条件的 off+=2 区分两趟落址。PTR 若直接返回
 *   ptr_base+2*xOff，pass2 会落回 +0/+1 把左半覆盖掉（标签只剩残字）。
 *   delta = ptr_base-(tileBase+off) ⇒ pass1 返回 ptr_base，pass2（off 已 +2）
 *   自动返回 ptr_base+2 —— 与 DYN 同构。 */
#define ADDR_SCENE_PTR_BASE 0x0203FF8Eu   /* FF8C = CHS_LAST_ROW_KEY（见 text_render.c） */

static uint16_t scene_ptr_base_get(void)
{
    return *(volatile uint16_t *)ADDR_SCENE_PTR_BASE;
}

static void scene_ptr_base_set(uint16_t v)
{
    *(volatile uint16_t *)ADDR_SCENE_PTR_BASE = v;
}

/* 分区选择：只依赖 (cfg, curX)，不依赖 glyph —— note_glyph 与 floor 共用。
 * 命中第一条 cx < cx_hi；全不中则取末条（约定 cx_hi = 0xFF 兜底）。 */
static const struct Tm1Zone *scene_zone_of(const struct WinCfg *cfg, uint8_t cx)
{
    unsigned i;

    if (cfg == 0 || cfg->zones == 0 || cfg->zone_n == 0u)
        return 0;
    for (i = 0u; i < cfg->zone_n; i++) {
        if (cx < cfg->zones[i].cx_hi)
            return &cfg->zones[i];
    }
    return &cfg->zones[cfg->zone_n - 1u];
}

void scene_note_glyph(TextPrinter *win, uint16_t glyph_id)
{
    const struct WinCfg *cfg;
    const struct Tm1Zone *z;
    uint32_t glyph;

    scene_ptr_base_set(0u);

    if ((win_u8(win, WIN_TEXTMODE) & 7u) != 1u)
        return;                              /* PTR/DYN 只服务 tm1 */
    if (!(glyph_id & 0x8000u))
        return;                              /* 只有 F9 汉字带 0x8000 标记；
                                              * SYM/日文字形不绑槽 */
    cfg = scene_lookup((uint32_t)(uintptr_t)win_template(win));
    z = scene_zone_of(cfg, win_u8(win, WIN_CURSOR_X));
    if (z == 0 || z->strategy != TM1_ZONE_PTR)
        return;                              /* DYN：off/span 由 floor 重算 */

    glyph = glyph_id & 0x1FFFu;
    {
        uint16_t pb = chs_ptr_base(glyph);   /* 未登记汉字 = 0 → 回退 DYN */

        if (pb != 0u)
            scene_ptr_base_set(pb);
    }
}

uint8_t scene_is_ptr_mode(TextPrinter *win)
{
    (void)win;
    return (scene_ptr_base_get() != 0u) ? 1u : 0u;
}

/* ============================================================================
 * §4 scene 接口（与 bak/text_original 同名同签名）
 * ==========================================================================*/

/* tm2 血条缓冲 / tm1+font4+tilemap0 队伍窗：整窗交还官方 PrintNextChar。 */
int scene_is_buffer_printer(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);

    if (win_u8(win, WIN_TEXTMODE) == 2u)
        return 1;
    if (!tpl || win_u8(win, WIN_TEXTMODE) != 1u)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 4u)
        return 0;
    return win_u32(tpl, TPL_TILEMAP) == 0u;
}

int scene_delegate_buffer_print(TextPrinter *win)
{
    /* 跳板 → ROM 0x08003300（entry.s）；勿对旧 incbin 副本取址。 */
    return PrintNextChar_Origin(win);
}

/* 线性/GRID 分派。
 *   tm0/tm2 → 线性（官方语义）；
 *   登记窗口 → 按配置；
 *   未登记 → 官方字段兜底：font3（阴影菜单字体）= GRID 族，其余线性。
 * （bak 对未识别窗口的 fallback 与此一致，但 bak 还叠了 tileBase/光标猜测，
 *   那些已废弃；猜错过的窗口以后靠登记修正，不靠猜。） */
int scene_should_use_linear(TextPrinter *win, uint8_t write_op)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
    const struct WinCfg *cfg;

    (void)write_op;
    if (tm == 0u || tm == 2u)
        return 1;
    cfg = scene_lookup((uint32_t)(uintptr_t)win_template(win));
    if (cfg)
        return cfg->use_linear;
    return win_u8(win, WIN_FONTNUM_REAL) != FONT_NORMAL_SHADOWED;
}

/* 行首落址准备（DrawGlyphTiles_core 在 chs_px==0 即行首字时调用一次）：
 *   1. DYN 区复位：win[0x18] 越出本区 → 回区头（幂等，重绘从区头开始）；
 *   2. 地板：登记窗口按 cfg->floor；未登记沿用 bak 默认
 *      （charBase==2 的窗口 0x100，其余 4 —— charBase 是官方字段）。
 * PTR 不用 win[0x18]（槽位固定），跳过复位。 */
void scene_apply_linear_floor(TextPrinter *win)
{
    const struct WinCfg *cfg;
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    uint16_t floor;

    cfg = scene_lookup((uint32_t)(uintptr_t)win_template(win));
    if (cfg) {
        if (scene_ptr_base_get() == 0u) {
            const struct Tm1Zone *z =
                scene_zone_of(cfg, win_u8(win, WIN_CURSOR_X));

            if (z != 0 && z->span != 0u) {
                if (off < z->off
                    || off >= (uint16_t)(z->off + z->span))
                    win_set_u16(win, WIN_TILE_OFFSET, z->off);
            }
        }
        if (cfg->floor != 0u) {
            off = win_u16(win, WIN_TILE_OFFSET);
            if (off < cfg->floor)
                win_set_u16(win, WIN_TILE_OFFSET, cfg->floor);
        }
        return;
    }

    {
        uint8_t *tpl = win_template(win);

        floor = (tpl && tpl[1] == 2) ? CHS_MENU_LINEAR_FLOOR : 4u;
    }
    if (off < floor)
        win_set_u16(win, WIN_TILE_OFFSET, floor);
}

/* 线性落址：tile 号（remap 前）。
 *   PTR      → 槽基址 + 2*xOff + yOff（与 win[0x16]/win[0x18] 无关）
 *   tm1 登记 → 行基址(配置表) + win[0x18]
 *   tm1 未登记 → tile_alloc 行位分段（图鉴），公式同官方线性
 *   tm0/tm2    → 官方公式 win[0x16] + win[0x18]（零配置直通） */
uint16_t scene_gctn_linear(TextPrinter *win, unsigned xOff, unsigned yOff)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
    const struct WinCfg *cfg;
    uint16_t base;
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);

    if (scene_ptr_base_get() != 0u) {
        /* PTR 固定槽：一字独占 4 个连续 tile，落址与 off/tileBase 无关。
         * pass1 传 xOff=0 得 +0/+1；pass2 传 xOff=1 得 +2/+3。
         * 此前用 delta = ptr_base-(tileBase+off) 想复用 off 推进，但 off 在
         * pass1 后被 +2，delta 同步抵消 ⇒ pass2 仍落回 +0/+1，右半覆盖左半，
         * 标签列显示成 "1" 状碎片（bug/20260830/12.PNG）。 */
        return scene_remap_tile(
            win, (uint16_t)(scene_ptr_base_get() + 2u * xOff + yOff));
    }

    if (tm == 1u) {
        cfg = scene_lookup((uint32_t)(uintptr_t)win_template(win));
        if (cfg && cfg->row_tab)
            base = cfg_row_base(cfg, win_u8(win, WIN_CURSOR_Y));
        else {
            tile_alloc_tm1_row(win);         /* 幂等：off!=0 即已分配 */
            base = win_u16(win, WIN_TILE_BASE);
        }
    } else {
        base = win_u16(win, WIN_TILE_BASE);  /* tm0 官方公式 */
    }

    return scene_remap_tile(win, (uint16_t)(base + off + 2u * xOff + yOff));
}

/* GRID 落址：官方公式 idx = tileBase + (curX+tile_x+2) + y*30 之上做搬位修正。
 *
 * 全局规则（对应 bak mode2_apply 的公共路径）：
 *   F9 80 短语 op 挂起 / y≤20 且偶数（标题行）→ 官方公式原样；
 *   origin 仅 charBase==2 时默认 2（bak 的 ORIGIN_SHOP 兜底）。
 * 区域规则（cfg->regions，按序命中第一条）：x/y 阈值 → x_add/y_sub/band/origin。
 *   未登记窗口 = 只有全局规则（与 bak 默认路径一致）。
 * 待办：队伍页脚（band 0x2A0，y/=8）未迁移——gdb 日志无该场景，
 *   有数据后以 region（或加 y_div 字段）登记，不恢复启发式。 */
void scene_gctn_mode2(TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower)
{
    const struct WinCfg *cfg;
    uint8_t *tpl = win_template(win);
    int x = (int)win_u8(win, WIN_CURSOR_X) + tile_x;
    int y = (int)win_u8(win, WIN_CURSOR_Y) + (int)win_u8(win, WIN_CURSOR_TILE_Y);
    int band = 0;
    int origin = (tpl && tpl[1] == 2) ? CHS_MODE2_ORIGIN_SHOP : 0;
    unsigned i;
    uint32_t idx;

    /* ⚠ cfg 必须显式查表赋值（2026-08-30 修复）：此前只声明未赋值就参与
     * `cfg != 0` 判断（编译器 -Wall: 'cfg' may be used uninitialized），
     * 区域搬位规则时灵时不灵，取决于栈垃圾。 */
    cfg = scene_lookup((uint32_t)(uintptr_t)tpl);

    if (chs_pitch_write_op(win) == 0u
        && !(y <= 20 && (y & 1) == 0)
        && cfg != 0) {
        for (i = 0u; i < cfg->region_n; i++) {
            const struct Mode2Region *r = &cfg->regions[i];

            if (x >= (int)r->x_min && y >= (int)r->y_min) {
                x += r->x_add;
                y -= r->y_sub;
                band   = (int)r->band;
                origin = (int)r->origin;
                break;
            }
        }
    }

    idx = (uint32_t)(y * CHS_TILE_GRID_W + x + band);
    idx += win_u16(win, WIN_TILE_BASE);
    idx += (uint32_t)origin;
    *upper = scene_remap_tile(win, (uint16_t)idx);
    *lower = scene_remap_tile(win, (uint16_t)(idx + CHS_TILE_GRID_W));
}

/* tile remap：中文/槽表不得占用的 tile 搬到 alt 区。
 *   登记窗口 → 配置的 remaps 区间表；
 *   未登记   → bak 全局默认（▶ 字形 / 菜单光标 / UI 图标——声明式常量区间）。
 * （bak 对 battle 窗口跳过 remap；v2 未做 battle 特判——battle 的中文 tile
 *   落在官方线性区，与这些保留区间不重叠，实测若发现冲突再登记。） */
uint16_t scene_remap_tile(TextPrinter *win, uint16_t tile)
{
    const struct WinCfg *cfg;
    unsigned i;

    (void)win;
    if (tile >= CHS_MENU_CURSOR_TILE && tile <= CHS_MENU_CURSOR_TILE_HI)
        return (uint16_t)(CHS_MENU_CURSOR_TILE_ALT + (tile - CHS_MENU_CURSOR_TILE));
    if (tile >= CHS_UI_ICON_TILE_LO && tile <= CHS_UI_ICON_TILE_HI)
        return (uint16_t)(CHS_UI_ICON_TILE_ALT + (tile - CHS_UI_ICON_TILE_LO));

    cfg = scene_lookup((uint32_t)(uintptr_t)win_template(win));
    if (cfg) {
        for (i = 0u; i < cfg->remap_n; i++) {
            const struct TileRemap *r = &cfg->remaps[i];

            if (tile >= r->lo && tile <= r->hi)
                return (uint16_t)(r->alt + (tile - r->lo));
        }
    }
    return tile;
}
