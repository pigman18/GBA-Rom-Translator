/* ============================================================================
 * text_scene.h — tm1 窗口布局：数据结构 + 查询接口
 *
 * 设计边界（2026-08-29 与用户确认）：
 *   ✅ 允许：以**窗口模板地址**为唯一键的静态配置表，一窗一条，数字显式写出。
 *   ❌ 禁止：启发式门控——靠 tileBase 区间 / 光标值 / 模板字段去"猜"当前场景
 *      （旧 bak/text_original/text_scene.c 的 screen_menu_mode2 等属此类）。
 *
 * 为什么必须是 per-window 配置（而不是一套通用公式）：
 *   tm1 每个窗口的预渲染字库都铺满 tile [1,513)（tile = startOffset + glyph*2）。
 *   "哪些 tile 是空的"取决于该窗口实际引用了哪些字形——天生的 per-window 数据。
 *
 * 布局只有一种：**PTR 区 + DYN 区**（按 curX 分区）。
 *   PTR（固定槽）：一字一固定槽（chs_slots.inc，构建期生成），每字独占
 *     2 个 tilemap 列 ⇒ 16px 步进。幂等——重绘必然落在同一处，用于标签列。
 *   DYN（动态分配）：相邻字共享 tile ⇒ 12px 步进，紧凑。落址 = 行基址 +
 *     行内偏移(win[0x18])，靠 zone 的 off/span 做会话复位；选中色只是换个
 *     前景色重画一遍，不占额外 tile。
 *   数值配置在 text_scene.c，查表/求值在 text_layout.c。
 *   （历史模式 PARTITION / GRID / PTR-整窗已退役删除，要翻旧账用 git 历史。）
 * ==========================================================================*/
#ifndef TEXT_SCENE_H
#define TEXT_SCENE_H

#include "game.h"
#include "text.h"

/* 分区策略 */
#define TM1_ZONE_PTR  0u   /* 固定槽（查 chs_slots.inc），16px 步进 */
#define TM1_ZONE_DYN  1u   /* 动态分配，12px 步进 */

/* 一个分区：curX < cx_hi 命中本区；zone 表按 cx_hi 升序，**末条必须 0xFF 兜底** */
struct Tm1Zone {
    uint8_t cx_hi;
    uint8_t strategy;   /* TM1_ZONE_PTR / TM1_ZONE_DYN */
    uint8_t font;       /* 字模：0 = 12px 常规，4 = 8px 小字 */
    uint8_t off;        /* DYN：行内 tile 偏移（相对行基址）；PTR 不用 */
    uint8_t span;       /* DYN：容量，须 ≥ 该区最大推进量；PTR 不用 */
};

/* 分区选择结果 —— 由 tm1_zone_select() 填充，调用方直接用 */
struct Tm1ZoneSel {
    uint8_t  strategy;  /* TM1_ZONE_PTR / TM1_ZONE_DYN */
    uint8_t  font;      /* 字模：0 = 12px，4 = 8px */
    uint16_t ptr_base;  /* PTR：槽基址；DYN：0 */
    uint16_t off;       /* DYN：行内起点；PTR：忽略 */
    uint16_t span;      /* DYN：容量；PTR：忽略 */
};

/* ---- tm1 窗口布局配置（用**指定初始化器**，防字段错位）-------------------*/
struct Tm1WinCfg {
    const char     *name;           /* 仅用于调试/日志，运行时不影响落址 */
    uint32_t        tpl;            /* 窗口模板地址 = 唯一键 */

    /* 行基址（DYN 候选列用；PTR 标签列不吃行区） */
    const uint16_t *row_tab;        /* 行基址表，下标 = 行号-1 */
    const uint8_t  *row_span_tab;   /* 每行**预留** tile 数（0 = 该行无中文候选）。
                                     * ⚠ 不能为了省事给有中文的行填 0：span=0 会让
                                     * 该行中文不复位 win[0x18] 而写到越界地址。 */
    uint8_t         row_tab_n;
    uint8_t         row_y0;         /* 行号推导：r = (curY - row_y0) >> row_shift */
    uint8_t         row_shift;

    /* 列分区规则表（按 cx_hi 升序，末条 cx_hi = 0xFF 兜底） */
    const struct Tm1Zone *zones;
    uint8_t         zone_n;

    /* 该窗口**已实测被引用的字形 tile**（各占 2 格）+ 已知特殊保留区。
     * 运行时不读，供离线自检核对"中文区/槽表有没有踩到它们"。
     * ⚠ 集合可能不完整：发现新乱码字符 → 反推 tile(=1+PCS*2) → 加进来。 */
    const uint16_t *glyph_avoid;
    uint8_t         glyph_avoid_n;
};

/* ---- 窗口登记表（数据在 text_scene.c，算法在 text_layout.c）--------------
 * 新增窗口：text_scene.c 加一组 static 数据（指定初始化器）并追加到这里，
 * 算法侧不用动；然后重跑 gen_tm1_slots.py 与 check_tm1_scene.py。 */
extern const struct Tm1WinCfg *const kTm1Windows[];
extern const unsigned kTm1WindowN;

/* 按模板地址查表；未登记返回 NULL（调用方回退线性式，不猜场景）。 */
const struct Tm1WinCfg *scene_tm1_lookup(uint32_t tpl);

/* 行基址：r = (curY - row_y0) >> row_shift，clamp 到 [1, row_tab_n]。
 * curY <= row_y0 的会话（标题/标签）在当前配置下走 PTR，不会到这里；
 * 防御起见 clamp 到第 1 行。 */
uint16_t scene_tm1_row_base(const struct Tm1WinCfg *cfg, uint8_t cur_y);

/* 分区选择：按当前 curX 命中 zones 表，填好 *out：
 *   PTR 区 → ptr_base = 该汉字的固定槽（未登记汉字回退普通槽）
 *   DYN 区 → off/span = 该区的行内偏移与容量
 * 未登记窗口 → out 保持默认（DYN/off0/span0），绝不给半初始化的值。 */
void tm1_zone_select(TextPrinter *win, uint32_t glyph, struct Tm1ZoneSel *out);

#endif /* TEXT_SCENE_H */
