/* =====================================================================================
 * PrintNextChar_hook.c — 渲染落点（翻译通路消费端）
 *
 * 统一模型（2026-09-04）：
 *   1) 非 FA..FF → TranslateHandleChar / DrawGlyph（翻译通路）
 *   2) resolve(tm, fn, 场景表) → 档位：tm2/fn4/req8 → 小库；场景表 → Middle/小库；
 *      否则 → 大库（11×11 步进 12）
 *   3) 取字 → g128 → chs_emit：按 tm 落点
 *        tm2     写 win[0x20] 缓冲，列步进 +0x40（官方血条再 CpuSet→OBJ）
 *        tm0/tm1 块基准位置定号：tile = TILE_BASE + block_base(CUR_X,CUR_Y)
 *                + TILE_OFFSET，并在 chs_emit 里推进 TILE_OFFSET
 *        tm3     官方网格：tile 按屏幕格算，不推 TILE_OFFSET
 *   🔴 tm 仍是 1（P31「36 条模板 tm1→tm0」已废）：tm0 会启用
 *   FontFuncTable[0] = 0x08003568，而它是「官方自己画」的处理器
 *   （bl 0x08003520 → dst = tpl->tileData + (win[0x16]+win[0x18])*32
 *    **正好是我们的画布**，画完还 win[0x18] += 2）。
 *   tm1 的 FontFunc[1] = 0x0800360C 经 FontSubTable 只调 UpdateTilemap，
 *   不碰任何 VRAM、不推 win[0x18] ⇒ 与我们自写渲染链零冲突。
 *   官方「字形图集预取」由 P32（patches/prefetch_off.asm 短接 0x080029E0）
 *   关掉，不再需要动模板数据。
 *   TILE_BASE 是**引擎自己给的**（`InitTextPrinter` 第 3 参数 → win[0x16]），
 *   v22 的 InitTextPrinter 钩子不再改写它（v21 的窗口私有画布 chs_canvas
 *   门控恒不成立、从未生效，已退役）。号完全由 chs_claim_tile 纯函数算出。
 * ===================================================================================== */
#include "text.h"
#include "blend_glyph.h"
#include "tile_alloc.h"
#include "scene_cfg.h"
#include "diag_log.h"

/* ---- 我方可变状态一律放固定 EWRAM 地址 ------------------------------------
 * 🔴 铁律：`link/game.ld` 只有 ROM 一个 MEMORY 段 ⇒ 任何 `static` 可变量都被
 * 放进 **ROM**（out/game.map: `.bss 0x08802180` = 0x08800000 段的尾部）。
 * 对 ROM 写入被**静默丢弃**，读回恒 0 —— 看起来「代码跑通」，实际状态一步没动。
 * （2026-09-21 实测：字符去重表全落 ROM ⇒ 全屏所有字都拿到 slot 0。）
 * 故本模块状态走固定地址，与 ADDR_OPT_* / ADDR_TRACE 同法。
 * 选址 0x0203E000：紧跟 8 KB trace 块（0x0203C000..0x0203DFFF）之后，
 * 已用 33 份不同页面快照确认该处恒为 0；游戏数据区自 0x0203FFD2 起，不得越过。 */
#define ADDR_CHS_SLAB    0x0203E000u
#define CHS_SLAB_MAGIC   0x4232544Cu   /* 'LT2B' */
#define CHS_SLAB_TICK    0x00000004u
/* 键的 hi 半「右格槽」标记位 —— 见 print_glyph_px 里 v34 一段。 */
#define CHS_KEY_R_MARK   0x80000000u
/* 两张槽表：域 0 = 本块顶部（cb1 块窗口用，40 槽）；域 1 = 下一块（cb2 块窗口用，92 槽）。
 * 两域各自独立去重 —— 同一字符在不同域占的是**不同的字节地址**，键必须分开。
 *
 * 🔴 键是 **64 位**（lo, hi）—— 见下面 v26 一节：
 *    本格 = 上一字的右半（px[0,phase)）+ 本字的左半（px[phase,8)）⇒ 内容同时由
 *    **本字身份**与**上一字身份**决定，缺一不可。 */
/* v35：**三张**槽表 —— 按「窗口所在 BG 层的 charBase」分人口。
 * 槽步进 2 ⇒ 槽数 = 54 / 199 / 64 = 317（段表由 `.tmp/genpool2.py` 生成）。
 * 表体一律放在 TRCH(0x8A8) **之后**，免得动到 g_trace_ch 的既有地址。
 *
 *   人口 0（cb1 窗口：队名 / 左面板）KEYS 0x8B0 + 54*8=0x1B0 → 0xA60
 *                                    STAMPS          0xA60 + 54*4=0xD8  → 0xB38
 *   人口 1（cb2 窗口：最常见）       KEYS 0xB40 +199*8=0x638 → 0x1178
 *                                    STAMPS          0x1180+199*4=0x31C → 0x149C
 *   人口 2（cb0 窗口：概况页顶栏）   KEYS 0x14A0 + 64*8=0x200 → 0x16A0
 *                                    STAMPS          0x16A0 + 64*4=0x100 → 0x17A0
 *   TRCH 0x8A8（不动）              表尾 0x17A0 ＜ 游戏数据区 0x1FD2 ✓
 *
 * 🔴 改槽数后**必须**同步这六个偏移（跑 `.tmp/genpool2.py` 会直接打印），
 *    且下面六条 `#if` 会当场报错 —— 2026-09-21 曾按「表长整除」手算，
 *    结果三处各压 4~8 B（不报错但会串字）。 */
#define CHS_SLAB_KEYS_MAX 224u
#define CHS_SLAB_KEYS0    0x000008B0u
#define CHS_SLAB_STAMPS0  0x00000A60u
#define CHS_SLAB_KEYS1    0x00000B40u
#define CHS_SLAB_STAMPS1  0x00001180u
#define CHS_SLAB_KEYS2    0x000014A0u
#define CHS_SLAB_STAMPS2  0x000016A0u
/* ⚠ 表体不重叠的静态断言放在**池子槽数定义之后**（下面）—— 这里是预处理器
 * 首次遇到的顺序，CHS_*_SLOT_N 还没定义，写在这儿会被当成 0 而恒真不报错。 */
#define CHS_SLAB_KEYS     CHS_SLAB_KEYS1      /* 兼容旧引用 */
#define CHS_SLAB_STAMPS   CHS_SLAB_STAMPS1
#define CHS_SLAB_TRCH    0x000008A8u

#define CHS_SLAB_U32(off) (*(volatile uint32_t *)(uintptr_t)(ADDR_CHS_SLAB + (off)))

#if CHS_TRACE
/* 诊断用：当前正在落砖的字符（由 chs_print / DrawGlyph 写入）。
 * 同样必须放 RAM —— 放 static 会被丢进 ROM，读回恒 0。 */
#define g_trace_ch (CHS_SLAB_U32(CHS_SLAB_TRCH))
#endif

/* ---- resolve：tm + fn + 场景表 + 请求步进 → 步进/墨宽/字形源 ----
 * 档位解析优先级（高 → 低）：
 *   ① tm2（血条缓冲直绘）/ fn4 / 请求 8px  → 1bpp 小库 9×9，步进 10、墨宽 9；
 *   ② 场景字号表（scene_cfg.c，键 tpl+win，curX 分区）：
 *        V6_FONT_PX_MIDDLE → 1bpp Middle 9×11，步进 10、墨宽 9（窄身全高，如领航员）
 *        V6_FONT_PX_SMALL  → 1bpp 小库 9×9，步进 10、墨宽 9
 *   ③ 默认 → 1bpp 大库 11×11，步进 12、墨宽 11。
 * 场景表**不覆盖** ①（血条/强制小字体是硬约束）。
 * 历史：2026-09-08「两档制 2.0」曾把场景表整体退役；2026-09-11 重建为档位选择器。 */
