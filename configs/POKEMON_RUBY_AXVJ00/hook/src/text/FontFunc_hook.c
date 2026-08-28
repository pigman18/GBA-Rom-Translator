/* ============================================================================
 * FontFunc_hook.c — 文本落址协议桥接（四种 textMode）
 *
 * 设计原则：**只替换"落址/表项"，像素处理仍走 ROM 原生与原 refpr 原语**。
 * 分派依据 win[0x0A](textMode) —— 不按 template 地址/光标值/tileBase 猜场景。
 *
 * ---- 四种原生落址协议（capstone 反汇编实证）----
 *  tm0 @0x08003569 → sub_8003520 @0x08003520（纯函数）
 *      tile = win[0x16] + win[0x18]；dst = tileData + (tile<<5)
 *      sub_8003630(glyph, dst, win[0xB], win[0xC], win[0xD], win[0xE])
 *      UpdateTilemap(win, tile, tile+1)    ← upper/lower 是【上下两行】
 *      推进：win[0x18] += 2; win[0x1B] += 1
 *  tm1 @0x0800360D → FontSubTable[fontNum] @0x081BB3BC（ROM 查表，预渲染 tile）
 *      font0/3: win[0x16]+glyph*2     font1/4: win[0x16]+FontType1Map[glyph*4]
 *      font2/5: upper=win[0x16]+0xD4, lower=win[0x16]+glyph
 *      font6  : win[0x16]+BrailleMap[glyph*4]
 *      ★ 零 VRAM 写入、零 win[0x18] 读写；推进 win[0x1B] += 1
 *  tm2 @0x0800338C（缓冲区直绘，TPL_TILEMAP==0，无 tilemap）
 *      dst = win[0x20]；sub_8003630(...)；推进 win[0x20] += 0x40
 *  tm3 @0x08003494 → sub_8003464 @0x08003464（grid 二维）
 *      idx = win[0x16] + (win[0x1A]+win[0x1B]+2) + (win[0x1C]+win[0x1D])*30
 *      dst = tileData + (idx<<5)   ← tile 索引 == 屏幕格子索引（sub_80034E0/500）
 *      UpdateTilemap(win, idx, idx+30)；推进 win[0x1B] += 1
 *      ★ 绘制用 sub_80033B4，不是 sub_8003630
 *
 * ---- 12px 字模的 spill（"8+4 / 4+8"）----
 *  px 序列 0,12,24,36… → startPixel = px&7 在 0/4 交替。每个字分【两趟】：
 *    pass1: 宽 8  → tl/bl  写 tile N，溢出部分 spill 到 tile N+1
 *    pass2: 宽 4  → tr/br  写 tile N+1，溢出 spill 到 tile N+2
 *  相邻字共享 tile（字 A 的右 4px 与字 B 的左 4px 同处一个 tile），
 *  故必须经 DrawGlyphTile_refpr 做移位 + spill，不能直接 copy_tile32。
 *
 * ---- 字库选择 ----
 *  FontChsSmall(fontId=4, 8px) 仅用于 tm2 战斗窗口昵称与队伍名；
 *  其余场景用常规字体（12px）。见 DecompressGlyph_Chinese 的 fontId 分支。
 *
 * 实证见 docs/调研_20260828_原生tm0协议与替换BUG根
 * ==========================================================================*/

#include "game.h"
#include "text.h"
#include "text_render.h"
#include "text_scene.h"

/* ---- 行相位影子存储 -------------------------------------------------------
 * game.bin 无 RAM 段（link/game.ld），全局落 ROM 不可写。
 * 0x0203FF80-0x0203FFCF 为已验证安全区；本模块取 0x0203FF84/0x88（避开
 * 旧 CHS_PITCH_CTRL@0x80 与 ChsPhase[8]@0x90）。 */
#define PROTO_PHASE_ADDR   0x0203FF84u   /* key(u16) << 16 | px(u16) */
#define PROTO_BASE_TX_ADDR 0x0203FF88u   /* 行首 cursorTileX (u8)    */

/* tm1 线性分配地板：tm1 窗口 tileData 前部是【ROM 预渲染字体区】，
 * 中文必须分配在其后，否则覆写字体。 */
/* 相位 8 槽 LRU（log1 实锤：全局单槽被其他窗口踩踏——换行后首字 px=320、
 * curTX=42，字符画出框外）。布局（安全区 0x0203FF80-0xFFCF 内）：
 *   0x0203FF84 槽[0..7] 每槽 6B：key(u16) px(u16) btx(u8) gen(u8)
 *   0x0203FFB4 ctrl.gen(u8)
 * 非中文字形烘焙改用 32B 栈缓冲（与 refpr 的 temp_words 同级），不占 RAM。 */
#define PHASE_SLOTS_ADDR   0x0203FF84u
#define PHASE_GEN_ADDR     0x0203FFC4u
#define PHASE_N            8u

typedef struct {
    uint16_t key;        /* +0 */
    uint16_t px;         /* +2 */
    uint8_t  btx;        /* +4 行首列 */
    uint8_t  last_adv;   /* +5 上次步进，参与 expect 计算（旧 last_adv） */
    uint8_t  gen;        /* +6 LRU */
    uint8_t  char_base;  /* +7 tpl[1]，与旧实现同，提高区分度 */
} PhaseSlot;

#define TM1_LINEAR_FLOOR   0x100u

/* tm1 确定性分区（无分配器、无槽——v2 行槽已被实测否决：标签/值是同 curY
 * 的不同会话（gdb：值列 curX=15/19/23 vs 标签 curX=4），并发 key ≈17 个，
 * 8 槽轮转覆盖 → 行内容串换）。
 *
 * 基址纯位置推导：row = curY>>1（实测标签 curY=1,5,7..17 → 0,2..8），
 * col = curX>=8（值列）：base = 0x100 + row*0x10 + col*0x8（每子区 4 字）。
 * 9 行 × 2 子区 × 0x8 = 0x90 ⊂ 自由区 [0x100,0x1C8)。同会话重绘永远映射
 * 同一子区 → 幂等，游标不漂移、不外溢。
 *
 * 会话重置检测：原生 ITP 把 win[0x18] 重置回 0x100+(curTX-1)*2（gdb 全部
 * 样本吻合：curTX=2/4/5/7 → 0x102/106/108/10C）。本子区全在 <0x100，
 * 重置值恒 ≥0x102 → 区间判定天然区分，无需公式比对。 */
