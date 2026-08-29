/* ============================================================================
 * text_scene.h — tm1 窗口布局的**声明式配置表**
 *
 * 设计边界（2026-08-29 与用户确认）：
 *   ✅ 允许：以**窗口模板地址**为唯一键的静态配置表，一窗一条，数字显式写出。
 *   ❌ 禁止：启发式门控——靠 tileBase 区间 / 光标值 / 模板字段去"猜"当前场景
 *      （旧 bak/text_original/text_scene.c 的 screen_menu_mode2 / screen_shop_bag
 *      / screen_party_footer 属此类，会误判且难验证）。
 *
 * 为什么必须是 per-window 配置（而不是一套通用公式）：
 *   tm1 每个窗口的预渲染字库都铺满 tile [1,513)（tile = startOffset + glyph*2）。
 *   "哪些 tile 是空的"取决于**该窗口实际引用了哪些字形** —— 这是天生的
 *   per-window 数据，不存在场景无关的通用解。
 *
 * 本文件只放**数据结构与查询接口**；具体数值一律在 text_scene.c 的表里。
 * 未登记的模板 → scene_tm1_lookup 返回 NULL，调用方回退线性式，**不猜场景**。
 * ==========================================================================*/
#ifndef TEXT_SCENE_H
#define TEXT_SCENE_H

#include "game.h"
#include "text.h"

/* ---- 候选列槽（值列）----------------------------------------------------
 * cx_hi：curX < cx_hi 命中本槽；**最后一条必须填 0xFF 兜底**。
 * off  ：行内 tile 偏移（相对行基址）。
 * span ：容量。会话复位判据是 `off < start || off >= start+span`，
 *        所以 span 必须 ≥ 该槽最大字数所需的推进量（12px 每字 4，8px 每字 2）。
 * ------------------------------------------------------------------------*/
struct Tm1Slot {
    uint8_t cx_hi;
    uint8_t off;
    uint8_t span;
};

/* ---- 布局模式 ------------------------------------------------------------
 * PARTITION（分配式）
 *   行基址表 + 列子区。省 tile、不越界、可静态证明安全；
 *   但要预知文本结构（一行几个候选 / 每候选几个字），
 *   为了塞进可用区间常常得给候选列降 8px。
 *
 * GRID（位置式，bak 的做法）
 *   tile = grid_base + (y-y0)*stride + (x-x0)，lower = upper + stride。
 *   每个屏幕格子固定占一格，**不分配、不记账** → 不依赖文本结构，
 *   全 12px 也装得下，且天然幂等。
 *   代价：格位需求 ≈ 列数 × 行数，容易越出 charblock2(512)；
 *   且会覆盖大半个预渲染字库（只影响本窗口自己的非中文字符，
 *   不影响其它界面——切场景时 VRAM 会重载）。
 *   ⚠ 若算到 tile ≥ 512 就是 charblock3，那里可能被其它窗口当 tilemap 用
 *     （实测见过 0x0600F800 = screenblock 31）→ **有可能影响其它界面**。
 *     用 scripts/check_tm1_scene.py 校验并让它搜一个安全的 grid_base。
 * ------------------------------------------------------------------------*/
#define TM1_MODE_PARTITION 0u
#define TM1_MODE_GRID      1u
#define TM1_MODE_PTR       2u
#define TM1_MODE_MIX       3u

/* ---- 混合模式（TM1_MODE_MIX）--------------------------------------------
 * 按 curX 把一行切成若干**区**，每区独立选排版策略与字模。
 *
 *   PTR（固定槽）：一字一槽，每字独占 2 个 tilemap 列 ⇒ **16px 步进**。
 *     幂等 —— 同一汉字永远落在同一处，重绘不漂移、光标怎么动都不串。
 *     代价：字模只有 12px，格子 16px，右边空 4px（看起来偏散）。
 *
 *   DYN（动态分配）：相邻字共享中间那个 tile ⇒ **12px 步进**，紧凑。
 *     落址 = 行基址 + 行内偏移(win[0x18])，靠 off/span 做会话复位。
 *     选中态不占额外 tile —— 换个前景色**重画一遍**即可。
 *
 * 两者可以共存：文字固定、求稳的一段用 PTR；要紧凑的一段用 DYN。
 * 设置菜单的做法：标签列 curX<8 → PTR；候选列 → DYN 12px（分 A/B/C 三槽，
 * 因为同一行的多个候选是各自独立的打印会话，必须分开，否则互相覆盖）。
 * ------------------------------------------------------------------------*/
#define TM1_ZONE_PTR  0u   /* 固定槽，16px 步进 */
#define TM1_ZONE_DYN  1u   /* 动态分配，12px 步进 */

struct Tm1Zone {
    uint8_t cx_hi;      /* curX < cx_hi 命中本区；**末条必须填 0xFF 兜底** */
    uint8_t strategy;   /* TM1_ZONE_PTR / TM1_ZONE_DYN */
    uint8_t font;       /* 字模：0 = 12px 常规，4 = 8px 小字 */
    uint8_t off;        /* DYN：行内 tile 偏移（相对行基址）；PTR 忽略 */
    uint8_t span;       /* DYN：容量，须 ≥ 该区最大推进量；PTR 忽略 */
};