static void resolve_draw(TextPrinter *win, uint8_t req_px, uint8_t *tm_out,
                         uint8_t *fn_out, uint8_t *adv_out, uint8_t *ink_out,
                         uint8_t *lib_out)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
    uint8_t fn = win_u8(win, WIN_FONTNUM_REAL);
    uint8_t scene_px;

    if (fn > 6u)
        fn = 3u;
    *tm_out = tm;

    *fn_out = (tm == 2u) ? 4u : fn;
    if (tm == 2u || fn == 4u || req_px == 8u) {
        *adv_out = 10u;
        *ink_out = 9u;
        *lib_out = CHS_FONT_LIB_1BPP_SMALL;
        return;
    }

    /* 场景字号表：tpl 取 win[0x00] 模板指针，win 取打印器自身地址，
     * 分区键取 WIN_CURSOR_X（整个字符串的起始列，按串恒定）。 */
    scene_px = v6_scene_font(win_u32(win, WIN_TEMPLATE),
                             (uint32_t)(uintptr_t)win,
                             win_u8(win, WIN_CURSOR_X));

    if (scene_px == V6_FONT_PX_MIDDLE) {
        *adv_out = 10u;
        *ink_out = 9u;
        *lib_out = CHS_FONT_LIB_MIDDLE;
        return;
    }
    if (scene_px == V6_FONT_PX_SMALL) {
        *adv_out = 10u;
        *ink_out = 9u;
        *lib_out = CHS_FONT_LIB_1BPP_SMALL;
        return;
    }

    /* v34：步进回到 **12px**（11px 墨 + 1px 空隙）。
     *
     * v30 曾改成 16px 来把「键 = 字符×前字」压成「纯字符」，代价是版式宽 33%：
     * 实测 START 菜单的 `宝可梦` / `领航员`（3 字 = 48px）**撑破只有 40px 的
     * 窗口内宽，把右边框压掉**。窗口是按日文 8px 全角排版的，12px 才是它的
     * 正常密度。
     *
     * v34 靠「1 格 1 槽」把容量问题解掉：12px 下一个字跨 2 格 ⇒ 2 个 2-tile 槽
     * （而 16px 是 1 个 4-tile 槽），**总砖数不变**，但同量空档能出两倍槽数
     * （实测 300 槽 = 604 砖，覆盖 470~630 砖的空档并集）。
     * 代价：phase 在 0/4 间交替 ⇒ 共享的那一格内容由 (前字, 本字) 共同决定
     * ⇒ 键仍是 (本字, 前字)（v26 的搬运机制原样保留）。 */
    *adv_out = 12u;
    *ink_out = 11u;
    *lib_out = CHS_FONT_LIB_1BPP_BIG;
}

/* 「下半 tile」偏移：本槽布局是 2×2 相邻四连号 ⇒ 恒 +1。
 * （tm3 旧的 +30 网格已废，见下方 v24 说明。） */
static uint16_t chs_lower_delta(uint8_t tm)
{
    (void)tm;
    return 1u;
}

/* v21 起「格子 → tile 映射」整体删除。
 * 位置定号下 `tile = TILE_BASE + TILE_OFFSET` 是纯函数，不需要读回 tilemap
 * 猜「这格是不是我们写的」。旧机制（ours 账本 + 竖直对自洽闸门 +
 * v8_official_end 水位）的全部存在理由已消失，见 docs/15-0b_*.md。
 * `chs_lower_delta` 仍在（chs_fill_bg 用「下半 tile 偏移」）。 */


/* ============================ v24：字符键字形图集 ============================
 *
 * 【为什么位置键必须废】引擎的号是**字符键**。`InitWindowTileData`(0x08002A50)
 * 三个分支逐指令实测（分派表 @0x08002A74，按 fontNum 索引）：
 *   font1/4 → 0x08002A8C: dst = TILE_DATA + base*32 + chr*64   （2 tile/字）
 *   font2/3 → 0x08002AAC: dst = TILE_DATA + (base+chr)*32      （1 tile/字）
 *   font5/6 → 0x08002ACC: dst = TILE_DATA + (base+chr)*32      （1 tile/字）
 * ⇒ 号 = base + chr*k，**同一字符全屏共用一槽**。
 * 预取 worker 0x080029E0 每帧 materialize 16 个 chr（游标 0x0300032E 每帧 +16，
 * 直到 0x1000 = chr 0..255），且 0x08002950 为 2-tile 字体返回 tiles needed = 512
 * ⇒ **窗口 TILE_DATA 的首块 [0,512) 整体是引擎自己的日文字形图集**。
 *
 * 我们 v8~v23 用的是位置键 `(CUR_Y>>1)*64 + CUR_X*2 + TILE_OFFSET`，落在同一块内
 * ⇒ 冷启动实测（scripts/chs_bg_ab.py / chs_tile_share.py）：
 *   · 队伍页 BG0 `号 34/38` 被我们覆盖 —— 它们是引擎自己写的 `Lv` 的槽
 *     （BG0 charBase=1 → cb1，原盘 map 直接引用 2*chr/2*chr+1）⇒「Lv 只剩半个记号」；
 *   · 背包页 `号 93` 被 (r6,c16)/(r10,c16)/(r15,c4) 三格共用 ⇒ 光标一动，远处格子
 *     跟着变 = 「背包固定位置被替换」；
 *   · 队伍页消息框 BG2 r17/r18 c1..c15 原盘是 `1+chr*2` 的逐字内容号，我们算出的
 *     `517,519,521,523,525`（= 1 + 512 + CUR_X*2 + TILE_OFFSET）**正好压在
 *     引擎消息框 9-slice 的 516..520 上** ⇒ 框体破损 =「请选择那里撞 UI」。
 *
 * 【v24 定号】`tile = base + slot * 4`，slot 由**字符键**去重。
 *   · 槽布局 [左上, 左下, 右上, 右下] = +0/+1/+2/+3（extract_cols 的四列来源），
 *     `chs_lower_delta` 因此恒为 1，t1 恒为 t0+2（tm3 的 +30 网格一并废除）。
 *   · 同一字符全屏共用一槽 ⇒ 结构上不可能「写一处串一片」。
 *   · 槽数上界来自 VRAM 布局：0x0600F000..0x0600FFFF 是**tilemap 区**
 *     （本页 BG0 screenBase=30 → 0x0600F000，窗口 scratch tilemap 0x0600F800），
 *     故 charBase=2 的窗口 index 必须 < 896。
 *   · 淘汰用 LRU（stamp 单调递增，命中刷新）——保证「屏幕上现存的字」不会被新字
 *     挤掉；只有超过槽数个**不同**字符同时上屏才会动到最久未用者。
 *   ⚠ base 的取值不是自由参数，v24 的「+528 一律」在 cb1 窗口上是错的，
 *     必须换成 v25 的双域规则（下面紧接的一节）。
 * ========================================================================== */

/* ==================== v25：图集落点必须避开「别人的字体块」 ====================
 *
 * v24 用的 `tile = TILE_BASE + 528 + slot*4`（528*32 = 0x4200 > 0x4000）语义是
 * 「落在**下一个** charBlock」。这条对 cb2 窗口成立，对 cb1 窗口是致命的：
 *
 *   窗口 tpl          tileData      +528 落在        +528 那块是谁的
 *   ----------------- ------------- --------------- ----------------------------
 *   0x081BB43C（cb1） 0x06004000    0x06008200      **cb2** = 模板 0x081BB46C 的字库块 ✗
 *   0x081BB46C（cb2） 0x06008000    0x0600C220      cb3（无模板占用）✓
 *
 * 🔴 2026-09-21 冷启动实测（`.tmp/vdiff.py`，判据 = 与原盘 VRAM dump **逐字节**比）：
 *   t_party 的 cb1 窗口 t0 = 697..762 → 字节 0x06009720..（cb2 块）；
 *   而 o_party vs t_party 的 **cb2 块差异 = 0 个 tile**（逐字节完全相同）
 *   ⇒ 我们写进去的砖被**整块抹掉**，屏上显示的是 cb2 字库在该号处的 8×8 字形
 *     —— 实机症状就是「队名变乱码日文、颜色发黑、黑底丢失」。
 *   对照：同一份 dump 的 cb3 差异里正好是我方 cb2 窗口的 12 个号
 *   ⇒ cb3 是真安全区（「请选择」一直渲染正确就是这个原因）。
 *   再对照：两份**原盘** dump（04:19 / 10:01，不同会话）四块全部逐字节相同
 *   ⇒ 这个判据可靠，不是采样噪声。
 *
 * 结构性结论：**引擎会整块重写任何「模板 tileData」所在的 16 KB 块**
 * （cb1 块 = 引擎自画字形缓存、cb2 块 = 静态字库重拷），故我方图集只能：
 *   ① 「下一块」不是模板 tileData ⇒ 放下一块 `[528, 1024)`（cb2 窗口走这条，92 槽）；
 *   ② 否则放**本块顶部** `[352, 512)`（cb1 窗口走这条，40 槽）——
 *      让开本块低号段的引擎自画字形与屏幕美术（实测 BG0 引用号全在 <346）。
 * 两域各自独立 LRU 去重（同一字符在不同域是不同字节地址，键必须分开）。
 * ============================================================================ */
#define CHS_FONT_BLK_LO 0x06004000u   /* 模板 0x081BB43C 的 tileData */
#define CHS_FONT_BLK_HI 0x06008000u   /* 模板 0x081BB46C 的 tileData */
#define CHS_BLK_MASK    0xFFFFC000u

#define CHS_SLOT_STRIDE 2u