/* ⚠️ 2026-08-29：v4 / v4.1（偶数槽方案）**已回退**，当前行为 = v3 确定性分区。
 * 回退原因（详见 docs/评估_20260829_text重构合理性反汇编复核.md）：
 *   v4   全屏"1" —— chs_tile_num 仍吃 win[0x16](=1)，tile=1+2=3 = 字模 1 上下半槽
 *   v4.1 仍未修复 —— 子区 0x8 装不下 4 字（12px 相位交错下约需 12 tile）、
 *        部分会话 win[0x18] 未被原生重置（残留 0x2C/0x14A/0x166 落进错子区）、
 *        off 可越过 0x100 再进字库区；且偶数区仅 127 tile 装不下 9 行需求。
 * v3 已知代价：中文区 [0x100,0x190) 压在字库 lower 奇数槽上（R1）→ 数字/问号
 * 被踩。这是"串换已修、基本可读"与"数字正常但整体错乱"之间的取舍，用户
 * 拍板取前者。R1 的彻底解法待专项（见评估文档 §四）：
 *   1) gdb 采 BGCNT 确认设置菜单窗 charBase 与表项值域
 *   2) 反汇编 InitWindowTileData 确认字库预渲染真实布局（连续 or 上下分离）
 *   3) 再据此重设计中文落址（目标：位置式 tile=格子，一次消解 R1/R2/R4） */
#define TM1_SUB_STRIDE     0x8u          /* 每子区 8 tile = 4 个 12px 字 */

/* ---- v5 方案 D：数据驱动安全区（2026-08-29 gdb 实测）----------------------
 * 字库预渲染写满 charBase 2 的 [1,0x201)=512 tile，但**设置菜单实际只引用
 * 22 个字模**（upper 去重集合，每字模占 2 连续 tile，实占 44 tile）：
 *   1 33 49 111 119 323 325 327 329 331 333 335 337 339 345 349 369 397 409 439 447 451
 * → 最大安全连续块 = **[121, 322]（202 tile）**，另有 [3,32]/[51,110]/[453,512]。
 *
 * 实测文本上界（模板 0x081BB874, tm=1）：标签恒 4 字（F9 80 短语：对话速度/
 * 战斗动画/对战规则/声音/按键模式/窗口/关闭/改变设置）。
 *
 * ⚠ 修正（用户实测）：**值不是单个值，而是该行所有候选值并列**，每行 3 个
 * 独立 ITP 会话（gdb 实测同 curY 下 curX=15 / 19 / 22-23 三条）——如"慢 普通 快"。
 * 每个候选 1-2 字，故值区必须**按 curX 分 3 槽**，否则三候选共用一子区互覆
 * （现象："快 快通 快"），且溢出会踩下一条标签（现象：字中间一条白条）。
 *
 * v8 排布——v7 漏判候选数（实测 **4 个**，不是 3 个：curX=15/19/22/23）：
 *   顶窗 curY=0  → TM1_TITLE_BASE          [3, 23)  ⊂ 小块 [3,32]
 *   标签区 12px  → 121 + row*16            [121, 249)  4 字 × 4 tile
 *   值列   8px   → 249 + row*8             [249, 313)  **4 候选槽 × 2 tile**
 *   row = (curY<=1) ? 0 : (curY-3)>>1 → curY{1,5,7,9,11,13,15,17} → 0..7
 *   合计 [121,313] ⊂ 安全块 [121,322]，余量 9；与 22 字模零冲突。
 *
 * ⚠ 候选按 curX 实测分 4 档（<17/<19/<21/<23），不能再合并 22/23 到 else。
 * "适中" 2 字候选 8px 需 4 tile 而槽仅 2 tile，会溢出——目前设置菜单候选
 * 全是单字（慢/适/中/快/替/交/看/单/立/L/是/否...），实测未触发；若日后汉化
 * 增 2 字候选需扩槽。
 *
 * ⛔ 2026-08-29 v9：上面"安全块 [121,322]"的**依据是错的**——把"tilemap
 * 引用稀疏"当成了"VRAM 占用稀疏"。实测 InitWindowTileData 分 256 次把整本
 * 字库**写满** tile [1,513)（tile = startOffset + glyph*2，每字形 2 tile）。
 * → 那 202 个 tile 上压着 128 个真实字形，这就是 R1（数字/问号被踩）的真身。
 * 详见下方 v9 段。 */

/* ---- v9：方案 C「削字库」+ 位置分区（2026-08-29 gdb 实测）----------------
 *
 * 1) 字库占用（一手数据）
 *    InitWindowTileData(tpl, startOffset=1, glyph 0..255)，256 次调用，
 *    返回 r1 = 0x06008060/A0/E0/…（每字形 +0x40 = 2 tile）
 *    → 实占 tile [1, 513)，一个 charblock 被占满。
 *    原生引用到的字形 tile 只有 22 个：
 *      1 33 49 111 119 | 323 325 327 329 331 333 335 337 339 345 349
 *      369 397 409 439 447 451
 *    → 最大空隙 = **[121, 323)（202 tile）**，全不含引用字形 ✓
 *
 * 2) ⛔「削字库」（P24 跳过部分字形）——**实测后停用**，钩子保留为直通。
 *    两条实测把它否掉了：
 *      a) 时序：预渲染循环（日志行 698-4013）整个跑在设置窗口文本打印
 *         （首个 ITP 在 4026 行）**之前**且只跑一次 → 永不覆盖中文，
 *         "跳过以腾地盘"的前提不成立。
 *      b) 跳过反而有害：菜单随后要用到的字形（实测 tile **139 / 255**）
 *         正落在被跳区间 → 那些位置显示成串到别行的中文或纯色方块
 *         （2026-08-29 截图实证：按键模式行首显示"普通"、窗口行首显示"类型"）。
 *    → 正确做法是**中文区避开已实测的引用字形**（见 TM1_ROW_TAB），
 *      字库一字不少地渲染。
 *    注：上面那份"22 个引用 tile"清单是 v3 老日志量的，**不完整**，
 *      漏了 139 / 255。任何"按引用集划安全区"的做法都必须留余量。
 *
 * 3) tile 账目（v8 修掉 pass2 的 off 推进 bug 后重算，勿再用 2n+2）
 *    12px：每字 off 推进 4（pass1 +2 / pass2 +2），**n 字 = 4n tile**
 *    8px ：pass2_w=0 只走一趟，**n 字 = 2n tile**
 *      → 4 字标签 = 16；3 字候选 12px=12 / 8px=6
 *      → **值列必须 8px**，否则 16+12+8+12=48/行 装不进 202
 *
 * 4) 布局（实测几何，以 [CFF] 行为准；ITP 行的 curX/curY 是上一会话残留）
 *    标题 curY=1（curX=4）；菜单行 curY=5,7,9,11,13,15,17（curX=4）
 *    候选 curX ∈ {15,18,19,20,22,23}
 *      标题                → [3, 19)    ⊂ [3,33)
 *      菜单行 r=1..7       → TM1_ROW_TAB[r-1]（**不能用"起点+步长"**：
 *                            可用区间被引用字形 139/255 切成碎块），行内：
 *        标签 (curX<8)     off  0  span 16   （4 字 × 12px）
 *        候选A (15..18)    off 16  span  6   （8px 3 字）
 *        候选B (19..21)    off 18  span  4   （8px 2 字，与 A 尾部重叠，见下）
 *        候选C (>=22)      off 22  span  6   （8px 3 字）
 *      每行跨 28 tile；r7（关闭）无候选项，只用到前 8 tile。
 *
 * ⚠ B 与 A 尾部重叠的合法性（逐行核对，**改翻译文本后必须重核**）：
 *    B 只在 r1(普通=4tile) 与 r6(慢=2tile) 用到；这两行 A 分别只用 2 和 0 tile。
 *    A 用到 4/6 tile 的 r3(替换)/r4(立体声) 都不用 B → 实际不冲突。
 * ⚠ 该引用集为设置菜单专属；但 InitWindowTileData 实测只由 tpl 0x081BB874
 *    使用（256/256 次），其余 tm1 窗口走 LZ77 场景字库，故 P24 钩子按 tpl 门控，
 *    非该窗口一律照常渲染（零回归）。 */
