/* ============================================================================
 * scene_cfg.c — v6 场景落址配置（纯数据，零方法；2026-09-04 拆分）
 *
 * 只放 const 配置表，不含任何函数实现。结构定义见 scene_cfg.h；
 * 查询访问器与渲染实现在 PrintNextChar_hook.c。
 * 新增窗口只需在此追加一条 kV6Scenes 条目。
 *
 * 设置菜单（模板 0x081BB874）：左标签列 16px、右候选列 12px（用户拍板 2026-09-04）。
 * 标签列与候选列**分用两条独立行带**（字号不同 ⇒ tile 步进不同，不能共用一条）：
 *   标签列  → kOptLabelRowBase[7]（16px 整格，每字 4 tile，最长 4 字 = 16 tile/行）
 *   候选列  → kOptRowBase[7]（12px 相位共享，最长 3 字 = 10 tile，独占 32-tile 行带）
 * 行带基址避开引用字形（kOptGlyphAvoid）与高段 [0x1C8,0x1FF]（场景映射/UI 图标）。
 * 相位隔离：标签 16px 与候选 12px 分属不同 zone（font_px 不同），v6_same_zone
 *   判定异区 ⇒ InitTextPrinter 时相位正确复位，不互相续接。
 * 候选列 off 分区（同区共享行带、异区互不覆盖）：
 *   候选A  off=0   占 [0,10)   （cx<19：慢/看/替换/单声道/普通/类型，最宽 3 字）
 *   候选B  off=10  占 [10,20)  （19≤cx<22：普通/不看/打到底/立体声）
 *   候选C  off=20  占 [20,30)  （cx≥22：快/打到底/L/7）
 * 标签行带（7 段 × 16 tile，选自 cb=2 空闲缝，避 kOptGlyphAvoid 与候选行带）：
 *   r1 0x003 对话速度 | r2 0x053 战斗动画 | r3 0x079 对战规则 | r4 0x0ED 声音
 *   r5 0x15F 按键模式 | r6 0x173 窗口 | r7 0x19B 关闭 */
#include "scene_cfg.h"

/* ---- 设置菜单：左标签列行带（16px 整格，7 行 × 16 tile）---- */
static const uint16_t kOptLabelRowBase[7] = {
    0x003u, 0x053u, 0x079u, 0x0EDu, 0x15Fu, 0x173u, 0x19Bu,
};

/* ---- 设置菜单：右候选列行带（12px 相位共享，7 行 × 32 tile）---- */
static const uint16_t kOptRowBase[7] = {
    0x033u, 0x08Du, 0x0ADu, 0x0CDu, 0x101u, 0x121u, 0x121u,
};

/* ---- 设置菜单：curX 分区（16px key / 12px value）---- */
static const struct V6Zone kOptZones[] = {
    /* 标签列（key）：16px 整格，独立行带 kOptLabelRowBase，off=0。 */
    { .cx_hi = 8u,    .font_px = 16u, .off = 0u,  .row_tab = kOptLabelRowBase },
    /* 候选列（value）：同一行多个候选是独立打印会话，按 curX 分区 + 固定 off 落址。 */
    { .cx_hi = 19u,   .font_px = 12u, .off = 0u,  .row_tab = 0 },
    { .cx_hi = 22u,   .font_px = 12u, .off = 10u, .row_tab = 0 },
    { .cx_hi = 0xFFu, .font_px = 12u, .off = 20u, .row_tab = 0 },
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

/* ---- 场景规则表（一窗一条）---- */
const struct V6SceneRule kV6Scenes[] = {
    { .tpl = 0x081BB874u, .row_y0 = 3u, .row_shift = 1u,
      .row_tab = kOptRowBase, .row_n = 7u,
      .title_base = 0x183u,          /* 标题「设置」2 字 16px = 8 tile，独立带避开标签/候选/引用字形 */
      .zones = kOptZones, .zone_n = 4u,
      .avoid = kOptGlyphAvoid, .avoid_n = 26u },
};

const unsigned kV6SceneN = (unsigned)(sizeof(kV6Scenes) / sizeof(kV6Scenes[0]));