/* ================== v33：池子按 **BG 层 charBase** 分「人口」 =================
 *
 * 【为什么必须分】map 项 n 的硬件地址 = 层基址(charBase) + n*32，
 *   而**层基址随屏面变**：概况页/技能页 BG0CNT=0x1E08（charBase=2），
 *   队伍页/详情页 BG0CNT=0x1E06（charBase=1）。实测窗口表里两个打印器：
 *     td=0x06008000 58 次（队伍行 HP/请选择…）   td=0x06004000 22 次（队名）
 *   同一个绝对写砖地址，在两种层基址下需要**两个不同的 map 号**；而 cb1 层
 *   够得着的地址只有 `[0x06004000,0x0600C000)`，够不到 cb2 的高半
 *   ⇒ **一个绝对池子不可能同时服务两种 charBase**（v31「单池 + 固定 CHS_CHAR_BLK」
 *   在 cb1 窗口上必然错位：号是 cb2 口径、硬件按 cb1 解释 ⇒ 队名整片乱码）。
 *
 * 【锚点】窗口模板的 `tileData` **就是**本层 char 块基址（引擎自己往那儿画
 *   字形缓存），所以：写砖基址 = `tpl->tileData`，map 号 = 段表给的**块内号**，
 *   两者同一口径，不需要任何偏置换算。
 *
 * 【空档来源】`.tmp/freemap.py`：把**原盘 7 个屏面 dump** 里所有 BG map 引用的
 *   砖地址 + 地图表自身字节区间取并集，再算连续空档。这是 ROM 的结构事实
 *   （不是 savestate、不是单页快照），并集保证不踩静态美术、地图表，以及
 *   **未翻译日文**的引擎自画字形缓存（背包页顶部横幅乱码 = 踩了 cb2 号 479）。
 *
 *   实测空档（绝对地址 → 块内号）：
 *     [0x06007000,0x06007800)  64 砖 = cb1 号 [384,448)   16 槽  ← 人口 0
 *     [0x0600B640,0x0600BBE0)  45 砖 = cb2 号 [434,479)   11 槽 ┐
 *     [0x0600C1C0,0x0600CB60)  77 砖 = cb2 号 [526,603)   18 槽 ├ 人口 1（68 槽）
 *     [0x0600CC80,0x0600E000) 156 砖 = cb2 号 [612,768)   39 槽 ┘
 *     [0x06001800,0x06002000)  64 砖 = cb0 号 [192,256)   16 槽 ┐ 人口 2（32 槽）
 *     [0x06002800,0x06003000)  64 砖 = cb0 号 [320,384)   16 槽 ┘
 *
 * ============================================================================
 * v36：人口 1 整体搬到「本层号 ≥ 514」—— 引擎**每次装载文本块都会重写** [1,513)
 * ----------------------------------------------------------------------------
 * 【新判据（代码推导，非采样）】`.tmp` 里的采样求补集有个致命盲区：只数「被 map
 *   **引用**」的砖，不数「被**写入**」的砖。而引擎的字形缓存是**超前预加载**的 ——
 *   写进去那一刻 map 还没引用它 ⇒ 被判成空档。
 *   现在把写入点静态解出来了（`scripts/scan_engine_tile_cache.py`，闸门全 PASS）：
 *     · 入口全 ROM 仅 2 处：`0x08002950(win, tileBase)` 配置 + `0x080029E0` 分帧推进。
 *     · 写入式：font 0/3 `tileData + tileBase*32 + index*64`，
 *               font 1/2/4/5 `tileData + (tileBase + index)*32`，`index ∈ [0,256)`。
 *     · 实测 `tileBase ≡ 1`、全部窗口 `tpl[+8] == 3` ⇒ 走 512 号那条。
 *   ⇒ **引擎必然写满 `[tileData+0x20, tileData+0x4020)`（513 号 / 16 KB）** ——
 *     也就是本层块内号 `[1,513)`。这不是「某个屏面」的性质，是**每次装载文本块
 *     都会发生**的动作，任何采样都躲不开。
 *
 * 【所以】常驻的中文砖**只能**放本层号 `[513,1024)`，物理上 = 下一个 charBlock。
 *   对 cb2 窗口（最常见）就是 cb3。逐页 BGxCNT 实测（14 页全查，`.tmp/bgcfg.py`）：
 *     · cb3 **没有任何 BG 层把它当 char block 用**（各层 charBase ∈ {0,1,2}）；
 *     · 但 cb3 里住着 **screen block 24..31**（0x0600C000..0x06010000）——
 *       实测 sb ∈ {0,4,6,7,8,10,12,15,22,28,29,30,31}，其中 28/29/30/31 落在
 *       cb3 的 0x0600E000..0x06010000。
 *   ⇒ 人口 1 的**唯一持久安全区** = `0x0600C040..0x0600E000`
 *     = cb2 号 `[514,768)` = **254 砖 = 127 槽**（单段）。
 *
 * 【顺带作废的两个旧结论（都记在这里免得被重新发明）】
 *   ① 「抬 tileBase 把字模搬去 cb3」**已判死**：cb3 被 screen 28..31 占着，
 *      抬 TB=512 ⇒ 字模写满 cb3 ⇒ 直接盖掉 BG0 的 tilemap（sb=30 → 0x0600F000）
 *      ⇒ 开机崩。而且 cb0/cb1/cb2 里**都不存在 16 KB 连续空闲段**，
 *      「给引擎搬个块」这条路整条走不通。
 *   ② 人口 0/2 **不动**：需求峰值实测仅 17/未知 槽（`.tmp/slabdemand.py`），
 *      且它们的 ≥513 区落在 cb2/cb1 里 —— 那是**别的窗口**的写入区，反而更危险。
 *
 * 🔴 残留风险（如实记录）：sb 24..27（0x0600C000..0x0600E000）在已采的 14 页里
 *    没出现过，但战斗页 / 领航员 / PC 箱子尚未采集。若某页用 sb∈[24,27]，
 *    本段会与它相撞。判据：`scripts/scan_screen_bases.py`（待采全后再跑）。
 * ============================================================================ */
#define CHS_OWN_BASE    384u
#define CHS_OWN_SLOT_N  54u           /* 32 + 22 */
#define CHS_FAR_BASE    514u
#define CHS_FAR_SLOT_N  127u          /* v36：单段 [514,768) = 254 砖 */
#define CHS_CB0_BASE    192u
#define CHS_CB0_SLOT_N  64u           /* 32 + 32 */

/* 段表由 `.tmp/genpool2.py` 直接生成（读 freemap 的空档 + 人口归属），别手抄号。
 * 归属原则：进得去的空档才给该人口 —— cb1 层只能寻址 [0x06004000,0x0600C000)，
 * 所以 cb2 号 526 以上的空档（地址 >= 0x0600C1C0）对 cb1 窗口**不存在**。
 * v34：槽步进 4→2（1 格 = 1 槽 = 上/下两砖），12px 步进下一个字占 2 格
 *       = 左右两个**独立**槽，故槽数翻倍、总砖数不变。
 * v35：人口 0 由 69 → 54 槽（实测需求峰值仅 17 槽，长期闲置）；腾出的 cb2 高段
 *       连同「cb2 抵达范围内所有 >= 4 砖的碎片空档」全划给人口 1 ⇒ 167 → 199 槽。
 *       动因：`.tmp/slabdemand.py` 实测 t_info / t_moves 恰好把 167 槽用满，
 *       触顶后 LRU 淘汰把屏上已有的字挤掉（`trdump.py` 抓到 7 例同砖异字）。
 * 🔴 人口 0 与人口 1 的可达范围**在 cb2 低半重叠**（p0 号 512..1023 与
 *    p1 号 0..511 指向同一批物理地址）⇒ 归属必须显式互斥，
 *    `.tmp/genpool2.py` 末尾会打印「物理重叠: p0&p1=0」做校验。 */
static const uint16_t chs_p0_seg_b[2]  = { 384u, 946u };
static const uint8_t  chs_p0_seg_n[2]  = { 32u,  22u  };
static const uint16_t chs_p1_seg_b[1]  = { 514u };
static const uint8_t  chs_p1_seg_n[1]  = { 127u };
static const uint16_t chs_p2_seg_b[2]  = { 192u, 320u };
static const uint8_t  chs_p2_seg_n[2]  = { 32u,  32u  };

typedef struct {
    const uint16_t *seg_b;
    const uint8_t  *seg_n;
    unsigned seg_c;
    unsigned slot_n;
} ChsPool;

static const ChsPool chs_pools[3] = {
    { chs_p0_seg_b, chs_p0_seg_n,  2u, CHS_OWN_SLOT_N },
    { chs_p1_seg_b, chs_p1_seg_n,  1u, CHS_FAR_SLOT_N },
    { chs_p2_seg_b, chs_p2_seg_n,  2u, CHS_CB0_SLOT_N },
};

#if CHS_FAR_SLOT_N > CHS_SLAB_KEYS_MAX
#error "池子槽数超过槽表容量"
#endif

/* 🔴 段表槽数之和必须**恰好**等于槽数宏：槽表按宏开长，落砖按段表走。
 *    两者不等时 `chs_slot_tile` 会对超界槽返回 0（= 写到 tile 0），
 *    症状是「屏幕上莫名多出一个字 / 别处被擦」。这两组数字是**故意重复**的
 *    （左边来自段表初始值、右边来自槽数宏），重复才能互相校验。 */