/* ↑ 上面 v9 段第 4 点描的**具体数值**已经全部搬到 src/text/text_scene.c 的
 * 配置表里（kOptRows / kOptSlots / kOptGlyphAvoid），按窗口模板地址键控。
 * 本文件不再持有任何窗口专属常量 —— 改布局请去 text_scene.c，不要在这里加。 */

typedef void (*fn_draw6)(uint32_t glyph, void *dst, uint32_t font,
                         uint32_t fg, uint32_t bg, uint32_t shadow);

/* 前向声明（本文件末尾实现，按 XXX_Origin 规范） */
void FontSub_Origin(TextPrinter *win, uint32_t glyph);
/* src/text/entry.s 的 P24 桩：重放被覆盖的 4 条序言后跳回 0x08002A58 */
void InitWindowTileData_Origin(void *tpl, uint32_t startOffset, uint32_t glyph);
void InitWindowTileData_Hook(void *tpl, uint32_t startOffset, uint32_t glyph);
void FontFunc_Tm0_Origin(TextPrinter *win, uint32_t glyph);
void FontFunc_Tm1_Origin(TextPrinter *win, uint32_t glyph);
void FontFunc_Tm2_Origin(TextPrinter *win, uint32_t glyph);
void FontFunc_Tm3_Origin(TextPrinter *win, uint32_t glyph);

/* 原生字形绘制原语（tm0/tm2）：sub_8003630 —— dst 是【参数】，桥接的支点 */
static void DrawGlyph_Origin(uint32_t glyph, void *dst,
                             uint32_t font, uint32_t fg, uint32_t bg, uint32_t shadow)
{
    ((fn_draw6)(ADDR_DRAW_GLYPH_PRIM | 1u))(glyph, dst, font, fg, bg, shadow);
}

/* 原生字形绘制原语（tm3 专用）：sub_80033B4 @0x080033B4 */
/* 保留备用：tm3 专用原语。当前 draw_native 统一走 sub_8003630（见其注释） */
__attribute__((unused)) static void DrawGlyph_Tm3_Origin(uint32_t glyph, void *dst,
                                 uint32_t font, uint32_t fg, uint32_t bg, uint32_t shadow)
{
    ((fn_draw6)(ADDR_DRAW_GLYPH_TM3_PRIM | 1u))(glyph, dst, font, fg, bg, shadow);
}

/* 统一用 sub_8003630 画非中文到临时缓冲，【不要】用 tm3 的 sub_80033B4。
 * 反汇编实证(0x08003424-0x08003430)：sub_80033B4 把 lower 写到 dst + 960
 *   movs r1,#0xf0; lsls r1,r1,#2  (=960); add r1,r8 → dst+960
 * 因为 tm3 的 upper/lower 在 VRAM 里相隔 30 个 tile(idx 与 idx+30)。
 * 而临时缓冲只有 64B，调用一次就会往 tmp+960 写 32B，冲掉游戏数据
 * —— 表现为数字/符号位显示成汉字(38.PNG "たかさ 约．花")，
 *    以及栈上版本直接把栈写穿崩溃(PC=0xF81FFF1E)。
 * sub_8003630 写 dst 与 dst+32（upper/lower 相邻），对 64B 缓冲安全。 */
static void draw_native(TextPrinter *win, uint32_t glyph, void *dst)
{
    uint32_t fn = win_u8(win, WIN_FONTNUM_REAL);
    uint32_t fg = win_u8(win, WIN_COLOR_C);
    uint32_t bg = win_u8(win, WIN_COLOR_D);
    uint32_t sh = win_u8(win, WIN_COLOR_E);

    DrawGlyph_Origin(glyph, dst, fn, fg, bg, sh);
}

/* ---- 行像素相位 ----------------------------------------------------------*/

static uint16_t phase_key(TextPrinter *win)
{
    /* 行指纹：换行/换流 → key 变 → px 自动归零 */
    return (uint16_t)(win_u16(win, WIN_TILE_BASE)
                      ^ ((uint16_t)win_u8(win, WIN_CURSOR_Y) << 8)
                      ^ ((uint16_t)win_u8(win, WIN_CURSOR_X) << 4)
                      ^ (uint16_t)win_u8(win, WIN_CURSOR_TILE_Y)
                      ^ ((uint16_t)(uintptr_t)win_template(win) & 0xFFF0u));
}