/* 分区选择结果 —— 由 tm1_zone_select() 填充，调用方直接用 */
struct Tm1ZoneSel {
    uint8_t  strategy;  /* TM1_ZONE_PTR / TM1_ZONE_DYN */
    uint8_t  font;      /* 字模：0 = 12px，4 = 8px */
    uint16_t ptr_base;  /* PTR：槽基址；DYN：0 */
    uint16_t off;       /* DYN：行内起点；PTR：忽略 */
    uint16_t span;      /* DYN：容量；PTR：忽略 */
};

/* ---- 指针模式（TM1_MODE_PTR）--------------------------------------------
 * 「指针直接指向字」：每个汉字占用一块**本窗口未引用的字形槽**，
 * 表项（指针）直接指向它。与另两种模式的根本区别：
 *
 *   PARTITION / GRID 都是在**字库之外**给中文找地方，可 tm1 字库已占满
 *   [1,513)，怎么找都会撞（镜像只是把冲突移到槽区，本质没变）。
 *   指针模式反过来——**中文就用字库自己的空槽**：
 *     · 不额外占用任何 tile
 *     · 槽位固定 → 幂等，上下移动重绘必然落在同一处
 *     · 槽位取自未被引用的字形 → 与原生字符零冲突，**不需要镜像**
 *
 * 槽表在 src/text/chs_slots.inc，由 gdb 实测的 glyph 集合 + 空闲区块生成。
 * 每个汉字 4 个连续 tile（+0 左上 / +1 左下 / +2 右上 / +3 右下）。
 * 容量：设置菜单 41 个汉字 × 4 = 164 tile，空闲区块合计 180 tile。
 * ⚠ 改翻译（增删汉字）后必须重新生成槽表，否则新汉字会回退到旧路径。
 * ------------------------------------------------------------------------*/

/* ---- 字形镜像（Glyph Mirror）--------------------------------------------
 * 背景：tm1 的原生字符走 ROM 预渲染查表，**零 VRAM 写入**（FontSub_Origin
 *   只写 tilemap 表项，值 = 字库 tile = startOffset + glyph*2）。
 *   中文要落 VRAM 就得躲开"本窗口实际引用的字形"，这就是 tile 稀缺的根源。
 *
 * 镜像 = 给被中文压住的字形做一个**替身**：
 *   1) 字库铺完后立刻把该字形（2 tile，64B）拷到空闲处 dst；
 *   2) 原生字符打印时，把 ROM 写好的表项值从 src 改成 dst。
 *   → 字库本身一字不动，中文不必再躲它。
 *
 * 为什么拷贝时机必须在 InitWindowTileData 里（而不是用到时再拷）：
 *   中文一写入就把 src 的内容覆盖了，**之后**再拷只会拷到中文碎片。
 *   而 InitWindowTileData 逐 glyph 调用、且整体跑在文本打印之前
 *   （gdb 实证：预渲染 日志行 698–4013，首个文本打印 4026），
 *   此刻字形刚渲染完、内容干净，是唯一的正确时机。
 *   → 这也让镜像**完全无状态**：不需要 RAM 映射表，更不需要失效逻辑。
 *
 * src/dst 都填**字形起点**（= startOffset + glyph*2，必为奇数），
 * 各占 2 格：src/src+1 → dst/dst+1。表项 lower 一律 = upper+1。
 * ------------------------------------------------------------------------*/
struct Tm1Mirror {
    uint16_t src;       /* 原字形 tile 起点（被中文覆盖的那个） */
    uint16_t dst;       /* 镜像 tile 起点（须不在中文足迹与引用字形内） */
};

/* ---- tm1 窗口布局配置 ---------------------------------------------------*/
struct Tm1WinCfg {
    const char     *name;           /* 仅用于调试/日志，运行时不影响落址 */
    uint32_t        tpl;            /* 窗口模板地址 = 唯一键 */
    uint8_t         mode;           /* TM1_MODE_PARTITION / TM1_MODE_GRID */

    /* 行基址 */
    const uint16_t *row_tab;        /* 菜单行基址表，下标 = 行号-1 */
    const uint8_t  *row_span_tab;   /* 每行**预留**的 tile 数（与 row_tab 等长）。
                                     * 必须显式给：末行常无候选列，只需标签那点容量；
                                     * 若一律按满跨度预留，会撞到后面的引用字形。 */
    uint8_t         row_tab_n;      /* 行数 */
    uint8_t         row_y0;         /* 行号推导：r = (curY - row_y0) >> row_shift */
    uint8_t         row_shift;
    uint16_t        title_base;     /* curY <= row_y0 时用它（标题/无候选列的行） */

    /* 列分区 */
    uint8_t         col_label_max;  /* curX < 此值 = 标签列，否则候选列 */
    uint8_t         lbl_off;        /* 标签子区起点（PARTITION） */
    uint8_t         lbl_span;       /* 标签子区容量（PARTITION） */
    const struct Tm1Slot *slots;    /* 候选槽表（PARTITION） */
    uint8_t         slot_n;
    uint8_t         cand_font;      /* 候选列字模：0 = 同标签(12px)，4 = FontChsSmall(8px) */