_Static_assert(( 32u + 22u ) == CHS_OWN_SLOT_N, "p0 seg sum != CHS_OWN_SLOT_N");
_Static_assert(( 127u ) == CHS_FAR_SLOT_N, "p1 seg sum != CHS_FAR_SLOT_N");
_Static_assert(( 32u + 32u ) == CHS_CB0_SLOT_N, "p2 seg sum != CHS_CB0_SLOT_N");
_Static_assert(sizeof(chs_p0_seg_b) / sizeof(chs_p0_seg_b[0]) == 2u, "p0 seg count");
_Static_assert(sizeof(chs_p1_seg_b) / sizeof(chs_p1_seg_b[0]) == 1u, "p1 seg count");
_Static_assert(sizeof(chs_p2_seg_b) / sizeof(chs_p2_seg_b[0]) == 2u, "p2 seg count");

/* 槽表布局静态断言（必须放在上面三个槽数宏定义之后，否则预处理器把未定义的
 * 标识符当 0，三条检查全部静默通过）。 */
#if CHS_SLAB_KEYS0 + CHS_OWN_SLOT_N * 8u > CHS_SLAB_STAMPS0
#error "槽表重叠：KEYS0 / STAMPS0"
#endif
#if CHS_SLAB_STAMPS0 + CHS_OWN_SLOT_N * 4u > CHS_SLAB_KEYS1
#error "槽表重叠：STAMPS0 / KEYS1"
#endif
#if CHS_SLAB_KEYS1 + CHS_FAR_SLOT_N * 8u > CHS_SLAB_STAMPS1
#error "槽表重叠：KEYS1 / STAMPS1"
#endif
#if CHS_SLAB_STAMPS1 + CHS_FAR_SLOT_N * 4u > CHS_SLAB_KEYS2
#error "槽表重叠：STAMPS1 / KEYS2"
#endif
#if CHS_SLAB_KEYS2 + CHS_CB0_SLOT_N * 8u > CHS_SLAB_STAMPS2
#error "槽表重叠：KEYS2 / STAMPS2"
#endif
#if CHS_SLAB_STAMPS2 + CHS_CB0_SLOT_N * 4u > 0x1FD2u
#error "槽表越过游戏数据区 0x0203FFD2"
#endif

/* 槽号 → 块内 tile 号。 */
static uint16_t chs_slot_tile(unsigned dom, unsigned slot)
{
    const ChsPool *p = &chs_pools[dom < 3u ? dom : 1u];
    unsigned i, k = slot;

    for (i = 0u; i < p->seg_c; i++) {
        if (k < (unsigned)p->seg_n[i])
            return (uint16_t)(p->seg_b[i] + k * CHS_SLOT_STRIDE);
        k -= (unsigned)p->seg_n[i];
    }
    return 0u;
}

/* 块内 tile 号 → 槽号。只接受本域的「R 砖」（+2 对齐，见 v26）。 */
static unsigned chs_tile_slot(unsigned dom, uint16_t t)
{
    const ChsPool *p = &chs_pools[dom < 3u ? dom : 1u];
    unsigned i, base = 0u, d;

    for (i = 0u; i < p->seg_c; i++) {
        if ((uint32_t)t >= p->seg_b[i]
            && (uint32_t)t < (uint32_t)p->seg_b[i]
                            + (uint32_t)p->seg_n[i] * CHS_SLOT_STRIDE) {
            d = (unsigned)(t - p->seg_b[i]);
            /* 槽基址落在偶数偏移（上半砖），下半砖在 +1 ⇒ 奇数一律不是槽头 */
            return ((d & 1u) == 0u) ? (base + d / CHS_SLOT_STRIDE) : 0xFFFFu;
        }
        base += (unsigned)p->seg_n[i];
    }
    return 0xFFFFu;
}

static unsigned chs_pool_n(unsigned dom)
{
    return chs_pools[dom < 3u ? dom : 1u].slot_n;
}

static uint32_t chs_keys_off(unsigned dom)
{
    return dom == 0u ? CHS_SLAB_KEYS0
         : (dom == 2u ? CHS_SLAB_KEYS2 : CHS_SLAB_KEYS1);
}

static uint32_t chs_stamps_off(unsigned dom)
{
    return dom == 0u ? CHS_SLAB_STAMPS0
         : (dom == 2u ? CHS_SLAB_STAMPS2 : CHS_SLAB_STAMPS1);
}
/* 【v31 的旧结论已被 v33 取代，保留结论记录：两个打印器窗口的 map 字段都是
 *   0x0600F000 / 0x0600F800 —— 但那是**概况页**的屏面；队伍页实测 BG0
 *   charBase=1。所以「两窗口同层同号空间」只在部分屏面成立，不能当通则。】 */

/* ==================== v26：相邻两字「共享尾列」必须显式搬运 ====================
 *
 * 【症状】v24/v25 把「号」按字符去重后，队伍页队名渲染成「每字只剩左半、右半丢失
 * 并错位」。判据（冷启动 t_party，`mapdump.py` + `bgview_*_bg0_3x.png` 10× 放大）：
 *
 *   屏上 BG0 r07/r08 的 c16..c20 = 388 392 396 400 | 402（四个槽的 +0，加末字 +2）
 *   ⇒ **每个字只推进 1 格**，而一个字要占 2 格。
 *
 * 【机理】`advance` = 10/12 px，相位 `px&7` 在 0/2/4/6（或 0/4）间交替，于是：
 *   字 N   (phase=p) 把「左半 col[0,w0)」写在 **格 c 的 px[p,8)**，
 *                     把「右半 col[w0,ink)」写在 **格 c+1 的 px[0,w1)**。
 *   字 N+1 (phase=q) 的光标正好落在 **格 c+1**，它把「左半」写在 **格 c+1 的 px[q,8)**。
 *   ⇒ 格 c+1 的 8 个像素里，**px[0,q) 属于字 N、px[q,8) 属于字 N+1**。
 *
 * 旧的位置定号（v22 方案 H / 更早）天然处理了这件事：格 c+1 的号**只由格坐标算**，
 * 两个字算出来是**同一个号 ⇒ 同一个 tile ⇒ `blend_glyph_4bpp` 的掩码自动把两段拼一起**。
 * v24 换成字符键后，字 N 的「+2」与字 N+1 的「+0」是两个不同的号，
 * 而后写者覆盖 map 表项 ⇒ **字 N 的右半再也无人引用**。
 *
 * 这不是相位没推进（实测相位确在 0/2/4/6 走），而是**键与「共享格」这个物理事实不匹配**。
 *
 * 【为什么不能靠「把步进改成 16px」绕开】
 * 16px 步进 = 每字独占 2 格，确实能消除共享，但版式宽度立刻涨 33%~60%；
 * `docs/20260921_定号重构_三方案离线判据与选型.md` §四 已判死这条路
 * （「按字形索引定号」与「12px 紧凑步进」结构互斥，取前者要 800 号 + 16px）。
 * 而位置定号又放不进私有子域（满屏格数 ~638 > 可用 368 号）。
 * ⇒ 只能保留字符键，**把「上一字的右半」显式搬进本槽**。
 *
 * 【做法（零新状态，全靠屏幕现存 map 项指路）】
 *   本槽内容 = 上一字右半（px[0,phase)）+ 本字左半（px[phase,8)）。
 *   上一字的右半此刻正躺在**本格现存 map 项所指的那块砖**里（= 上一字的 +2/+3），
 *   直接照抄 px[0,phase) 过来，再让原来的 blend 写 px[phase,8)。
 *   ⇒ 上一字的身份**就是本槽内容的一部分** ⇒ 键必须是
 *      `lo` = 本字身份(码/字号/墨宽/相位)，`hi` = 上一字的 `lo`。
 *   ⇒ 同一字符跟在**不同前字**后面时是两个不同的槽（内容本来就不同），必须分开；
 *      跟在**相同前字**后面时内容逐字节相同 ⇒ 复用同一个槽，去重仍然成立。
 *
 * 搬运源的合法性校验（**不是**避让带/扫描，只是「这一格现在指向的号是不是我们的 +2」）：
 *   号 ∈ 本域区间 且 `(号 - 域基) % 4 == 2`。不合法（首字 / 引擎残留）⇒ px[0,phase)
 *   一律写成背景色 `colors[0]`，绝不留残影。
 * ============================================================================ */

