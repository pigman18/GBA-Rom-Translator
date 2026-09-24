#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_v21_canvas.py — v21「位置定号 + 窗口私有画布」剩余改动（一次性）

覆盖：
  1. hook/src/text/tile_alloc.c     加 `#include "text.h"`（win_u8/win_template）
  2. hook/include/game.h            v8/v9/v10 宏块 → v21 宏块（含 TPL_TEXTMODE）
  3. hook/src/text/PrintNextChar_hook.c
        · 删 chs_cell_slot / CHS_TM_ROW_STRIDE
        · chs_claim_tile → 纯位置函数
        · print_glyph_px 的 t0/t1 段合并
        · 删 v8_phase_set_last_tile
  4. hook/src/text/entry.s          写回 r0（新 tile_base）到保存的 r2 槽
  5. hook/main.asm                  加 patches/textmode_tm1_to_tm0.asm
  6. hook/build.bat + build_sh_equiv.sh   加 chs_canvas.c 编译与链接

每处替换都有 assert（铁律 9：Edit 有坑 ⇒ 批量改动用一次性 python）。
"""
import os
import sys

ROOT = r"C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\hook"
CHANGES = 0


def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    crlf = "\r\n" in raw
    return raw.replace("\r\n", "\n"), crlf


def write_text(path, text, crlf):
    out = text.replace("\n", "\r\n") if crlf else text
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(out)


def patch(path, old, new, tag, expect=1):
    global CHANGES
    full = os.path.join(ROOT, path)
    text, crlf = read_text(full)
    n = text.count(old)
    if n != expect:
        print("❌ [%s] 期望 %d 处匹配，实得 %d 处 —— 中止" % (tag, expect, n))
        sys.exit(2)
    write_text(full, text.replace(old, new), crlf)
    CHANGES += 1
    print("✅ [%s] %d 处" % (tag, n))


def patch_span(path, start_marker, end_marker, new, tag):
    """删除 [start_marker, end_marker] 闭区间并替换为 new。"""
    global CHANGES
    full = os.path.join(ROOT, path)
    text, crlf = read_text(full)
    i = text.find(start_marker)
    if i < 0:
        print("❌ [%s] 找不到起点标记" % tag)
        sys.exit(2)
    j = text.find(end_marker, i)
    if j < 0:
        print("❌ [%s] 找不到终点标记" % tag)
        sys.exit(2)
    j += len(end_marker)
    write_text(full, text[:i] + new + text[j:], crlf)
    CHANGES += 1
    print("✅ [%s] 区间替换（删 %d 字符）" % (tag, j - i))


# =============================================================================
# 1. tile_alloc.c：补 text.h
# =============================================================================
patch("src/text/tile_alloc.c",
      '#include "tile_alloc.h"\n\nuint16_t v8_phase_get',
      '#include "tile_alloc.h"\n#include "text.h"\n\nuint16_t v8_phase_get',
      "tile_alloc.c: include text.h")

# =============================================================================
# 2. game.h：宏块替换
# =============================================================================
GAME_H_BLOCK = """/* ============================================================================
 * v21（2026-09-20）：位置定号 + 窗口私有画布
 *
 * 15-0b 逐指令实证：日版引擎本来就是「位置定号 + 每窗口一块私有基址」——
 *   · `InitTextPrinter(win, text, tile_base, x, y)` → `win[0x16] = tile_base`（u16）
 *   · `UpdateTilemap` 写 `tile | (win[0x0F] << 12)`（**原样写号，不加 charBase 偏移**）
 *     ⇒ tile 号是 0..1023 全局号，地址 = `tpl->tileData + tile*32`；
 *       号空间 = 该窗口 charBase 起 32 KB。
 *   · `InitWindowTileData` 的字形 worker 只对 **textMode == 1** 加载
 *     ⇒ tm0 窗口的画布是纯净的（官方一个字节都不放）。
 *
 * v12 的 `v8_official_end(win) ∈ {535, 279}` 是把 `cap = 512`（待加载**字形个数**，
 * 即 progress 循环上界）误读成「号区间长度」⇒ 从一个不存在的坐标系发号，
 * 正好撞进官方 `{0x28, 0x90, 0xBC}` 三族画布。分配器族（含本区所有旧状态）已删。
 *
 * 静态资产落点实测（scripts/scan_vram_assets.py + scan_vram_cpu_assets.py）：
 *   LZ77 / RL / CpuSet / CpuFastSet 四条 VRAM 写入路径的落点并集（含解压长度）：
 *     [0,384) 空闲 ｜ [384,425) [448,489) [512,873) [896,937) [960,1001) 被占
 *   ⇒ 画布池 = 号 [0, 384)，2 块 × 192，只对 charBase == 0 的窗口启用。
 *
 * 🔴 地址区 0x0203FF48..0x0203FF8F 原属 v8/v9/v10 分配器状态（全部废弃）。
 *    0x0203FFD0 起才是活区（OPT_* / GLYPH_PAGE_CURTAB），**严禁越过**。
 * ==========================================================================*/