/* 绑定当前行的槽。
 * ⚠ 关键：命中已有槽时【必须做连续性校验】，否则会把上一次绘制会话残留的 px
 *   继续累加 —— 表现为路名/对话重复绘制时文字一路向右铺满整屏、多条文本互相
 *   穿插（用户观察："私有变量追加到公有变量"）。
 *   校验式与 chs_sync_tilex 的写入式严格配对：curTX = btx + ((px-1)>>3)。
 *   旧实现 DrawGlyphTiles_common(text_render.c:436-453) 同构。 */
static int phase_bind(TextPrinter *win, uint16_t *px_out, uint8_t *btx_out)
{
    volatile PhaseSlot *S = (volatile PhaseSlot *)PHASE_SLOTS_ADDR;
    volatile uint8_t *genp = (volatile uint8_t *)PHASE_GEN_ADDR;
    uint8_t *tpl = win_template(win);
    uint8_t char_base = tpl ? tpl[1] : 0u;
    uint16_t key = phase_key(win);
    uint8_t g = (uint8_t)(*genp + 1u);
    uint8_t cur_tx = win_u8(win, WIN_CURSOR_TILE_X);
    unsigned i, best = 0;
    uint8_t best_gen = 255;

    *genp = g;
    for (i = 0; i < PHASE_N; i++) {
        if (S[i].key == key && S[i].char_base == char_base) {
            S[i].gen = g;
            if (S[i].px != 0u) {
                unsigned last = S[i].last_adv ? (unsigned)S[i].last_adv
                                              : (unsigned)CHS_GLYPH_ADVANCE_PX;
                uint8_t expect =
                    (uint8_t)(S[i].btx + (uint8_t)((S[i].px + last - 1u) >> 3));
                if (cur_tx <= S[i].btx || cur_tx != expect) {
                    /* 不是同一次连续的绘制 → 重新起行 */
                    S[i].px  = 0u;
                    S[i].btx = cur_tx;
                }
            } else {
                S[i].btx = cur_tx;          /* 行首：每次重捕获 */
            }
            *px_out  = S[i].px;
            *btx_out = S[i].btx;
            return (int)i;
        }
        if (S[i].gen < best_gen) { best_gen = S[i].gen; best = i; }
    }

    /* 新槽 */
    S[best].key       = key;
    S[best].px        = 0u;
    S[best].btx       = cur_tx;
    S[best].last_adv  = (uint8_t)CHS_GLYPH_ADVANCE_PX;
    S[best].char_base = char_base;
    S[best].gen       = g;
    *px_out  = 0u;
    *btx_out = cur_tx;
    return (int)best;
}

static void phase_px_store(TextPrinter *win, int slot, uint16_t px)
{
    volatile PhaseSlot *S = (volatile PhaseSlot *)PHASE_SLOTS_ADDR;

    (void)win;
    S[slot].px = px;
}

/* 由槽内 base_tx 同步 cursorTileX（式同旧 chs_finish：(px+w-1)>>3） */
/* 与旧 chs_finish 同式：curTX = btx + ((px + adv - 1) >> 3)。
 * 连续性校验(phase_bind)必须用同一个式子，否则会误判为换会话。 */
static void chs_sync_tilex(TextPrinter *win, int slot, unsigned px, unsigned adv)
{
    volatile PhaseSlot *S = (volatile PhaseSlot *)PHASE_SLOTS_ADDR;

    S[slot].last_adv = (uint8_t)adv;
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(S[slot].btx + ((px + adv - 1u) >> 3)));
}

/* ---- 落址：按 textMode 求 tile 编号 / VRAM 指针 ---------------------------*/

/* 前向声明：tm1 行基址（实现见中文入口前），chs_tile_num 需要它算 tile 索引 */
static uint16_t tm1_row_base(TextPrinter *win);
static const struct Tm1WinCfg *tm1_cfg(TextPrinter *win);

static uint16_t chs_tile_num(TextPrinter *win, unsigned map_tx, int col_delta, int row_delta)
{
    uint8_t  tm   = win_u8(win, WIN_TEXTMODE) & 7u;
    uint16_t base = win_u16(win, WIN_TILE_BASE);

    if (tm == 3u) {                                  /* grid：列+1，行+30 */
        uint8_t col = (uint8_t)(win_u8(win, WIN_CURSOR_X) + map_tx + (uint8_t)col_delta);
        uint8_t row = (uint8_t)(win_u8(win, WIN_CURSOR_Y)
                                + win_u8(win, WIN_CURSOR_TILE_Y) + row_delta);
        return (uint16_t)(base + col + 2u + (unsigned)row * CHS_TILE_GRID_W);
    }
    {                                                /* tm0 / tm1 */
        uint16_t off = win_u16(win, WIN_TILE_OFFSET);
        /* tm1 分配式：win[0x18] 已是「行内偏移」(0..19，由 chs_blit 恢复/推进)，
         * tile = 行基址 + 行内偏移；**不再加 win[0x16]**（v4 全屏"1"的坑：
         * +win[0x16] 会让所有中文表项指到 1+2=3 = 字模 1）。
         * row_delta=1 → lower=upper+1（gdb 实测 469 条差=1，连续成对）。 */
        if (tm == 1u) {
            const struct Tm1WinCfg *cfg = tm1_cfg(win);

            if (cfg && cfg->mode == TM1_MODE_GRID)
                /* 位置式：lower 在下一行同列(+stride)，spill 在下一列(+1)。 */
                return (uint16_t)(scene_tm1_grid_num(
                                      cfg,
                                      win_u8(win, WIN_CURSOR_X),
                                      win_u8(win, WIN_CURSOR_Y),
                                      win_u8(win, WIN_CURSOR_TILE_Y),
                                      map_tx)
                                  + (uint16_t)(col_delta
                                               + row_delta * cfg->grid_stride));
            return (uint16_t)(tm1_row_base(win) + off
                              + (uint16_t)(col_delta * 2 + row_delta));
        }
        return (uint16_t)(base + off + (uint16_t)(col_delta * 2 + row_delta));
    }
}

static uint8_t *chs_tile_ptr(TextPrinter *win, unsigned map_tx, int col_delta, int row_delta)
{
    if ((win_u8(win, WIN_TEXTMODE) & 7u) == 2u) {
        uint32_t p = win_u32(win, WIN_TILE_DATA);
        return (uint8_t *)(uintptr_t)(p + (uint32_t)col_delta * 0x40u
                                        + (uint32_t)row_delta * 0x20u);
    }
    return vram_tile(win, chs_tile_num(win, map_tx, col_delta, row_delta));
}