/* ================= v27：域 1 落点必须抬到「下一块的顶部」 ====================
 *
 * 【症状】2026-09-21 用户截图：标题画面的「继续游戏 / 新游戏 / 设置」整页框体
 *   被咬掉 —— 三个选项的红色九宫格框**整条消失**，面板左竖条变黑，中部花边残缺。
 *
 * 【判据（原盘 A/B，`.tmp/bgref.py`）】原盘没有中文 ⇒ 窗口文字的字形住在低号
 *   段，所以 **map 引用到的 >= 512 的号 = 框体/UI 美术**（都住在「下一个 charBlock」）。
 *   四个页面实测（原盘 dumps：`.tmp/drive_o_{title,start,party,bag}_vram.bin`）：
 *
 *     页面              BG0 charBase   下一块内 UI 图形占用的**偏移**
 *     ----------------  ------------  ----------------------------------
 *     队伍页(BG2 cb2)        2        0 .. 8
 *     START 菜单            2        25 .. 27  +  91 .. 99
 *     标题菜单              2        91 .. 99
 *     背包页                2        无
 *
 *   而旧规则 `base = TILE_BASE + 528` ⇒ 下一块偏移 **17 .. 384**
 *   ⇒ 把 25..27 与 91..99 全压住。框体那 9 块砖的内容在两个页面上**逐字节相同**
 *   （`1321201171557155 / 1111212055555572 / …`），落点却不同（偏移 0 vs 偏移 91）
 *   ⇒ 引擎的 UI 图形落点是**运行时分配**的，写死一个低位固定偏移永远不可能对所有
 *   页面成立。
 *
 * 【为什么不能改放「本块顶部」】同一批 dump 显示各页**第一块**的字形缓存可以涨到
 *   号 509（START 菜单 BG0）—— 本块已经满了，没有安全余量。
 *
 * 【v27 定号】域 1 = **下一块的最高 368 个号** = `[1024-368, 1024) = [656, 1024)`。
 *   依据：引擎的 UI 图形从下一块低号段往上长，四个页面实测最高只到偏移 99，
 *   而我方从偏移 144 起 ⇒ 留 45 个号（1.4 KB）余量。
 *   并且改用**绝对块内号**（去掉 `+ TILE_BASE`）：号段恒定，不会因为某个窗口的
 *   TILE_BASE 偏大而整体越界（旧写法 `tb+528+368 <= 1024` 要求 tb <= 128）。
 *   越界护栏仍保留：号段本来就在界内，护栏只剩「槽号超出 92 ⇒ 不落砖」。
 *
 * ⚠ 残留风险（未测）：战斗页 / 领航员 / PC 箱子等尚未采集。若某页把 UI 图形塞到
 *   下一块偏移 > 144，仍会撞。判据脚本已就位，补测即可（`.tmp/bgref.py`）。
 * ============================================================================ */

/* ================= v28：域 1 上界必须让开 tilemap（v27 的 656 太高） ============
 *
 * 【症状】2026-09-21 用户截图 + 冷启动复现（`t_info` = 「宝可梦信息」概况页）：
 *   整页碎片化 —— 顶部黄绿标题条变黑、宝可梦立绘与草地被撕碎、满屏红/灰小方块。
 *
 * 【定位（`.tmp/vramdiff.py` o_info vs t_info）】差异**只在 cb3**（我方域 1 所在
 *   的块），而 cb1/cb2 逐字节相同 ⇒ 不是引擎覆盖我们，是**我们写坏了别的东西**。
 *   再看 `BG0` 的 tilemap（`.tmp/mapgrid.py t_info 0`）：
 *
 *     r00: ... 0 780 784 786 788 664 ... 522 524 904 908 910 0
 *     r01: ... 0 781 785 787 789 665 ... 523 525 905 909 911 0
 *
 *   号 904/908/910 = 槽 62/63，地址 = `cb2 + 904*32` = `0x0600F100`。
 *   **而 BG0 的 tilemap 就在 `0x0600F000`**（概况页 BG0CNT sb=30）⇒
 *   我们把中文字形写进了**地图表本身** ⇒ 表项变成一堆垃圾号 ⇒ 满屏碎片。
 *
 * 【真正的空间地图（cb3 = 下一块，512 个号）】
 *   偏移 0..99    引擎 UI 图形（原盘 A/B：概况页 0..13、标题菜单 91..99、
 *                 START 菜单 25..27 + 91..99 ⇒ 取并集 0..99）
 *   偏移 100..255 **空**  ← 39 槽
 *   偏移 256..383 概况页 **BG3 的 tilemap**（sb=28 ⇒ `0x0600E000`，64×32=4 KB）
 *   偏移 384..447 概况页 **BG0 的 tilemap**（sb=30 ⇒ `0x0600F000`，32×32=2 KB）
 *   偏移 448..511 标题菜单 **BG0 的 tilemap**（sb=31 ⇒ `0x0600F800`）
 *   ⇒ 只有一个连续空档：**偏移 [100, 256) = 号 [612, 768)**。
 *
 * 【为什么 v27 的「抬到顶部」是错的方向】`0x0600F000` 乍看是「高位空区」，其实
 *   是**给文字层用的 tilemap 槽**（sb 30/31），越靠近顶部越危险。抬得越高，
 *   越容易一屁股坐在 map 上 —— 而且只有「字数多到用满 60+ 槽」的页面才暴露
 *   （标题菜单 13 个字，恰好没踩到，所以当时看着是好的）。
 *
 * 【v28 定号】域 1 = 号 `[612, 768)`，39 槽。两个界都是**实测**出来的：
 *   下界 100 = 让开 UI 图形；上界 256 = 让开 tilemap。
 *
 * ⚠ 待办：39 槽 < 概况页需要的 ~64 槽 ⇒ 会出现 LRU 淘汰（屏幕上已有的字指向
 *   被复用的槽 ⇒ **串字**）。扩容方向见 docs/20260921_*（候选：把 cb3 的
 *   偏移 [448,512) 那 16 槽按「标题菜单字数少」的前提并入，或对 cb1 窗口启用
 *   偏移 [256,352)）。**不要**为此复活水位/账本。
 * ============================================================================ */

/* v33：人口 = 窗口所在 BG 层的 char 块基址（= 模板 tileData）。
 *   0x06004000(cb1) → 0   0x06008000(cb2) → 1   0x06000000(cb0) → 2
 * 未知值一律当 cb2（最常见）。 */
static unsigned chs_domain_of(uintptr_t tile_data)
{
    if (tile_data == 0x06004000u)
        return 0u;
    if (tile_data == 0x06000000u)
        return 2u;
    return 1u;
}

/* 写砖基址 = 本窗口所在 BG 层的 char 块基址。锚点恒为模板 tileData（引擎自己
 * 往那儿画字形缓存），只在是已知 char 块基址时才信，否则退回 cb2。 */
static uintptr_t chs_bg_blk(uint8_t *tpl)
{
    uintptr_t b = (uintptr_t)win_u32(tpl, TPL_TILE_DATA);

    if (b == 0x06004000u || b == 0x06008000u || b == 0x06000000u)
        return b;
    return 0x06008000u;
}

/* 字符键 → 槽号（表体在 ADDR_CHS_SLAB，见文件上方铁律）。
 * 键 = (lo, hi)：lo = 本字身份（码/字号/墨宽/相位），hi = 上一字身份（见 v26 一节）。
 * 命中刷新 LRU 时间戳；未命中优先取空槽，无空槽则淘汰最久未用者。
 * ⚠ 槽号在**人口内**唯一：`(dom, slot)` 才对应一个确定的字节地址与 tile 号。
 * ⚠ 三个入口槽数不同（16 / 68 / 32），表长必须按人口取。 */
static uint16_t chs_slot_for(unsigned dom, uint32_t lo, uint32_t hi)
{
    const uint16_t n = (uint16_t)chs_pool_n(dom);
    uint16_t i, victim;
    uint32_t tick, best;
    volatile uint32_t *kw;
    volatile uint32_t *st;
    uint32_t keys_off = chs_keys_off(dom);
    uint32_t st_off = chs_stamps_off(dom);

    if (CHS_SLAB_U32(0u) != CHS_SLAB_MAGIC) {          /* 首次使用：清零建表 */
        /* ⚠ 三个人口槽数不同，必须各清各的长度（曾用单一长度同时清两张表，
         * 结果末槽留脏值 ⇒ 误命中 ⇒ 当场串字）。 */
        unsigned d, j;
        for (d = 0u; d < 3u; d++) {
            uint32_t ko = chs_keys_off(d);
            uint32_t so = chs_stamps_off(d);
            unsigned nn = chs_pool_n(d);
            for (j = 0u; j < nn; j++) {
                CHS_SLAB_U32(ko + (uint32_t)j * 8u) = 0u;
                CHS_SLAB_U32(ko + (uint32_t)j * 8u + 4u) = 0u;
                CHS_SLAB_U32(so + (uint32_t)j * 4u) = 0u;
            }
        }
        CHS_SLAB_U32(CHS_SLAB_TICK) = 0u;
        CHS_SLAB_U32(0u) = CHS_SLAB_MAGIC;
    }
    kw = (volatile uint32_t *)(uintptr_t)(ADDR_CHS_SLAB + keys_off);
    st = (volatile uint32_t *)(uintptr_t)(ADDR_CHS_SLAB + st_off);

    if (lo == 0u)
        lo = 1u;                                       /* 0 = 表尾哨兵，不能当键 */
    tick = CHS_SLAB_U32(CHS_SLAB_TICK) + 1u;
    if (tick >= 0xF0000000u) {                         /* 防回绕：三张表整体折半保序 */
        /* 每个人口的 STAMPS 区不同，必须各折各的；同一张表只折一次
         * （折两次等于除以 4，虽然仍保序，但高位消耗加倍）。 */
        unsigned d, j;
        for (d = 0u; d < 3u; d++) {
            uint32_t so = chs_stamps_off(d);
            unsigned nn = chs_pool_n(d);
            for (j = 0u; j < nn; j++)
                CHS_SLAB_U32(so + (uint32_t)j * 4u) >>= 1;
        }
        tick = 0x78000000u;
    }
    CHS_SLAB_U32(CHS_SLAB_TICK) = tick;

    for (i = 0u; i < n; i++) {
        if (kw[i * 2u] == lo && kw[i * 2u + 1u] == hi) {
            st[i] = tick;
            return i;
        }
    }
    victim = n;                                        /* 哨兵：无空槽 */
    for (i = 0u; i < n; i++) {
        if (kw[i * 2u] == 0u) {
            victim = i;
            break;
        }
    }
    if (victim == n) {
        best = st[0];
        victim = 0u;
        for (i = 1u; i < n; i++) {
            if (st[i] < best) {
                best = st[i];
                victim = i;
            }
        }
    }
    kw[victim * 2u] = lo;
    kw[victim * 2u + 1u] = hi;
    st[victim] = tick;
    return victim;
}