#define ADDR_V21_CANVAS       0x0203FF50u  /* 6 × {u32 win;u16 base;u16 pad} = 48B */
#define ADDR_V21_CANVAS_RR    0x0203FF80u  /* u16 块轮转计数 */
#define ADDR_V21_CANVAS_MAGIC 0x0203FF82u  /* u16 冷启动校验 */

/* 模板（tpl）字段：textMode。字号加载 worker @0x080029E0 读的就是它
 * （`ldrb r0,[r0,#9]`），所以 tm1→tm0 必须改**数据**，钩 win[0x0A] 挡不住。 */
#define TPL_TEXTMODE        0x09
"""
patch_span("include/game.h",
           "/* --- 手工追加（非生成区）：v9 队列分配器状态块",
           "#define ADDR_V8_OURS_BM                    0x0203FF70u",
           GAME_H_BLOCK,
           "game.h: v21 宏块")

# =============================================================================
# 3. PrintNextChar_hook.c
# =============================================================================
# 3a. 删 v10 注释 + CHS_TM_ROW_STRIDE + chs_cell_slot
patch_span("src/text/PrintNextChar_hook.c",
           "/* ---- v10「按格子定号」：格子 → tile 的映射就是 tilemap 本身",
           """    *out = r;
    return 1;
}""",
           """/* v21 起「格子 → tile 映射」整体删除。
 * 位置定号下 `tile = TILE_BASE + TILE_OFFSET` 是纯函数，不需要读回 tilemap
 * 猜「这格是不是我们写的」。旧机制（ours 账本 + 竖直对自洽闸门 +
 * v8_official_end 水位）的全部存在理由已消失，见 docs/15-0b_*.md。
 * `chs_lower_delta` 仍在（chs_fill_bg 用「下半 tile 偏移」）。 */
""",
           "PrintNextChar_hook.c: 删 chs_cell_slot")

# 3b. chs_claim_tile → 纯位置函数
patch("src/text/PrintNextChar_hook.c",
      """/* tm0：跟官方线性寻址；tm3：官方网格（窗口自有区）；其余（tm1 共享图集）
 * 走 v8 动态分配（AXVJ tm1 无窗口私有区，反汇编定论 2026-09-08）。
 * 🔴 v10 在共池分支前插一步「按格子复用」：本格已是我们的字形槽 ⇒ 直接返回它。
 *    这是「同格重画零消耗」的全部机制 —— 不领新号 ⇒ 池子不增长 ⇒
 *    领航员反复进出/滚动地图不再越来越空。
 * 🔴 v10.1：闸门换成 `chs_cell_slot` 的竖直对自洽判据（见上），不再只看账本。 */
static uint16_t chs_claim_tile(TextPrinter *win, uint8_t tm, uint8_t font_px,
                               uint8_t glyph_len, unsigned dx)
{
    uint16_t r;

    if (tm == 0u)
        return (uint16_t)(win_u16(win, WIN_TILE_BASE)
                          + win_u16(win, WIN_TILE_OFFSET));
    if (tm == 3u)
        return chs_tm3_grid_tile(win);

    if (chs_cell_slot(win, dx, chs_lower_delta(tm), &r))
        return r;
    return v8_alloc_tile(win, font_px, glyph_len);
}""",
      """/* v21：tile 号 = 位置的**纯函数**，无账本 / 无扫描 / 无分配器。
 *   tm3（官方网格）→ 官方自己的格子公式；
 *   其余（tm0；本补丁把 tm1 全部改成 tm0）→ TILE_BASE + TILE_OFFSET 线性推进。
 * 二者都是「算出来的」，这正是「同格重画零消耗」在结构上的保证。 */