    /* GRID 用：tile = grid_base + (y - grid_y0)*stride + (x - grid_x0) */
    uint16_t        grid_base;
    uint8_t         grid_stride;
    uint8_t         grid_x0;
    uint8_t         grid_y0;

    /* GRID 用：**中文保护区矩形**（行/列下标，闭区间，相对 grid_x0/y0）。
     *
     * 为什么需要它：镜像表的冲突集若按"每个会话精确字数"算，就会依赖一份
     * 手抄的字数表——改一次翻译就失效一次，而且漏一条就漏镜像（表现为
     * Ｌ/Ｒ 之类非中文字符变乱码，2026-08-29 实测踩过）。
     * 矩形是**结构性上界**：只要中文不画到框外就永远成立，与文本无关。
     *
     * 判据：矩形内所有"已实测引用的字形"都必须有镜像条目。
     * 宁可把矩形取大一点（多镜像几个字形），也不要取小了漏掉。 */
    uint8_t         prot_row0, prot_row1;
    uint8_t         prot_col0, prot_col1;

    /* 字形镜像表（可为空：mirror_n == 0 表示无需镜像，运行时零开销）。
     * ⚠ 只有 GRID 这类"位置式"布局才需要——它没法躲开引用字形。
     *   PARTITION 若本就无冲突，保持空表即可。 */
    const struct Tm1Mirror *mirrors;
    uint8_t                 mirror_n;

    /* 该窗口**已实测被引用的字形 tile**（各占 2 格）。运行时不读；
     * 供离线自检脚本核对"中文区有没有踩到引用字形"。
     * ⚠ 集合可能不完整，改翻译后应重新采集。 */
    const uint16_t *glyph_avoid;
    uint8_t         glyph_avoid_n;

    /* MIX 模式：列分区规则表（按 cx_hi 升序，末条 cx_hi=0xFF 兜底）。
     * 非 MIX 模式可为 NULL / 0。 */
    const struct Tm1Zone *zones;
    uint8_t              zone_n;
};

/* ---- 窗口登记表（**数据在 text_scene.c，算法在 text_layout.c**）----------
 * 新增窗口：在 text_scene.c 底部定义配置并追加到 kTm1Windows[]，算法侧不用动。 */
extern const struct Tm1WinCfg *const kTm1Windows[];
extern const unsigned kTm1WindowN;

/* 按模板地址查表；未登记返回 NULL（调用方回退默认，禁止猜场景）。 */
const struct Tm1WinCfg *scene_tm1_lookup(uint32_t tpl);

/* 由配置求行基址：curY <= row_y0 → title_base；否则 row_tab[r-1]，r clamp 到 [1,n]。 */
uint16_t scene_tm1_row_base(const struct Tm1WinCfg *cfg, uint8_t cur_y);

/* 由配置求行内子区起点，容量写入 *span。GRID 模式返回 span=0（不做复位）。 */
uint16_t scene_tm1_sub_off(const struct Tm1WinCfg *cfg, uint8_t cur_x, uint16_t *span);

/* GRID 模式求 tile。map_tx = 行内已推进的 tile 列（base_tx + (px>>3)）。
 * 返回值未加 lower 偏移——lower 由调用方按 row_delta*grid_stride 另加。 */
uint16_t scene_tm1_grid_num(const struct Tm1WinCfg *cfg, uint8_t cur_x,
                            uint8_t cur_y, uint8_t cur_ty, unsigned map_tx);

/* 字形镜像查表（宽松）：tile 落在 [src, src+2) 即命中，返回对应镜像 tile
 * （src→dst，src+1→dst+1）。给**运行时表项改写**用——原生字符的 upper/lower
 * 表项值分别是 src / src+1，两者都要改。无镜像返回 0。 */
uint16_t scene_tm1_mirror_of(const struct Tm1WinCfg *cfg, uint16_t tile);

/* 字形镜像查表（严格）：仅当 tile **精确等于** src 才返回 dst。
 * 给**预渲染期拷贝**用——InitWindowTileData 传来的 tile 恒为字形起点
 * （startOffset + glyph*2），精确匹配可以杜绝错位拷贝。无镜像返回 0。 */
uint16_t scene_tm1_mirror_src(const struct Tm1WinCfg *cfg, uint16_t tile);

/* ---- 混合模式：分区选择（实现见 src/text/text_layout.c）------------------
 * 按当前 curX 命中 zones 表，填好 *out：
 *   PTR 区 → ptr_base = 该汉字的固定槽（查 kOptChsSlots）
 *   DYN 区 → off/span = 该区的行内偏移与容量，ptr_base = 0
 * 未登记窗口 / 非 MIX 模式 / 未登记汉字 → out->strategy 按旧模式回退，
 * 绝不让调用方拿到半初始化的值。 */
void tm1_zone_select(TextPrinter *win, uint32_t glyph, struct Tm1ZoneSel *out);

#endif /* TEXT_SCENE_H */