/* 读某槽的「本字身份」（lo）—— 上一字右半的搬运源校验用。 */
static uint32_t chs_slot_lo(unsigned dom, uint16_t slot)
{
    uint32_t off = chs_keys_off(dom) + (uint32_t)slot * 8u;

    return CHS_SLAB_U32(off);
}

/* 返回本字左上砖的 tile 号（= 该 BG 层 charBase 块内的 index）。
 * 槽内四号固定 [左上,左下,右上,右下] = +0/+1/+2/+3（见 v24/v25 说明）。
 * 写砖基址由调用方按**同一个** tileData 算，口径一致。
 * 唯一护栏：槽号超出本人口容量就本字不落砖（不是「装不下退回」分支）。
 * `dom_out` / `base_out` 回传本人口身份，供 v26 的「上一字右半」搬运源做校验。 */
static uint16_t chs_claim_tile(TextPrinter *win, uint32_t lo, uint32_t hi,
                               unsigned *dom_out, uint16_t *base_out)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
    uint16_t slot;
    unsigned dom;

    if (!tpl)
        return 0u;
    tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!tile_data)
        return 0u;

    dom = chs_domain_of((uintptr_t)tile_data);
    if (dom_out)
        *dom_out = dom;
    if (base_out)
        *base_out = chs_slot_tile(dom, 0u);

    slot = chs_slot_for(dom, lo, hi);
    if (slot >= chs_pool_n(dom))
        return 0u;                           /* 本人口用满后不再外溢到越界号 */
    return chs_slot_tile(dom, slot);
}

static void fill_colors(TextPrinter *win, uint8_t colors[16])
{
    uint8_t fg_ov = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    uint8_t color_c = fg_ov ? fg_ov : win_u8(win, WIN_COLOR_C);
    uint8_t color_d = win_u8(win, WIN_COLOR_D);
    uint8_t color_e = win_u8(win, WIN_COLOR_E);
    unsigned i;

    for (i = 0; i < 16u; i++)
        colors[i] = color_d;
    colors[14] = color_e;
    colors[15] = color_c;
}

/* 【已撤销】chs_line_has_next() —— 曾用于把尾列清底右界收到「下一字墨迹起点」。
 *
 * 记录在此以免重走：
 *   12px 步进（墨宽 11）下相邻两字**共用同一个 tile 列** ——
 *       本字尾   占该 tile 的 px[0, w1)      w1 = ink - w0
 *       下一字头 占该 tile 的 px[next, 8)     next = (px + advance) & 7 = w1 + 1
 *   ⇒ 理论无人认领的只有 px[w1, next) —— 0 或 1 个像素。
 *   于是 2026-09-21 改成 `chs_fill_bg(t1, w1, (px + advance) & 7)`，
 *   想借此治好「设置页『普通』的『通』只剩右半」。
 *
 * 🔴 **实测证伪，已回退**（`.tmp/bgview_*_bg0.png` + dump 逐列比对）：
 *   与「引擎自己的字形缓存」共存后（P32 停用，见 main.asm），同一个 tile 列里
 *   **本来就常驻引擎原盘（日文）字形的残留像素**；只清 0~1 列 = 把这些残影留在屏上
 *   —— 设置页每一行标签末尾都多出一根 ink/shadow 竖条。
 *   清满 8 才是对的。
 * ⇒ 结论：治「半个字」要从**重画一致性**（让同一行的字在同一次重画里更新）
 *   入手，不要回到「按相位算清底右界」。 */
static void chs_fill_bg(TextPrinter *win, uint8_t tm, uint16_t tile,
                        unsigned x0, unsigned x1)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
    uint8_t colors[16];
    uint8_t zero[32];
    uint16_t dlow = chs_lower_delta(tm);
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
    fill_colors(win, colors);
    for (i = 0; i < 32u; i++)
        zero[i] = 0u;
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)tile << 5)),
                           0, zero, x1 - x0, x0, colors);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(tile + dlow) << 5)),
                           0, zero, x1 - x0, x0, colors);
}

/* ---- v26：逐像素 nibble 搬运/清零 ----------------------------------------
 * 4bpp tile = 8 行 × 4 B；与 blend_row_4bpp 同一约定：**低 nibble = 较左像素**，
 * 于是一个 u32 就是「一行 8 个像素」，nibble 序号 = 列号。
 *
 * 🔴🔴 **必须整字 32 位读写，绝不可逐字节写。**
 *   GBA 的 VRAM 是 16 位总线；ARM7TDMI 发 8 位写时会把这一字节**整份复制到同一个
 *   半字**（byte 2k 与 2k+1 互相冲掉）。冷启动哨兵实验实测（`.tmp/bytediff.py`，
 *   把「列号标记」写进 TL 砖，期望 vs 实得）：
 *       phase=2 期望 `21 00 00 00`  实得 `12 12 12 12`
 *       phase=4 期望 `21 43 00 00`  实得 `34 34 00 00`
 *       phase=6 期望 `21 43 65 00`  实得 `43 43 65 00`
 *   ⇒ 后写的那一次字节写把同一半字的另一半一起改掉。凡是 `phase >= 4`
 *     （要写 byte0 和 byte1）**必然**被自己的第二次写毁掉 —— 外观上就是
 *     「上一字右半搬进来的列不对 / 半个字错位」，而不是搬运逻辑本身错。
 *   ⇒ 本文件里所有落在 `tile_data`（VRAM）上的像素操作一律整字 RMW。
 *     （`extract_cols` 里的 `put_px4` 写的是栈上 `up/lo`，不在 VRAM，无需改。）
 * ------------------------------------------------------------------------- */
static uint32_t px4_col_mask(unsigned n)
{
    return (n >= 8u) ? 0xFFFFFFFFu : (uint32_t)((1u << (n * 4u)) - 1u);
}

/* dst 的列 [0,n) ← src 的列 [0,n)，其余列原样保留。 */
static void copy_px_cols(uint8_t *dst, const uint8_t *src, unsigned n)
{
    uint32_t m;
    unsigned r;

    if (n == 0u)
        return;
    m = px4_col_mask(n);
    for (r = 0u; r < 8u; r++) {
        uint32_t *dp = (uint32_t *)(void *)(dst + r * 4u);
        uint32_t sv = *(const uint32_t *)(const void *)(src + r * 4u);

        *dp = (*dp & ~m) | (sv & m);
    }
}

/* dst 的列 [0,n) ← 全部填成色号 bg，其余列原样保留。 */
static void clear_px_cols(uint8_t *dst, unsigned n, uint8_t bg)
{
    uint32_t m, pat;
    unsigned r;

    if (n == 0u)
        return;
    m = px4_col_mask(n);
    pat = (uint32_t)(bg & 0x0Fu) * 0x11111111u;
    for (r = 0u; r < 8u; r++) {
        uint32_t *dp = (uint32_t *)(void *)(dst + r * 4u);

        *dp = (*dp & ~m) | (pat & m);
    }
}

/* 12px/11px 两段式 + 相位共享；ink=墨宽、advance=步进（11×11 库：11/12）。
 * 返回游标推进列数 adv = (phase + advance) >> 3 */
