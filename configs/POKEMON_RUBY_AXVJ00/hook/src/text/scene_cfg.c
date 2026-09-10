/* ============================================================================
 * scene_cfg.c — 场景字号配置（纯数据 + 查询访问器；2026-09-11 重建）
 *
 * 本文件只决定「每个窗口、每个 curX 起始列分区用哪档字库」，不含任何渲染实现
 * （渲染在 PrintNextChar_hook.c 的 resolve_draw）也不含任何 tile 基址/偏移表。
 *
 * 档位三选一（见 scene_cfg.h）：
 *   V6_FONT_PX_BIG    12 → 1bpp 大库 11×11（步进 12、墨 11）
 *   V6_FONT_PX_SMALL  10 → 1bpp 小库  9×9 （步进 10、墨 9）
 *   V6_FONT_PX_MIDDLE 13 → 1bpp Middle 9×11（步进 10、墨 9）
 *
 * 历史沿革：
 *   2026-09-04 建表（设置菜单 16/12px 分区）
 *   2026-09-07 加宝可导航 / 地图信息粉框 / 训练家信息三条 Middle 规则（实机验收通过）
 *   2026-09-08「两档制换地基」把场景表整体清空（kV6Scenes = {}），三条规则注释停用
 *   2026-09-11 重建：恢复机制 + 按用户要求只启用「领航员」一条
 * ==========================================================================*/
#include "scene_cfg.h"

/* ============================================================================
 * 领航员（PokéNav）字号配置
 *
 * 键：模板 0x081BB49C + win 0x0202E658（用户拍板 2026-09-07）
 *   · 0x0202E658 是**被多模板复用的全局打印器**（同 win 还挂过 0x081BB46C 对话、
 *     0x081BB7E4 粉框），所以必须 tpl+win 双键，只比 win 会误伤对话与设置菜单。
 *   · 该窗 tilemap=0x0600F000(sb30)、charBase=0、tileData=0x06000000、textMode=1、
 *     fontNum=3；存放大段宝可梦/训练家介绍文本，是全作 tile 最紧张、字体最挤的
 *     场景 —— 早年「避让带找空闲带」方案正是在这里不够放而失败。
 *   · 因此走 Middle：**窄身（9px 墨宽 / 10px 步进）但保持全高 11 行**，一行能多排
 *     约 20% 的字且不比 Small 9×9 矮，行距观感与正文一致。
 *
 * ⚠ Middle 的字形源是 `fonts/default/Middle.bdf`（9×11），由 Normal.bdf 经
 *   `src/util/fonts_patcher.py` 分组 OR（11→9 列）派生 —— **不会自动跟随
 *   Normal.bdf 改动**。改了 Normal.bdf 想同步到领航员，需重跑一次：
 *     python src/util/fonts_patcher.py --source fonts/default/Normal.bdf \
 *            --charmap configs/POKEMON_RUBY_AXVJ00/charmap.txt \
 *            --out fonts/default/Middle.bdf \
 *            --src-cols 11 --dst-cols 9 --ink-h 11 --top-pad 2 --no-fallback
 *   再跑打包。Middle 的 ROM 落址 = ADDR_FONT_1BPP_MIDDLE (0x09700000)，步进 13B/字。
 *
 * 分区（curX = WIN_CURSOR_X，字符串起始列，单位 tile）：
 *   cx 0~3 → Middle（正文/介绍）
 *   cx ==4 → Big（固定缩进 32px 的「描述/标签」短串，保持整格观感，用户拍板 09-07）
 *   cx 5+  → Middle
 * ==========================================================================*/
static const struct V6Zone kPokeNavZones[] = {
    { .cx_hi = 4u,    .font_px = V6_FONT_PX_MIDDLE },  /* 起始列 0~3：Middle */
    { .cx_hi = 5u,    .font_px = V6_FONT_PX_BIG },     /* 起始列 ==4：Big（原 16px 整格）*/
    { .cx_hi = 0xFFu, .font_px = V6_FONT_PX_MIDDLE },  /* 起始列 5+：Middle */
};

// 注册人数、对战人数
static const struct V6SceneRule kPokeNavScene1 = {
    .tpl    = 0x081BB7B4u,
    .win    = 0x0202E658u,
    .zones  = kPokeNavZones,
    .zone_n = 3u,
};
// 训练家名
static const struct V6SceneRule kPokeNavScene2 = {
    .tpl    = 0x081BB7E4u,
    .win    = 0x0202E658u,
    .zones  = kPokeNavZones,
    .zone_n = 3u,
};