/* tilemap 表项地址 —— 复刻 ROM sub_08003708（UpdateTilemap 的定位子程）：
 *   col = (win[0x1A] + win[0x1B]) & 0xFF
 *   row = (win[0x1C] + win[0x1D]) & 0xFF
 *   addr = tpl->tilemap + ((row*32 + col) << 1)
 * lower 表项在 addr + 0x40（= 下一行同列）。
 * tx 可覆盖列游标：原生 FontSub 返回后 win[0x1B] 已被推进，
 * 故必须在调用【前】取好 tx 与地址。 */
static uint16_t *tilemap_entry_at(TextPrinter *win, uint8_t tx)
{
    uint8_t *tpl = win_template(win);
    uint32_t tp  = win_u32(tpl, TPL_TILEMAP);
    unsigned col, row;

    if (tp == 0u)
        return 0;                       /* 缓冲区直绘窗口无 tilemap */
    col = (unsigned)((unsigned)win_u8(win, WIN_CURSOR_X) + (unsigned)tx) & 0xFFu;
    row = (unsigned)((unsigned)win_u8(win, WIN_CURSOR_Y)
                     + (unsigned)win_u8(win, WIN_CURSOR_TILE_Y)) & 0xFFu;
    return (uint16_t *)(uintptr_t)(tp + ((row * 32u + col) << 1));
}

static void chs_map_at(TextPrinter *win, uint8_t tx, uint16_t abs_u, uint16_t abs_l)
{
    if ((win_u8(win, WIN_TEXTMODE) & 7u) == 2u)
        return;                                      /* 缓冲区直绘，无 tilemap */
    win_set_u8(win, WIN_CURSOR_TILE_X, tx);
    UpdateTilemap_PreserveCursorX(win, abs_u, abs_l);
}

static void chs_off_add(TextPrinter *win, unsigned d)
{
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;

    if (tm == 2u || tm == 3u)
        return;
    win_set_u16(win, WIN_TILE_OFFSET,
                (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + d));
}

/* 非中文移位写入：src 已烘焙成 4bpp，只做移位+spill，不二次烘焙。in-place。 */
static void chs_refpr_nobake(TextPrinter *win, const uint8_t *src32,
                             uint8_t *dest, uint8_t *spillTile,
                             unsigned startPixel, unsigned width)
{
    uint32_t bg_word;
    uint32_t keep;
    unsigned left, right, gw_end, r;
    int need_spill;

    if (spillTile == 0 && startPixel == 0u && width >= 8u) {
        copy_tile32(dest, src32);
        return;
    }
    if (width > 8u)
        width = 8u;

    gw_end     = startPixel + width;
    need_spill = (spillTile != 0) && (gw_end > 8u);
    bg_word    = 0x11111111u * ((uint32_t)win_u8(win, WIN_COLOR_D) & 0x0Fu);
    left       = startPixel * 4u;
    right      = 32u - left;
    keep       = (startPixel == 0u) ? 0u : ((1u << left) - 1u);

    {
        uint32_t *d  = (uint32_t *)dest;
        uint32_t *sp = (uint32_t *)spillTile;

        for (r = 0; r < 8u; r++) {
            uint32_t val = ((const uint32_t *)src32)[r];

            if (width < 8u)
                val &= (1u << (width * 4u)) - 1u;
            d[r] = (d[r] & keep) | (val << left);
            if (gw_end < 8u)
                d[r] |= bg_word << (gw_end * 4u);
            if (need_spill)
                sp[r] = (val >> right) | (bg_word << ((gw_end - 8u) * 4u));
        }
    }
}

/* ---- 12px 两趟 spill 绘制（中文，bake=1；非中文整字走 native_via_phase）---*/
static void chs_core_ex(TextPrinter *win, const struct ChsGlyphTiles *tiles,
                        unsigned glyphWidth, int bake)
{
    unsigned startPixel, pass2_w, px;
    uint8_t base_tx, map_tx, btx0;
    uint16_t px_in;
    int slot;
    uint16_t abs_u, abs_l, su = 0, sl = 0;
    uint8_t *du, *dl, *du_sp = 0, *dl_sp = 0;
    int spilled;
    struct GlyphTileInfo info;

    if (glyphWidth < 8u)
        glyphWidth = 8u;
    if (glyphWidth > 12u)
        glyphWidth = 12u;
    pass2_w = glyphWidth - 8u;
    spilled = 0;

    slot = phase_bind(win, &px_in, &btx0);
    px = px_in;
    base_tx = btx0;

    startPixel = px & 7u;
    map_tx = (uint8_t)(base_tx + (px >> 3));
    info.startPixel = (uint8_t)startPixel;

    /* ---- pass1：tl / bl，宽 8 ---- */
    info.width = 8u;
    abs_u = chs_tile_num(win, map_tx, 0, 0);
    abs_l = chs_tile_num(win, map_tx, 0, 1);
    du    = chs_tile_ptr(win, map_tx, 0, 0);
    dl    = chs_tile_ptr(win, map_tx, 0, 1);
    if (startPixel + 8u > 8u) {
        su    = chs_tile_num(win, map_tx, 1, 0);
        sl    = chs_tile_num(win, map_tx, 1, 1);
        du_sp = chs_tile_ptr(win, map_tx, 1, 0);
        dl_sp = chs_tile_ptr(win, map_tx, 1, 1);
        spilled = 1;
    }
    if (bake) {
        DrawGlyphTile_refpr(win, &info, tiles->tl, du, du_sp);
        DrawGlyphTile_refpr(win, &info, tiles->bl, dl, dl_sp);
    } else {
        chs_refpr_nobake(win, tiles->tl, du, du_sp, startPixel, info.width);
        chs_refpr_nobake(win, tiles->bl, dl, dl_sp, startPixel, info.width);
    }
    chs_map_at(win, map_tx, abs_u, abs_l);
    chs_off_add(win, 2u);
    px += 8u;

    if (pass2_w == 0u) {
        if (spilled)
            chs_map_at(win, (uint8_t)(map_tx + 1u), su, sl);
        phase_px_store(win, slot, (uint16_t)px);
        chs_sync_tilex(win, slot, px, glyphWidth);
        return;
    }

    /* ---- pass2：tr / br，宽 4 ---- */
    map_tx = (uint8_t)(base_tx + (px >> 3));
    info.width = (uint8_t)pass2_w;
    abs_u = chs_tile_num(win, map_tx, 0, 0);
    abs_l = chs_tile_num(win, map_tx, 0, 1);
    du    = chs_tile_ptr(win, map_tx, 0, 0);
    dl    = chs_tile_ptr(win, map_tx, 0, 1);
    du_sp = 0;
    dl_sp = 0;
    if (startPixel + pass2_w > 8u) {
        du_sp = chs_tile_ptr(win, map_tx, 1, 0);
        dl_sp = chs_tile_ptr(win, map_tx, 1, 1);
    }
    if (bake) {
        DrawGlyphTile_refpr(win, &info, tiles->tr, du, du_sp);
        DrawGlyphTile_refpr(win, &info, tiles->br, dl, dl_sp);
    }
    chs_map_at(win, map_tx, abs_u, abs_l);
    /* ⚠ pass2 之后的推进量**取决于相位**，不能恒定 +2（v7 的"修复"是错的）。
     *
     * 正解：off 必须恒等于 `sub_start + 2*(px >> 3)`（px = 本趟起始像素）。
     *   12px 步进下相邻字**共享一个 tile**——字 N 的右 4px 与字 N+1 的左 4px
     *   同处一格（文档 FONT_12PX_DRAW.md：「右缘填 D，不碰左缘」即为此）。
     *   推导（px_N 为第 N 字起点，sp = px_N & 7）：
     *     pass1 off = sub + 2*(px_N >> 3)
     *     pass2 off = sub + 2*((px_N+8) >> 3) = pass1 + 2      （两相位都成立）
     *     下一字 pass1 = sub + 2*((px_N+12) >> 3)
     *       sp==0 → +2  ； sp==4 → +4
     *   → pass2 之后应推进 **sp==0 ? 0 : 2**。
     *
     * 恒定 +2 的后果（2026-08-29 截图实证）：off 比正确值大 2 并持续累积 →
     * 字 N+1 的 pass1 落到一格**新** tile，其左 4px 从未被写过（应放上一字
     * 的右 4px）→ 屏幕上出现**背景透明的空格子**，且 4 字标签多用 4 个 tile。 */
    chs_off_add(win, (startPixel == 0u) ? 0u : 2u);

    px += pass2_w;
    phase_px_store(win, slot, (uint16_t)px);
    chs_sync_tilex(win, slot, px, glyphWidth);
}