static uint16_t chs_claim_tile(TextPrinter *win, uint8_t tm, uint8_t font_px,
                               uint8_t glyph_len, unsigned dx)
{
    (void)font_px;
    (void)glyph_len;
    (void)dx;

    if (tm == 3u)
        return chs_tm3_grid_tile(win);
    return (uint16_t)(win_u16(win, WIN_TILE_BASE)
                      + win_u16(win, WIN_TILE_OFFSET));
}""",
      "PrintNextChar_hook.c: chs_claim_tile")

# 3c. print_glyph_px 的 t0/t1 段
patch("src/text/PrintNextChar_hook.c",
      """    if (phase == 0u) {
        /* 字形 = 竖直对（t0=上半 8 行、t0+1=下半 8 行），8px/12px 均占 2 tile。
         * 此处不得省成 1：t0+1 未占位会被后续领号回收踩踏。 */
        t0 = chs_claim_tile(win, tm, 12u, 2u, 0u);
        if (t0 == 0u)
            return adv;
    } else {
        t0 = v8_phase_last_tile();
        if (t0 == 0u) {
            /* 相位非 0 却没有可复用的尾列（相位残留/跨块边界）⇒ 退回领新对。
             * **绝不**让 t0 保持 0：tile 0 = charBase 首格，写它是不可逆的破坏
             * （像素进官方格 + 表项指向 tile 0）。 */
            t0 = chs_claim_tile(win, tm, 12u, 2u, 0u);
            if (t0 == 0u)
                return adv;
        }
    }
    /* tm0 线性：下一列 = t0+2；tm3 网格：下一列 = t0+1；v8 则再 alloc 一对 */
    if (w1 != 0u) {
        if (tm == 0u)
            t1 = (uint16_t)(t0 + 2u);
        else if (tm == 3u)
            t1 = (uint16_t)(t0 + 1u);
        else {
            /* 🔴 v10：右邻格必须在推进 CURSOR_TILE_X 之前读（见 chs_cell_slot 注释）。
             * 竖直对自洽 ⇒ 复用；否则领新号（下方 UpdateTilemap 会把这格改指到
             * t1，天然完成「格子 → tile」登记）。 */
            t1 = chs_claim_tile(win, tm, 12u, 2u, 1u);
            /* 左右半格不得撞车：右邻格若给出与左半同一对（t0 / t0+dlow），
             * 两半会叠进同一个 tile ⇒ 字形自毁。改领新号。 */
            if (t1 == t0 || t1 == (uint16_t)(t0 + dlow))
                t1 = v8_alloc_tile(win, 12u, 2u);
            if (t1 == 0u) {
                /* 尾列领不到（v8 队列耗尽）⇒ **放弃右半**，绝不退化成写 tile 0。
                 * tile 0 = charBase 首格（图集/空白槽）：写它一箭双雕地坏 ——
                 *   ① 该字的右半像素落进官方格 ⇒ 破坏别人的字形；
                 *   ② 紧接着 UpdateTilemap 把 **tile 0** 写进本格表项 ⇒ 该格
                 *      显示成空白/官方首格内容。
                 * 实机表现就是「字只剩半个」。宁缺不砸：本字只留左半。 */
                w1 = 0u;
            }
        }
    } else {
        t1 = 0u;
    }""",
      """    /* v21 位置定号：`t0` 恒为「当前列」= TILE_BASE + TILE_OFFSET。
     *   · phase == 0 → 本字的左半列（新列起点）；
     *   · phase != 0 → **正是上一字的尾列**（TILE_OFFSET 只在 chs_emit 末尾
     *     推进一次，故两种相位同式）。
     * ⇒ 不需要「全局尾列单例」，也不需要右邻格复用闸门 / 领号器。 */
    t0 = chs_claim_tile(win, tm, 12u, 2u, 0u);
    if (t0 == 0u)
        return adv;

    /* 下一列：竖直对（上/下 2 号）⇒ +2；tm3 官方网格的相邻列只差 1。 */
    t1 = (w1 != 0u) ? (uint16_t)(t0 + ((tm == 3u) ? 1u : 2u)) : 0u;""",
      "PrintNextChar_hook.c: t0/t1")

# 3d. 删 v8_phase_set_last_tile
patch("src/text/PrintNextChar_hook.c",
      """    v8_phase_advance((uint16_t)advance);
    v8_phase_set_last_tile((w1 != 0u) ? t1 : t0);
    return adv;""",
      """    v8_phase_advance((uint16_t)advance);
    return adv;""",
      "PrintNextChar_hook.c: 删 last_tile")

# 3e. 头注释更新
patch("src/text/PrintNextChar_hook.c",
      """ *        tm0     官方线性 TILE_BASE+TILE_OFFSET + UTM（不同 BASE 区互不冲 VRAM）
 *        tm1     v8_alloc + UTM，并 TILE_OFFSET += adv*2
 *        tm3     v8_alloc + UTM，不推 TILE_OFFSET（网格只推 cursorTileX）
 *   tm1 是分配器的主因（预渲染窗无自写 VRAM）；tm3 中文叠字领号避 atlas。
 *   tm0 不走 v8_alloc：战斗四格(BASE≈0x90)与「怎么办」(BASE≈0x190) 同 tpl/同 cb，
 *   若共用 0x100 起领号，后一次 Init 会盖掉前一次 VRAM。""",
      """ *        tm0     位置定号：tile = TILE_BASE + TILE_OFFSET，并推进 TILE_OFFSET
 *        tm3     官方网格：tile 按屏幕格算，不推 TILE_OFFSET
 *   v21 起 tm1 已不存在（patches/textmode_tm1_to_tm0.asm 把 36 条模板改成 tm0）。
 *   TILE_BASE 由 InitTextPrinter 钩子按窗口实例分配（chs_canvas），
 *   画布池 = 号 [0,384)，见 include/chs_canvas.h。""",
      "PrintNextChar_hook.c: 头注释")

# =============================================================================
# 4. entry.s：写回 r2
# =============================================================================
patch("src/text/entry.s",
      """    bl      InitTextPrinter_hook_C
    pop     {r0, r1, r2, r3}""",
      """    bl      InitTextPrinter_hook_C
    str     r0, [sp, #8]           @ 🔴 v21：写回保存的 r2 槽 = 本窗画布基址
    pop     {r0, r1, r2, r3}""",
      "entry.s: 写回 r2")

# =============================================================================
# 5. main.asm：加模板补丁
# =============================================================================
patch("main.asm",
      '.include "./patches/start_menu.asm"',
      '.include "./patches/start_menu.asm"\n.include "./patches/textmode_tm1_to_tm0.asm"',
      "main.asm: include 模板补丁")

# =============================================================================
# 6. build 脚本：加 chs_canvas
# =============================================================================
patch("build_sh_equiv.sh",
      '$CC $CFLAGS  $TEXT/tile_alloc.c                  -o $BUILD/tile_alloc.o',
      '$CC $CFLAGS  $TEXT/tile_alloc.c                  -o $BUILD/tile_alloc.o\n'
      '$CC $CFLAGS  $TEXT/chs_canvas.c                  -o $BUILD/chs_canvas.o',
      "build_sh_equiv.sh: 编译 chs_canvas")
patch("build_sh_equiv.sh",
      '  $BUILD/tile_alloc.o \\',
      '  $BUILD/tile_alloc.o \\\n  $BUILD/chs_canvas.o \\',
      "build_sh_equiv.sh: 链接 chs_canvas")

patch("build.bat",
      "echo === Compiling text\\tile_alloc.c ===\r\n%CC% %CFLAGS% %TEXT%\\tile_alloc.c -o %BUILD%\\tile_alloc.o\r\nif errorlevel 1 exit /b 1",
      "echo === Compiling text\\tile_alloc.c ===\r\n%CC% %CFLAGS% %TEXT%\\tile_alloc.c -o %BUILD%\\tile_alloc.o\r\nif errorlevel 1 exit /b 1\r\n\r\n"
      "echo === Compiling text\\chs_canvas.c ===\r\n%CC% %CFLAGS% %TEXT%\\chs_canvas.c -o %BUILD%\\chs_canvas.o\r\nif errorlevel 1 exit /b 1",
      "build.bat: 编译 chs_canvas")
patch("build.bat",
      "  %BUILD%\\tile_alloc.o ^",
      "  %BUILD%\\tile_alloc.o ^\r\n  %BUILD%\\chs_canvas.o ^",
      "build.bat: 链接 chs_canvas")

print()
print("✅ 全部 %d 处改动完成" % CHANGES)