static unsigned print_glyph_px(TextPrinter *win,
                               const uint8_t g128[CHS_CELL_BYTES],
                               unsigned ink, unsigned advance, uint32_t key)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data;
    uint8_t colors[16];
    uint8_t up[32], lo[32];
    unsigned px, phase, w0, w1, adv, dom, prev_slot;
    uint16_t t0, t1, dlow, prev;
    uint8_t tx0, tm;

    px = v8_phase_get(win);
    phase = px & 7u;
    w0 = (8u - phase < ink) ? (8u - phase) : ink;
    w1 = ink - w0;
    adv = (phase + advance) >> 3;
    dlow = chs_lower_delta(win_u8(win, WIN_TEXTMODE) & 7u);
    tx0 = win_u8(win, WIN_CURSOR_TILE_X);
    tm = win_u8(win, WIN_TEXTMODE) & 7u;
    if (adv < 1u)
        adv = 1u;
    if (!tpl)
        return adv;
    tile_data = (uint8_t *)(uintptr_t)chs_bg_blk(tpl);
    if (!tile_data)
        return adv;
    /* v33：写砖基址 = **本窗口所在 BG 层的 char 块基址**（= 模板 tileData 锚定）。
     * map 号由 chs_claim_tile 按同一基址给出，两者同口径 —— 不再用固定
     * CHS_CHAR_BLK（那在 BG0charBase=1 的屏面（队伍/详情页）会整体错位，
     * 队名整片乱码就是这么来的）。 */

    fill_colors(win, colors);

    /* ---- v26 第一步：先算出本域基址，并从**本格现存的 map 项**反查上一字身份 ----
     * 上一字写完右半时，把它的「+2 砖号」留在了本格（它的 格+1 = 本格）。
     * 该砖号是 10 位号，位模式 `(号 - 域基) % 4 == 2` 只可能是我们本域的 R 砖。 */
    dom = chs_domain_of((uintptr_t)tile_data);
    prev = 0u;
    prev_slot = 0xFFFFu;
    if (phase != 0u) {
        uint16_t *cellp = GetCursorTilemapPointer_Origin(win);
        uint16_t pv = cellp ? (uint16_t)(*cellp & 0x03FFu) : 0u;

        /* 本格现在指向的号，是不是**本域**的「R 砖」（+2 对齐）？
         * 是 ⇒ 它就是上一字写下的右半砖，据此反查上一字身份。
         * 不是（首字 / 引擎残留 / 别的域）⇒ 一律当没有上一字。 */
        prev_slot = chs_tile_slot(dom, pv);
        if (prev_slot != 0xFFFFu)
            prev = pv;
    }

    /* ---- v26 第二步：取槽。键 = (本字身份, 上一字身份)，见 v26 一节 ---- */
    t0 = chs_claim_tile(win, (key << 3) | phase,
                        (prev_slot != 0xFFFFu)
                            ? chs_slot_lo(dom, (uint16_t)prev_slot) : 0u,
                        (unsigned *)0, (uint16_t *)0);
    if (t0 == 0u)
        return adv;

    /* v34：12px 步进下一个字**跨 2 格**（左格 + 右格），两格是**两个独立槽**
     * （1 格 = 1 槽 = 上/下两砖）。右格的键 = (本字, phase) 并置 hi 位 31 作 R 标记。
     *
     * 为什么必须独立取槽：右格的内容**只由本字决定**（px[w0, ink)），而左格的内容
     * 还要带上「上一字的右半」⇒ 两者键不同、物理砖不同。若让右格复用左格槽，
     * 本字左半（后写）会盖掉自己写进去的右半。
     *
     * `hi` 位 31 作标记是安全的：左格槽的 hi 只有两种取值 —— `0`（首字/无前字）
     * 或 `chs_slot_lo(...) = (key << 3) | phase`，而 `key = chs_make_key()` 最大
     * `code(≤0x1BFF) << 8` ⇒ `key << 3` 远小于 2^31，永不带位 31 ⇒ 键空间不相交。 */
    t1 = 0u;
    if (w1 != 0u) {
        t1 = chs_claim_tile(win, (key << 3) | phase, CHS_KEY_R_MARK,
                            (unsigned *)0, (uint16_t *)0);
        if (t1 == 0u)
            return adv;
    }

    /* ---- v26 第三步：把上一字的右半抄进本槽（px[0,phase)），再写本字左半 ---- */
    if (phase != 0u) {
        uint8_t *du = tile_data + ((uint32_t)t0 << 5);
        uint8_t *dl = tile_data + ((uint32_t)(t0 + dlow) << 5);

        if (prev != 0u) {
            copy_px_cols(du, tile_data + ((uint32_t)prev << 5), phase);
            copy_px_cols(dl, tile_data + ((uint32_t)(prev + dlow) << 5), phase);
        } else {
            /* 首字 / 本格不是我们的 R 砖（引擎残留）⇒ 绝不留残影 */
            clear_px_cols(du, phase, colors[0]);
            clear_px_cols(dl, phase, colors[0]);
        }
    }

    extract_cols(g128, 0u, w0, up, lo);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)t0 << 5)),
                           0, up, w0, phase, colors);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(t0 + dlow) << 5)),
                           0, lo, w0, phase, colors);

    if (w1 != 0u) {
        extract_cols(g128, w0, w1, up, lo);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)t1 << 5)),
                               0, up, w1, 0u, colors);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(tile_data + ((uint32_t)(t1 + dlow) << 5)),
                               0, lo, w1, 0u, colors);
        /* 尾列清底：**必须清满到 8**，不能只清到「下一字墨迹起点」。
         *
         * 2026-09-21 曾按「只清无人认领的 px[w1, (px+advance)&7)」改过一版
         * （理由：12px 步进下相邻两字共用同一 tile 列，多清会擦掉下一字的头列）。
         * 🔴 **该改动已撤销 —— 实测在设置页引入可见残影**：
         *   与「引擎自己的字形缓存」共存后，我们这一列里常有**引擎原盘字形
         *   （日文）的残留像素**；只清 0~1 列会把这些残留留在屏上
         *   （实测差异 tile 28 个、逐列比对为 ink/shadow 值的孤立竖条）。
         *   清满 8 才能把它们抹掉。见 docs 与 memory/2026-09-21.md。
         * ⇒ 现状取舍：宁可多清一列（下一字紧随重画时会覆盖回去），
         *   也不留日文残影。若日后要治「半个字」，应从**重画一致性**入手，
         *   不要回到「按相位算清底右界」。 */
        chs_fill_bg(win, tm, t1, w1, 8u);
    }

#if CHS_TRACE
    trace_glyph((uint32_t)(uintptr_t)win, (uint32_t)(uintptr_t)tpl,
                win_u16(win, WIN_TILE_BASE), win_u16(win, WIN_TILE_OFFSET),
                win_u8(win, WIN_CURSOR_X), win_u8(win, WIN_CURSOR_Y),
                tx0, win_u8(win, WIN_CURSOR_TILE_Y),
                t0, t1, prev, (uint8_t)phase, (uint8_t)adv, tm, g_trace_ch);
#endif

    UpdateTilemap_PreserveCursorX(win, t0, (uint16_t)(t0 + dlow));
    if (w1 != 0u) {
        win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(tx0 + 1u));
        UpdateTilemap_PreserveCursorX(win, t1, (uint16_t)(t1 + dlow));
    }
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(tx0 + adv));

    v8_phase_advance((uint16_t)advance);
    return adv;
}

/* tm2 血条：win[0x20] 线性缓冲直绘（无分配器/无 tilemap，列槽=0x40=上/下半
 * 两 tile）。9×9 字体（步进 10、墨 9）相位两段式：本列 phase..phase+w0，
 * 尾列 0..w1 并把 w1..8 清底；每字推进 adv 列（dst += adv*0x40）。
 * 相位用全局 v8_phase（InitTextPrinter 会话边界复位，血条名是独立会话）。 */
static unsigned tm2_print_px(TextPrinter *win,
                             const uint8_t g128[CHS_CELL_BYTES],
                             unsigned ink, unsigned advance)
{
    uint8_t colors[16];
    uint8_t up[32], lo[32], zero[32];
    uint32_t dst, dnext;
    unsigned px, phase, w0, w1, adv, i;

    dst = win_u32(win, WIN_TILE_DATA);
    if (dst == 0u)
        return 1u;

    px = v8_phase_get(win);
    phase = px & 7u;
    w0 = (8u - phase < ink) ? (8u - phase) : ink;
    w1 = ink - w0;
    adv = (phase + advance) >> 3;
    if (adv < 1u)
        adv = 1u;

    fill_colors(win, colors);
    for (i = 0; i < 32u; i++)
        zero[i] = 0u;

    extract_cols(g128, 0u, w0, up, lo);
    (void)blend_glyph_4bpp((uint32_t *)(void *)dst, 0, up, w0, phase, colors);
    (void)blend_glyph_4bpp((uint32_t *)(void *)(dst + 0x20u), 0, lo, w0, phase,
                           colors);

    dnext = dst + 0x40u;
    if (w1 != 0u) {
        extract_cols(g128, w0, w1, up, lo);
        (void)blend_glyph_4bpp((uint32_t *)(void *)dnext, 0, up, w1, 0u, colors);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(dnext + 0x20u), 0, lo, w1,
                               0u, colors);
        if (w1 < 8u) {
            (void)blend_glyph_4bpp((uint32_t *)(void *)dnext, 0, zero,
                                   8u - w1, w1, colors);
            (void)blend_glyph_4bpp((uint32_t *)(void *)(dnext + 0x20u), 0,
                                   zero, 8u - w1, w1, colors);
        }
    } else if (phase + w0 < 8u) {
        /* 墨未跨列且本列未写满（8px 标点等）：右侧清底防残留 */
        (void)blend_glyph_4bpp((uint32_t *)(void *)dst, 0, zero,
                               8u - (phase + w0), phase + w0, colors);
        (void)blend_glyph_4bpp((uint32_t *)(void *)(dst + 0x20u), 0, zero,
                               8u - (phase + w0), phase + w0, colors);
    }

    win_set_u32(win, WIN_TILE_DATA, dst + (uint32_t)adv * 0x40u);
    v8_phase_advance((uint16_t)advance);
    return adv;
}