static void chs_advance(TextPrinter *win, unsigned adv)
{
    uint16_t px;
    uint8_t  btx;
    int      slot = phase_bind(win, &px, &btx);

    px = (uint16_t)(px + adv);
    phase_px_store(win, slot, px);
    chs_sync_tilex(win, slot, px, adv);
}

/* ---- tm2 缓冲区直绘（无 spill、无 tilemap；结构照抄旧 DrawGlyphTiles_buffer） */
static void chs_buffer(TextPrinter *win, const struct ChsGlyphTiles *tiles, unsigned glyphWidth)
{
    uint32_t dst_u = win_u32(win, WIN_TILE_DATA);
    uint8_t *dst;
    struct GlyphTileInfo info;
    unsigned cols, i;

    if (dst_u == 0u)
        return;
    dst = (uint8_t *)(uintptr_t)dst_u;

    if (glyphWidth < 8u)
        glyphWidth = 8u;
    if (glyphWidth > 12u)
        glyphWidth = 12u;
    cols = (glyphWidth <= 8u) ? 1u : 2u;
    info.startPixel = 0;

    for (i = 0; i < cols; i++) {
        const uint8_t *src_u = (i == 0u) ? tiles->tl : tiles->tr;
        const uint8_t *src_l = (i == 0u) ? tiles->bl : tiles->br;

        info.width = (i == 0u) ? 8u : (uint8_t)(glyphWidth - 8u);
        if (info.width == 0u)
            break;
        if (info.width > 8u)
            info.width = 8u;
        DrawGlyphTile_refpr(win, &info, src_u, dst, 0);
        DrawGlyphTile_refpr(win, &info, src_l, dst + 0x20, 0);
        dst += 0x40;
    }
    win_set_u32(win, WIN_TILE_DATA, (uint32_t)(uintptr_t)dst);
}

/* ---- tm1 落址：查窗口配置表，查不到就回退线性式（不猜场景） ---------------
 * 布局数值全部在 src/text/text_scene.c，本文件只做"查表 + 求值"。 */

static const struct Tm1WinCfg *tm1_cfg(TextPrinter *win)
{
    return scene_tm1_lookup((uint32_t)(uintptr_t)win_template(win));
}

/* 行基址。已登记窗口走配置表；未登记回退 win[0x16]（等价 tm0 的线性式）。 */
static uint16_t tm1_row_base(TextPrinter *win)
{
    const struct Tm1WinCfg *cfg = tm1_cfg(win);

    if (!cfg)
        return win_u16(win, WIN_TILE_BASE);
    return scene_tm1_row_base(cfg, win_u8(win, WIN_CURSOR_Y));
}

/* 行内子区起点 + 容量。
 * ⚠ span 必须 ≥ 该子区会走到的最大 off，否则 off 回卷覆盖本字前半
 *   （v8 的槽跨度 2 就是这么炸的）。
 *   12px 每字 off+4（4 字 → 需 16）；8px 每字 off+2（3 字 → 需 6）。
 * 未登记窗口返回 span=0 表示"不做复位"。 */
static uint16_t tm1_sub_off(TextPrinter *win, uint16_t *span)
{
    const struct Tm1WinCfg *cfg = tm1_cfg(win);

    if (!cfg) {
        *span = 0u;
        return 0u;
    }
    return scene_tm1_sub_off(cfg, win_u8(win, WIN_CURSOR_X), span);
}