/* 历史规则（2026-09-07 实机验收通过，2026-09-08 随两档制退役；按需再启用）：
 *
 * 地图信息粉框（tpl 0x081BB7E4，r3=13 居中，如「119号道路」）：整模板 Middle。
 *   游戏按 8px/字算居中起点，Big 11×11 字形会画出窄框造成重叠踩踏花屏
 *   （2026-09-07 实机截图确认）。若粉框再出花屏，把这条加回 kV6Scenes。
 *     { 0x081BB7E4u, 0u, (const struct V6Zone[]){ {0xFFu, V6_FONT_PX_MIDDLE} }, 1u }
 *
 * 训练家信息窗（tpl 0x081BB7B4，UISURVEY 疑似训练家）：整模板 Middle，用户要求瘦体。
 *     { 0x081BB7B4u, 0u, (const struct V6Zone[]){ {0xFFu, V6_FONT_PX_MIDDLE} }, 1u }
 *
 * 设置菜单（tpl 0x081BB874）：左标签列 16px / 右候选 12px —— 新档位下 16 与 12
 *   都并入 Big，等价于整模板 Big，无需再列一条。
 */
const struct V6SceneRule kV6Scenes[] = {
    kPokeNavScene1,
    kPokeNavScene2,
};

const unsigned kV6SceneN = (unsigned)(sizeof(kV6Scenes) / sizeof(kV6Scenes[0]));

/* ============================================================================
 * 查询访问器（渲染层 resolve_draw 消费）
 * ==========================================================================*/
const struct V6SceneRule *v6_scene_lookup(uint32_t tpl, uint32_t win_addr)
{
    const struct V6SceneRule *wild = 0;
    unsigned i;

    for (i = 0; i < kV6SceneN; i++) {
        const struct V6SceneRule *r = &kV6Scenes[i];

        if (r->tpl != tpl)
            continue;
        if (r->win != 0u && r->win == win_addr)
            return r;                       /* tpl+win 精确命中：最高优先，即返回 */
        if (r->win == 0u && wild == 0)
            wild = r;                       /* tpl 通配：留到最后兜底 */
    }
    return wild;
}

static uint8_t v6_zone_font_px(const struct V6SceneRule *r, uint8_t cx)
{
    unsigned i;

    if (r == 0 || r->zones == 0)
        return 0u;
    for (i = 0; i < r->zone_n; i++) {
        if (cx < r->zones[i].cx_hi)
            return r->zones[i].font_px;
    }
    return 0u;
}

uint8_t v6_scene_font(uint32_t tpl, uint32_t win_addr, uint8_t cx)
{
    uint8_t px = v6_zone_font_px(v6_scene_lookup(tpl, win_addr), cx);

    /* 归一化：历史档位 16（整格标签）并入 Big；其余只认三档，未知一律 0（走默认）。 */
    if (px >= 16u)
        return V6_FONT_PX_BIG;
    if (px == V6_FONT_PX_BIG || px == V6_FONT_PX_SMALL || px == V6_FONT_PX_MIDDLE)
        return px;
    return 0u;
}

#if 0
/* ============================================================================
 * 【未编译·存档】v9 避让带「静态登记」通道（2026-09-10 写，从未纳入 build）
 *
 * 该块依赖的 chs_band_add() 在 tile_alloc.c 里**不存在**（v9 队列分配器不做
 * 避让带），scene_cfg.c 也一直没进 build.bat 的编译清单 ⇒ 属未接线的存档代码。
 * 与「只认 VRAM 分配器 / 禁避让带」的路线冲突，故保留原文但置 0，勿直接启用。
 *
 * 原文：
 *  ① s_scene_bands[] —— 静态 tilemap 带（VRAM 屏幕块硬件占用，全局下标）
 *     sb0@0x00000 [0,64) / sb14-15@0x07000 [896,1024) /
 *     sb23-24@0x0B800 [1472,1600) / sb30-31@0x0F000 [1920,2048)
 *  ② chs_scene_reserved_len(font_num) —— tm1 窗自留区 = 图集 cap + 9 + 14
 *     font0/3 → cap 512，其余 256；返回 cap + 22
 * ==========================================================================*/
#endif