/* ---- 唯一落点：按 tm 写目标；返回推进列数（供 TILE_OFFSET）----
 * advance=本字步进像素（12/10），ink=墨宽（11/9），二者分离（11×11 库
 * 墨 11 步进 12、9×9 库墨 9 步进 10，pokeE 语义）。
 * 旧 8px/16px 光栅路径已删（2026-09-08 两档制 2.0；advance 恒为
 * 12/10/8，全走相位两段式 print_glyph_px）。 */
static unsigned chs_emit(TextPrinter *win, uint8_t tm, unsigned advance,
                         const uint8_t g128[CHS_CELL_BYTES], unsigned ink,
                         uint32_t key)
{
    unsigned adv;

    if (ink == 0u)
        ink = advance;

    if (tm == 2u)
        return tm2_print_px(win, g128, ink, advance);

    adv = print_glyph_px(win, g128, ink, advance, key);
    /* TILE_OFFSET 已不再参与我方定号（v24 字符键），但仍按旧式推进：
     * 引擎 tm0 的下箭头图形落在 TILE_BASE+TILE_OFFSET（0x08003DF0 分支）。 */
    if (tm == 0u || tm == 1u)
        win_set_u16(win, WIN_TILE_OFFSET,
                    (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + adv * 2u));
    return adv;
}

/* 字符键：字码 + 字形档位。同一字在同一档位 ⇒ 同一槽；
 * 同字不同档（大库 11×11 / Middle 9×11 / 小库 9×9）位图不同，必须分开占槽。 */
static uint32_t chs_make_key(uint32_t code, uint8_t lib, uint8_t ink)
{
    return (code << 8) | ((uint32_t)(lib & 0x3Fu) << 4) | (uint32_t)(ink & 0x0Fu);
}

static void jp_glyph_to_g128(uint8_t font_num, uint16_t glyph,
                             uint8_t g128[CHS_CELL_BYTES])
{
    uint8_t *up, *lo;
    unsigned i;

    GetGlyphTilePointers_Origin(font_num, glyph, &up, &lo);
    for (i = 0; i < CHS_CELL_BYTES; i++)
        g128[i] = 0u;
    if (FontIsShadowed(font_num)) {
        copy_tile32(g128 + 0x00u, up);
        copy_tile32(g128 + 0x20u, lo);
    } else {
        CopyGlyph1bppTo4bpp_Origin(up, g128 + 0x00u, 15u, 0u);
        CopyGlyph1bppTo4bpp_Origin(lo, g128 + 0x20u, 15u, 0u);
    }
}

void chs_print(TextPrinter *win, uint32_t code, uint8_t fontSize)
{
    uint8_t tm, fn, adv, ink, lib;
    uint8_t g128[CHS_CELL_BYTES];
    uint8_t w = 0;
    uint8_t saved_fn;

    /* fontSize=请求步进（翻译层按 tm 传 CHS_PRINT_TMx_FONT_PX） */
    resolve_draw(win, fontSize, &tm, &fn, &adv, &ink, &lib);
#if CHS_TRACE
    g_trace_ch = (uint8_t)code;
#endif

    saved_fn = win_u8(win, WIN_FONTNUM_REAL);
    win_set_u8(win, WIN_FONTNUM_REAL, fn);
    if (!GetGlyph(win, code, g128, &w, lib)) {
        win_set_u8(win, WIN_FONTNUM_REAL, saved_fn);
        return;
    }
    win_set_u8(win, WIN_FONTNUM_REAL, saved_fn);
    (void)chs_emit(win, tm, adv, g128, ink, chs_make_key(code, lib, ink));
}

int DrawHalfWidth(TextPrinter *win, uint32_t cur_char)
{
    uint8_t tm, fn, adv, ink, lib;
    uint8_t g128[CHS_CELL_BYTES];
    unsigned i;

    if (cur_char < SYM_GLYPH_BASE
        || cur_char >= SYM_GLYPH_BASE + SYM_GLYPH_COUNT)
        return 0;

    resolve_draw(win, 0u, &tm, &fn, &adv, &ink, &lib);
    (void)fn;
    (void)adv;

    {
        const uint8_t *sym =
            (const uint8_t *)ADDR_FONT_CHS_SYM
            + (cur_char - SYM_GLYPH_BASE) * 64u;
        for (i = 0; i < CHS_CELL_BYTES; i++)
            g128[i] = 0u;
        for (i = 0; i < 32u; i++) {
            g128[0x00 + i] = sym[i];
            g128[0x20 + i] = sym[32u + i];
        }
    }
    (void)chs_emit(win, tm, 8u, g128, 8u, chs_make_key(cur_char, lib, 8u));
    return 1;
}

int DrawGlyph(TextPrinter *win, uint32_t cur_char)
{
    uint8_t tm, fn, adv, ink, lib;
    uint8_t g128[CHS_CELL_BYTES];

    if (cur_char >= 0xF7u)
        return 1;
    if (DrawHalfWidth(win, cur_char))
        return 1;

    resolve_draw(win, 0u, &tm, &fn, &adv, &ink, &lib);
    (void)adv;
    (void)ink;
    (void)lib;
    #if CHS_TRACE
    g_trace_ch = (uint8_t)cur_char;
    #endif
    jp_glyph_to_g128(fn, (uint16_t)cur_char, g128);
    /* 半角 JP：墨宽 8、步进 8（相位恒 0） */
    (void)chs_emit(win, tm, 8u, g128, CHS_GLYPH_ADVANCE_JP_PX,
                   chs_make_key(cur_char, lib, (uint8_t)CHS_GLYPH_ADVANCE_JP_PX));
    return 1;
}

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

    /* FA..FF：Origin 尾调用进 ROM，返回后本函数后续语句不会执行 */
    if (c >= 0xFAu) {
        /* ① 等 A 箭头（FA=\l 滚动 / FB=\p 清屏）：把落列推到 ceil(px/8)，
         * 别让它压掉本行末字的**尾列**。
         *   · 引擎 DrawInitialDownArrow@0x08003F4C → 箭图形 blit 到固定 tile
         *     (TILE_BASE+0xFE) → UpdateTilemap(win, t, t+1)：**表项格由
         *     [WIN_CURSOR_TILE_X] 决定**（0x08003EA4..EAE 实证）。
         *   · 我们 12px 步进 = 1.5 列 ⇒ 行末常停在半列（px & 7 != 0）。此时
         *     CURSOR_TILE_X = floor(px/8) 恰好 = 行末字的**尾列**（12px 两段式
         *     里相邻字共享尾列）⇒ 箭头表项一盖，行末字只剩左半 = 实机「半个字」。
         *   · 文档 docs/FONT_12PX_DRAW.md：「同句 \p → TILE_X = base_tx +
         *     ceil(chs_px/8)（勿减 CURSOR_X）」= 半列时推一列到 ceil。
         *   ⚠ 推完**不还原**：闪烁箭头每帧按 CURSOR_TILE_X 重画，还原会再压回去。
         *   ⚠ 行内 px == 0（`\n{\p}` 空行）不动 —— 保持 FE 光标，避免双▼。 */
        if (c == 0xFAu || c == 0xFBu) {
            uint16_t px = v8_phase_get(win);

            if ((px & 7u) != 0u) {
                win_set_u8(win, WIN_CURSOR_TILE_X,
                           (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
                /* tm0 线性：箭头**图形**落在 TILE_BASE+TILE_OFFSET 那个 tile
                 * 上（0x08003DF0 分支）——行末同样停在尾列，一并推一列。 */
                if ((win_u8(win, WIN_TEXTMODE) & 7u) == 0u)
                    win_set_u16(win, WIN_TILE_OFFSET,
                                (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + 2u));
            }
        }
        /* ② 换行类控制码 → 显式复位行相位：FE(\n 换行) / FB(\l 滚动) / FA(\p 清屏)。
         * 不依赖 v8_phase_get 行标识（tpl^curY^curTileY）的**时序** —— 官方 FE
         * 是「先推一个、另一个稍后才变」，存在漏检窗口。漏检时新行首字会带
         * 上一行的累计相位起步：累计 = 12n mod 8，**n 为奇数时 = 4** ⇒ 走
         * phase!=0 分支复用 v8_phase_last_tile()（上一行行尾字的尾列 tile）
         * ⇒ 覆写行尾字右半 ⇒ 实机「奇数个字的一行，换行后行尾只剩半个字」。 */
        if (c == 0xFAu || c == 0xFBu || c == 0xFEu)
            v8_phase_reset();
        return PrintNextChar_Origin(win);
    }

    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx + 1u));

    if (*(volatile uint8_t *)ADDR_V6_BYPASS != 0u)
        return 1;

    if (TranslateHandleChar(win, c))
        return 1;
    DrawGlyph(win, c);
    return 1;
}