/* ---- 中文入口：字库选择 + 解压 + 分派 -------------------------------------*/
static void chs_blit(TextPrinter *win, uint32_t glyph)
{
    struct TextGlyph g;
    struct ChsGlyphTiles t;
    uint8_t tm = win_u8(win, WIN_TEXTMODE) & 7u;
    uint8_t fn = win_u8(win, WIN_FONTNUM_REAL);

    if (fn > 6u)
        fn = 3u;
    /* tm2 战斗窗口昵称/血条：原生 8px 槽，须用 FontChsSmall；
     * 队伍名等其余小字体场景同理。其余一律常规字体（12px）。 */
    if (tm == 2u)
        fn = 4u;
    /* tm1 混排：标签列 12px、候选列 8px，由配置表的 col_label_max 划分。
     * 8px 的原因见文件头 v9 段账目——12px 时 3 字候选要 12 tile，加标签 16 后
     * 48 tile/行；8px 下只需 6 tile → 16+6+4+6=28 tile/行，才装得进可用区间。
     * 未登记窗口没有这个划分 → 一律 12px，且不做子区复位。 */
    if (tm == 1u) {
        const struct Tm1WinCfg *cfg = tm1_cfg(win);

        /* cand_font=0 表示候选列也用 12px（GRID 因此可以全 12px） */
        if (cfg && cfg->cand_font
            && win_u8(win, WIN_CURSOR_X) >= cfg->col_label_max)
            fn = cfg->cand_font;
    }

    /* tm1：把 win[0x18] 恢复为「行内偏移」——标签 / 候选槽各有起点。
     * 行基址由 chs_tile_num 加 tm1_row_base()。新会话（原生重置为较大值）
     * 或越出本子区 → 复位；同会话内推进则不动（幂等：重绘总从子区头开始）。
     * span==0 表示未登记窗口 → 不复位（保持 win[0x18] 原样推进）。 */
    if (tm == 1u) {
        uint16_t off = win_u16(win, WIN_TILE_OFFSET);
        uint16_t start, span;

        start = tm1_sub_off(win, &span);
        if (span != 0u && (off < start || off >= (uint16_t)(start + span)))
            win_set_u16(win, WIN_TILE_OFFSET, start);
    }

    DecompressGlyph_Chinese(&g, (uint16_t)(glyph & 0xFFFFu), fn);
    t.glyph_id = (uint16_t)(0x8000u | (glyph & 0x1FFFu));
    t.tl = (uint8_t *)&g.gfxBufferTop[0];
    t.tr = (uint8_t *)&g.gfxBufferTop[8];
    t.bl = (uint8_t *)&g.gfxBufferBottom[0];
    t.br = (uint8_t *)&g.gfxBufferBottom[8];

    if (tm == 2u)
        chs_buffer(win, &t, g.width);
    else
        chs_core_ex(win, &t, g.width, 1);
}

/* 非中文（tm0/tm3）必须【也走相位】：旧实现里所有字符都过 DrawGlyphTiles，
 * startPixel 移位对它们同样生效。若直接整 tile 交给原生原语写，会覆盖相邻
 * 汉字的右半（表现为数字/假名被汉字吞掉、位置乱掉，见 28.PNG "たかさ 约.花"）。
 * 这里先用原生原语画到临时缓冲，再按 chs_core_ex(bake=0) 移位落 VRAM。 */
static void native_via_phase(TextPrinter *win, uint32_t glyph)
{
    uint8_t buf[32];              /* 烘焙缓冲，仅 1 tile（与 refpr 的 temp_words 同级） */
    uint8_t *up_src, *lo_src;
    unsigned px, startPixel, map_tx;
    uint16_t abs_u, abs_l, su = 0, sl = 0;
    uint8_t *du, *dl, *du_sp = 0, *dl_sp = 0;
    uint8_t font = win_u8(win, WIN_FONTNUM_REAL);
    (void)su; (void)sl;
    uint8_t fg_ov = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    uint8_t c = (fg_ov != 0u) ? fg_ov : win_u8(win, WIN_COLOR_C);
    uint8_t d = win_u8(win, WIN_COLOR_D);
    uint8_t e = win_u8(win, WIN_COLOR_E);
    uint16_t px16;
    uint8_t btx0;
    int slot = phase_bind(win, &px16, &btx0);

    px = px16;
    startPixel = px & 7u;
    map_tx = (uint8_t)(btx0 + (px >> 3));

    abs_u = chs_tile_num(win, map_tx, 0, 0);
    abs_l = chs_tile_num(win, map_tx, 0, 1);
    du    = chs_tile_ptr(win, map_tx, 0, 0);
    dl    = chs_tile_ptr(win, map_tx, 0, 1);
    if (startPixel + 8u > 8u) {
        su    = chs_tile_num(win, map_tx, 1, 0);
        sl    = chs_tile_num(win, map_tx, 1, 1);
        du_sp = chs_tile_ptr(win, map_tx, 1, 0);
        dl_sp = chs_tile_ptr(win, map_tx, 1, 1);
    }

    GetGlyphTilePointers_Origin(font, (uint16_t)(glyph & 0xFFFFu), &up_src, &lo_src);
    /* upper：烘焙到 32B 栈缓冲 → 相位移位落 VRAM */
    if (FontIsShadowed(font))
        CopyGlyph2bppTo4bpp_Origin(up_src, buf, c, e, d);
    else
        CopyGlyph1bppTo4bpp_Origin(up_src, buf, c, d);
    chs_refpr_nobake(win, buf, du, du_sp, startPixel, 8u);
    /* lower */
    if (FontIsShadowed(font))
        CopyGlyph2bppTo4bpp_Origin(lo_src, buf, c, e, d);
    else
        CopyGlyph1bppTo4bpp_Origin(lo_src, buf, c, d);
    chs_refpr_nobake(win, buf, dl, dl_sp, startPixel, 8u);

    chs_map_at(win, map_tx, abs_u, abs_l);
    chs_off_add(win, 2u);
    px16 = (uint16_t)(px + 8u);
    phase_px_store(win, slot, px16);
    chs_sync_tilex(win, slot, px16, 8u);
}

/* ---- tm 桥接：非中文交官方原语，中文交 chs_blit ---------------------------*/

static void br_tm0(TextPrinter *win, uint32_t glyph, int is_chs)
{
    if (is_chs) { chs_blit(win, glyph); return; }

    native_via_phase(win, glyph);   /* 落址/相位由 chs_core_ex 统一处理 */
}

static void br_tm1(TextPrinter *win, uint32_t glyph, int is_chs)
{
    const struct Tm1WinCfg *cfg;

    if (is_chs) { chs_blit(win, glyph); return; }

    cfg = tm1_cfg(win);
    if (cfg != 0 && cfg->mirror_n != 0u) {
        /* 原生字符只写 tilemap 表项（值 = 字库 tile），不写 VRAM。
         * 若那个 tile 正被中文占着，就把表项改指到预渲染期备好的镜像。
         * ⚠ 地址必须在 FontSub_Origin【之前】算：它会推进 win[0x1B]。 */
        uint8_t  tx = win_u8(win, WIN_CURSOR_TILE_X);
        uint16_t *e = tilemap_entry_at(win, tx);

        FontSub_Origin(win, glyph);
        if (e != 0) {
            uint16_t v  = (uint16_t)(*e & 0x0FFFu);
            uint16_t mv = scene_tm1_mirror_of(cfg, v);

            if (mv != 0u) {
                *e = (uint16_t)((*e & 0xF000u) | mv);   /* 保留 palette */
                e[32] = (uint16_t)((e[32] & 0xF000u) | (mv + 1u));  /* lower: +0x40B */
            }
        }
    } else {
        FontSub_Origin(win, glyph);   /* ROM 预渲染查表，零 VRAM 写入 */
    }
    chs_advance(win, 8u);
}

static void br_tm2(TextPrinter *win, uint32_t glyph, int is_chs)
{
    if (is_chs) { chs_blit(win, glyph); return; }

    uint32_t p = win_u32(win, WIN_TILE_DATA);

    draw_native(win, glyph, (uint8_t *)(uintptr_t)p);
    win_set_u32(win, WIN_TILE_DATA, p + 0x40u);
}

static void br_tm3(TextPrinter *win, uint32_t glyph, int is_chs)
{
    if (is_chs) { chs_blit(win, glyph); return; }

    native_via_phase(win, glyph);   /* 落址/相位由 chs_core_ex 统一处理 */
}

/* ============================================================================
 * 统一入口：按 textMode 分派
 * ==========================================================================*/
void Chs_FontFunc_hook(TextPrinter *win, uint32_t glyph, int is_chs)
{
    switch (win_u8(win, WIN_TEXTMODE) & 7u) {
    case 1u: br_tm1(win, glyph, is_chs); break;
    case 2u: br_tm2(win, glyph, is_chs); break;
    case 3u: br_tm3(win, glyph, is_chs); break;
    default: br_tm0(win, glyph, is_chs); break;
    }
}

/* ---- 原函数调用（新命名规范：XXX_Origin）---------------------------------*/

static void font_func_call(TextPrinter *win, uint32_t glyph, unsigned idx)
{
    typedef void (*fn_t)(void *, uint32_t);
    const volatile uint32_t *tbl = (const volatile uint32_t *)ADDR_FONT_FUNC_TABLE;

    ((fn_t)tbl[idx])(win, glyph);     /* 表项已含 Thumb 位，勿再 |1 */
}

void FontFunc_Tm0_Origin(TextPrinter *win, uint32_t glyph) { font_func_call(win, glyph, 0u); }
void FontFunc_Tm1_Origin(TextPrinter *win, uint32_t glyph) { font_func_call(win, glyph, 1u); }
void FontFunc_Tm2_Origin(TextPrinter *win, uint32_t glyph) { font_func_call(win, glyph, 2u); }
void FontFunc_Tm3_Origin(TextPrinter *win, uint32_t glyph) { font_func_call(win, glyph, 3u); }

/* FontSubTable[fontNum] @0x081BB3BC：tm1 第二级（ROM 预渲染查表） */
void FontSub_Origin(TextPrinter *win, uint32_t glyph)
{
    typedef void (*fn_t)(void *, uint32_t);
    const volatile uint32_t *tbl = (const volatile uint32_t *)ADDR_FONT_SUBTABLE;
    uint32_t fn = win_u8(win, WIN_FONTNUM_REAL);

    if (fn >= 7u)
        fn = 0u;
    ((fn_t)tbl[fn])(win, glyph);
}

/* ============================================================================
 * P24「削字库」—— tm1 字库占满 charblock 的根治
 *
 * 原生 void InitWindowTileData(tpl, u16 startOffset, u8 glyph)
 *   → 写 tileData + (startOffset + glyph*2) 两格（upper/lower），
 *     256 次铺满 tile [1,513)。中文字形要落 VRAM 就只能跟它抢。
 *
 * 做法：落址 [tile0, tile0+2) 与中文区 [TM1_CHS_LO, TM1_CHS_HI) 相交的
 *   字形**不渲染**，把那 202 个 tile 让给中文（= 跳过 glyph 60..160）。
 *   校验：原生实际引用到的 22 个字形 tile 全在 <121 或 >=323，无冲突。
 *
 * ⚠ 门控：gdb 实证 256/256 次调用的 r0 都是 0x081BB874（设置窗口），
 *   其余 tm1 窗口走 LZ77 场景字库（README §F7）。这里仍按 tpl 门控，
 *   非该窗口一律照常渲染 —— 保证对未采集场景零回归。
 * ==========================================================================*/
void InitWindowTileData_Hook(void *tpl, uint32_t startOffset, uint32_t glyph)
{
    /* ⛔ 跳过逻辑已于 2026-08-29 实测后停用，见上方 v9 段说明。
     * 保留钩子（直通）以便日后需要时恢复；勿删——入口桩已占用 P24。 */
    InitWindowTileData_Origin(tpl, startOffset, glyph);

    /* ---- 字形镜像：把被中文压住的字形复制一份到空闲处 ------------------
     * 时机是这里而非"用到时"的唯一原因：中文一写入就把原位置覆盖了，
     * 之后再拷只会拷到中文碎片。此刻（预渲染刚写完、文本尚未打印）
     * 是内容干净且**整体早于任何中文写入**的唯一窗口
     * （gdb 实证：预渲染行 698–4013 < 首个文本打印 4026）。
     * 逐 glyph 调用 ⇒ 每个字形只会命中一次，天然无状态、无需失效逻辑。 */
    {
        const struct Tm1WinCfg *cfg =
            scene_tm1_lookup((uint32_t)(uintptr_t)tpl);

        if (cfg && cfg->mirror_n != 0u) {
            /* tile0 恒为字形起点（startOffset + glyph*2），故用严格匹配 */
            uint16_t dst = scene_tm1_mirror_src(cfg,
                               (uint16_t)(startOffset + glyph * 2u));

            if (dst != 0u) {
                uint8_t *td = (uint8_t *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);

                if (td != 0) {
                    const uint32_t *s = (const uint32_t *)(td
                                        + (startOffset + glyph * 2u) * 32u);
                    uint32_t *d = (uint32_t *)(td + (uint32_t)dst * 32u);
                    unsigned k;

                    /* 一个字形 = 上下 2 个 tile × 32B = 64B = 16 个 u32 */
                    for (k = 0u; k < 16u; k++)
                        d[k] = s[k];
                }
            }
        }
    }
}
