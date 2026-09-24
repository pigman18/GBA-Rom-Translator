# -*- coding: utf-8 -*-
"""apply_v14.py —— v14：框的 tilemap 与文字同权（「领不到号 ⇒ 不画」的 UI 侧）

背景（2026-09-11 逐指令定案）：
  官方把「框」拆成两截 ——
    ① 图形：⑦/⑧ 把 9/14 个 tile 写到 `template->tileData + 32*base`
    ② tilemap：⑨b `TextWindow_DrawStdFrame`(0x0806212C，内层 0x080621D8)
               / `DrawDialogueFrame`(0x080625B8，唯一调用者 = 包装 0x0806266C)
               把 `base + 0..8` 写进 `template->tilemap`
  v12 只门控 ①；**② 从来没接过** ⇒ 池子满、⑤ 返 0、0x03000514 = 0 时
  图形不装（对），但 ② 照样写 `0 + 0..8` —— 而那 8 个 tile 正是第一次进入时
  落在 tile 1..9 的旧框图形（池底 V12_POOL_LO = 1）⇒ 框照画
  ⇒ 用户实测「文字空了、UI 没空」。

本脚本只做两件事：
  · 在 ② 的两个写入点补门控桩（8B「不碰栈」纯跳转）；
  · 跳板在「号 == 0」时把整个框矩形擦成 0 号 tile（= 框消失 + 旧砖失去引用）。

一次性脚本；任一处锚点对不上即整体不写盘。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook")

# ---------------------------------------------------------------- 内容定义

GAME_ADDRS_BLOCK = """\
;
; [v14] 框 **tilemap** —— 「领不到号 ⇒ 不画」的 UI 侧（2026-09-11）
;   官方「框」= 图形（⑦⑧ 装 9/14 个 tile 到 template->tileData + base*32）
;              + tilemap（把 base+0..8 写进 template->tilemap）。
;   v12 只门控了图形那一截；tilemap 这一截**从来没接** ⇒ 池子满、⑤ 返 0、
;   `0x03000514 = 0` 时图形不装（对），但 tilemap 仍被写成 `0 + 0..8` ——
;   而那 8 个 tile 正是**第一次进入时**落在 tile 1..9 的旧框图形
;   （池底 V12_POOL_LO = 1）⇒ 框照画、只是错位一格 ⇒ 实测「文字空、UI 不空」。
;   ⇒ v14 在 tilemap 写入点补门控：号 == 0 就把整块 rect 擦成 0 号 tile。
;
;   ⑨b `TextWindow_DrawStdFrame` @0x0806212C 体内读框号处：
;       8062154: 4906  ldr  r1, =(0x03000514)
;       8062156: 8809  ldrh r1, [r1]
;     ⚠ r3 在该点**已死**（0x0806215E 会 `mov r3, r8` 重设）⇒ 可作跳转寄存器。
;       该点活着的是 r0(tilemap = 0x08062150 `bl 0x0800424C` 的返回值)、
;       r4(right) / r5(bottom) / r6(left) / r8(top)，全在 ⑨b 自己的栈帧里
;       （⑨b prologue push 过 {r4,r5,r6,lr}）⇒ 跳板可自由砸，epilogue 会还原。
;     桩覆盖 0x08062154..0x0806215B；续跑点 0x0806215C（adds r2,r6,#0）。
StdFrameBase_Load                      equ 0x08062154
;   对话框框架包装 `TextWindow_DrawDialogueFrame` @0x0806266C
;     —— writer 0x080625B8 的唯一调用者就是它（0x0806267A），
;        且它**硬编码** rect（left=1 / top=14 / width=22 / height=4）
;        ⇒ 矩形恒为 (1,14)-(28,19)，写死在跳板里是安全的。
;     入口处 r1/r2/r3 还没赋值（0x08062670 才 `movs r1,#4`）⇒ r3 可作跳转寄存器。
;     桩覆盖 0x0806266C..0x08062673；续跑点 0x08062674（movs r1,#1）。
TextWindow_DrawDialogueFrame           equ 0x0806266C
"""

HOOKS_ORIGIN_BLOCK = """\

; =============================================================================
; [v14] 框 **tilemap** 门控 —— 「领不到号 ⇒ 不画」的 UI 侧（2026-09-11）
;
; 为什么必须有这一条：官方「框」= 图形（⑦⑧，v12 已门控）+ tilemap（本桩覆盖的
;   两个写入点，**从来没接**）。池子满 ⇒ ⑤ 返 0 ⇒ 0x03000514 = 0 ⇒ ⑦ 不装图形，
;   但 tilemap 照样被写成 0 + 0..8 ⇒ 框仍然画出来（指向第一次进入时装在 tile 1..9
;   的旧框图形，池底 = 1）⇒ 实测「文字空、UI 不空」。判据「满池 ⇒ 文字与 UI 一起
;   空白」卡住的就是这一步。
;
; 桩型：**8B「不碰栈」纯跳转**（ldr r3 / bx r3 / .pool）——
;   与 ⑤ 的 16B「自带返回」、③ 的原地 6B 都不同，理由：这两个钩点**都在函数体
;   中段**，原体自己的 prologue 已经把 callee-saved 压栈，桩只要是纯跳转就
;   零栈账、零寄存器风险（跳转寄存器 r3 在两点上都已死）。
;   ⚠ 两个桩的 .pool 都紧随其后（imm = 0 可寻址）⇒ 每个桩恰好 8 字节。
; =============================================================================

; ⑨b 内读框号处 —— 覆盖 0x08062154..0x0806215B
;   （ldr r1 / ldrh r1 / str r4,[sp,#0] / str r5,[sp,#4]）
.org StdFrameBase_Load
    ldr  r3, =(V14StdFrame_Hook | 1)
    bx   r3
.pool

; 对话框架包装入口 —— 覆盖 0x0806266C..0x08062673
;   （push {lr} / sub sp,#4 / movs r1,#4 / str r1,[sp,#0]）
.org TextWindow_DrawDialogueFrame
    ldr  r3, =(V14DlgFrame_Hook | 1)
    bx   r3
.pool
"""

ENTRY_BLOCK = """\

@ =============================================================================
@ [v14] 框 **tilemap** 与文字同权 —— 「领不到号 ⇒ 不画」的 UI 侧（2026-09-11）
@ -----------------------------------------------------------------------------
@ 官方「框」= 图形（⑦⑧ 装 9/14 tile 到 template->tileData + base*32）
@            + tilemap（把 base+0..8 写进 template->tilemap）。
@ v12 只门控了图形；**tilemap 这一截从来没接** ⇒ 池子满、⑤ 返 0、
@ 0x03000514 = 0 时图形不装（对），但 tilemap 仍被写成 `0 + 0..8` ——
@ 而那 8 个 tile 正是第一次进入时落在 tile 1..9 的旧框图形（池底 = 1）
@ ⇒ 框照画（错位一格）⇒ 实测「文字空、UI 不空」。
@ 领航员每次进入都重画框（pokenav.c 的 sub_80EF874 case 10），开始菜单不重画
@   —— 这正是两个画面表现不同的原因。
@ 语义 = 「领不到号 ⇒ 把框擦掉」：写 0 号 tile（游戏自己的 erase 约定），
@   同时让旧框砖失去 tilemap 引用 ⇒ 活引用层放行 ⇒ 下一轮可回收。
@
@ 钩点 0x08062154 在 ⑨b 体内 ⇒ ⑨b 的 prologue 已 push {r4,r5,r6,lr}，
@   r4/r5/r6 随便砸（epilogue 会从栈上还原）；桩不碰栈 ⇒ 直接回调用者。
@   现场：r0 = tilemap、r6 = left、r8 = top、r4 = right、r5 = bottom
@         （四者都已被 `lsls/lsrs #24` 收成 u8）。
@ =============================================================================
    .global V14StdFrame_Hook
    .thumb_func
    .type V14StdFrame_Hook, %function
    .extern v14_std_frame_erase_C
V14StdFrame_Hook:
    ldr     r1, =0x03000514            @ 重放 0x08062154（官方框号槽，⑤ 写）
    ldrh    r1, [r1]                   @ 重放 0x08062156 → r1 = 框号
    cmp     r1, #0                     @ 0 = 池子没发出号
    bne     StdFrameTmap_Resume
    push    {r4, r5, r6, lr}           @ 16B：保 lr，且让 SP 保持 8 对齐（C 调用）
    lsls    r4, r4, #16                @ right  → packed bits 16..23
    lsls    r5, r5, #24                @ bottom → packed bits 24..31
    orrs    r4, r5
    mov     r5, r8                     @ top（已 u8）
    lsls    r5, r5, #8                 @        → packed bits 8..15
    orrs    r6, r5                     @ r6 = left | (top << 8)
    orrs    r6, r4                     @ r6 = packed(left, top, right, bottom)
    adds    r1, r6, #0
    bl      v14_std_frame_erase_C      @ (tilemap = r0, packed = r1)
    pop     {r4, r5, r6, lr}
    ldr     r3, =0x08062165            @ ⑨b epilogue（add sp,#8）—— |1 保 Thumb
    bx      r3
StdFrameTmap_Resume:
    str     r4, [sp, #0]               @ 重放 0x08062158
    str     r5, [sp, #4]               @ 重放 0x0806215A
    ldr     r3, =0x0806215D            @ 续跑点 0x0806215C（adds r2,r6,#0）—— |1
    bx      r3
    .size V14StdFrame_Hook, .-V14StdFrame_Hook
    .pool

@ =============================================================================
@ [v14] 对话框框架 —— 同一个门控，另一个 tilemap 写入点
@ -----------------------------------------------------------------------------
@ 钩点 = 包装 `TextWindow_DrawDialogueFrame` @0x0806266C 的入口。
@   ⚠ writer 0x080625B8 的唯一调用者就是它（0x0806267A），且它**硬编码**
@     rect（left=1 / top=14 / width=22 / height=4）⇒ 矩形恒为 (1,14)-(28,19)，
@     right = left + width + 5 = 28，bottom = top + height + 1 = 19
@     （对齐官方 `DrawDialogueFrame` 的循环范围 x∈[0,width+6) y∈[0,height+2)）。
@   ⚠ 框号在**全局** 0x03000516（⑥ 写），不在入参里 ⇒ 由 C 侧折算。
@   入口处 r1/r2/r3 还没赋值（0x08062670 才 `movs r1,#4`）⇒ r3 可作跳转寄存器。
@ 已擦路径 = 桩没碰栈、跳板 push/pop 成对 ⇒ `bx lr` 直接回调用者；
@   包装自己的 push {lr} 与 epilogue 一并跳过，栈完全平衡。
@ =============================================================================
    .global V14DlgFrame_Hook
    .thumb_func
    .type V14DlgFrame_Hook, %function
    .extern v14_dlg_frame_erase_C
V14DlgFrame_Hook:
    ldr     r1, =0x03000516            @ 官方对话框框号槽（⑥ 写）
    ldrh    r1, [r1]
    cmp     r1, #0                     @ 0 = 池子没发出号
    bne     DlgFrameTmap_Resume
    ldr     r1, =0x131C0E01            @ packed：left 1 | top 14<<8 | right 28<<16 | bottom 19<<24
    push    {r4, lr}                   @ 8B：保 lr，且让 SP 保持 8 对齐
    bl      v14_dlg_frame_erase_C      @ (win = r0, packed = r1)
    pop     {r4, lr}
    bx      lr                         @ 直接回调用者
DlgFrameTmap_Resume:
    push    {lr}                       @ 重放 0x0806266C
    sub     sp, #4                     @ 重放 0x0806266E
    mov     r1, #4                     @ 重放 0x08062670（armips 无 movs 助记符）
    str     r1, [sp, #0]               @ 重放 0x08062672
    ldr     r3, =0x08062675            @ 续跑点 0x08062674（movs r1,#1）—— |1
    bx      r3
    .size V14DlgFrame_Hook, .-V14DlgFrame_Hook
    .pool
"""

WIN_ALLOC_H_BLOCK = """
/* ============================================================================
 * v14（2026-09-11）：框的 **tilemap** 也与文字同权 —— 「领不到号 ⇒ 不画」。
 *
 * 官方把「框」拆成两截：
 *   ① 图形：⑦ `TextWindow_LoadStdFrameGraphics` 把 9 个 tile 写到
 *           `win->template->tileData + 32 * sTextWindowBaseTileNum`；⑧ 同理 14 个。
 *   ② tilemap：⑨b `TextWindow_DrawStdFrame`（内层 `DrawStandardFrame`）把
 *           `base + 0..8` 写进 `win->template->tilemap`；对话框版
 *           `DrawDialogueFrame` 写 `sDialogueFrameBaseTileNum + 偏移`。
 * v12 只门控了 ①；**② 从来没接过**（全盘 `.org` 清单里没有这两个写入点）。
 * ⇒ 池子满、⑤ 返 0、`0x03000514 = 0` 时图形不装（对），但 ② 照样写
 *   `0 + 0..8` —— 而那 8 个 tile 正是**第一次进入时**落在 tile 1..9 的旧框
 *   图形（池底 `V12_POOL_LO = 1`）⇒ 框照画、只是错位一格
 *   ⇒ 实测「文字空了、UI 没空」。
 *   为什么「继续游戏」空白了而领航员没有：领航员的初始化步进器
 *   （pokenav.c `sub_80EF874` case 10）**每次进入都重画框**，开始菜单不重画。
 *
 * 语义 = 把整块框矩形写成 **0 号 tile**（游戏自己的擦除约定：
 *   `TextWindow_EraseDialogueFrame` 写的就是 `paletteNum << 12`，低 10 位 = 0）。
 *   一次拿到两个效果：
 *     · 框在屏上消失（与文字的 `t0 == 0 ⇒ return` 对称）；
 *     · 旧框砖失去 tilemap 引用 ⇒ 活引用层 `bm` 放行 ⇒ 下一轮可回收
 *       （否则它们被永久保护，池子只出不进）。
 * 由 entry.s 的 `V14StdFrame_Hook` / `V14DlgFrame_Hook` 调用。
 * ==========================================================================*/
void v14_std_frame_erase_C(uint16_t *tilemap, uint32_t packed);
void v14_dlg_frame_erase_C(uint8_t *win, uint32_t packed);
"""

WIN_ALLOC_C_BLOCK = """

/* ============================================================================
 * v14（2026-09-11）：框的 tilemap 与文字同权 —— 「领不到号 ⇒ 不画」。
 * 病灶与判据见 win_alloc.h 的同名段落。这里只说两件事：
 *
 * 🔴 为什么擦成 **0 号 tile** 而不是「什么都不写」：
 *   不写 ⇒ 上一次那份 tilemap（指向旧框砖）原样留着 ⇒ 框还在屏上。
 *   必须擦掉，旧框砖的引用才会断，才谈得上回收。
 *   0 号 tile 是官方自己的「空」约定（`Menu_EraseScreen` /
 *   `TextWindow_EraseDialogueFrame` 都写 `paletteNum << 12`，低 10 位 = 0）。
 *
 * 🔴 为什么门控读 0x03000514 / 0x03000516：
 *   这两个槽是**官方自己的字段**，v12 起由 `v10_set_frame_base_C`（⑤）与官方 ⑥
 *   写：成功 = 1..1023，失败（池子满）= 0。不是自造魔数。⑤ 与 ⑨b 在同一段
 *   初始化里严格前后相邻（⑤ 先）⇒ 读到 0 就一定是「这一窗没领到号」。
 * ==========================================================================*/
static void v14_erase_rect_C(void *tm, unsigned left, unsigned top,
                             unsigned right, unsigned bottom)
{
    volatile uint16_t *tilemap = (volatile uint16_t *)tm;
    unsigned x, y, s;

    if (!tilemap)
        return;
    if (left > right) { s = left; left = right; right = s; }
    if (top > bottom) { s = top;  top = bottom; bottom = s; }
    if (left > 31u)   left = 31u;
    if (right > 31u)  right = 31u;
    if (top > 31u)    top = 31u;
    if (bottom > 31u) bottom = 31u;

    for (y = top; y <= bottom; y++)
        for (x = left; x <= right; x++)
            tilemap[x + 32u * y] = 0u;
}

/* packed = left | top<<8 | right<<16 | bottom<<24（四项都是 u8，调用方已收窄）。 */
void v14_std_frame_erase_C(uint16_t *tilemap, uint32_t packed)
{
    v14_erase_rect_C(tilemap,
                     packed & 0xFFu, (packed >> 8) & 0xFFu,
                     (packed >> 16) & 0xFFu, (packed >> 24) & 0xFFu);
}

/* 对话框版：入参是 win；packed 里是**绝对**矩形 (left, top, right, bottom)，
 * 由跳板按官方 `TextWindow_DrawDialogueFrame` 硬编码的
 * (left=1, top=14, width=22, height=4) 折算好：right = 28、bottom = 19。 */
void v14_dlg_frame_erase_C(uint8_t *win, uint32_t packed)
{
    uint8_t *tpl;

    if (!win)
        return;
    tpl = *(uint8_t *volatile *)win;                    /* win[0] = 模板指针 */
    if (!tpl)
        return;
    v14_erase_rect_C(*(void *volatile *)(tpl + 0x10u),   /* TPL_TILEMAP */
                     packed & 0xFFu, (packed >> 8) & 0xFFu,
                     (packed >> 16) & 0xFFu, (packed >> 24) & 0xFFu);
}
"""

# ---------------------------------------------------------------- 补丁表
# (相对 HOOK 的路径, [(旧, 新, 期望命中数), ...], 末尾追加内容 or None)
PATCHES = [
    ("game_addrs.asm", [(
        "TextWindow_LoadDlgFrameGraphics        equ 0x08062684\n",
        "TextWindow_LoadDlgFrameGraphics        equ 0x08062684\n\n" + GAME_ADDRS_BLOCK,
        1,
    )], None),

    ("src/text/hooks_origin.s", [(
        "    ldr  r5, =(V13NoteWin_Hook | 1)\n    bx   r5\n.pool\n",
        "    ldr  r5, =(V13NoteWin_Hook | 1)\n    bx   r5\n.pool\n" + HOOKS_ORIGIN_BLOCK,
        1,
    )], None),

    ("src/text/entry.s", [(
        "    .size V13NoteWin_Hook, .-V13NoteWin_Hook\n    .pool\n\n.end\n",
        "    .size V13NoteWin_Hook, .-V13NoteWin_Hook\n    .pool\n" + ENTRY_BLOCK + "\n.end\n",
        1,
    )], None),

    ("include/win_alloc.h", [(
        "void v13_note_win_C(uint8_t *win);\n",
        "void v13_note_win_C(uint8_t *win);\n" + WIN_ALLOC_H_BLOCK,
        1,
    )], None),

    ("src/text/win_alloc.c", [(
        "void v13_set_tpl_C(uint8_t *win)\n",
        "void v13_set_tpl_C(uint8_t *win)\n",
        1,
    )], WIN_ALLOC_C_BLOCK),

    ("build_sh_equiv.sh", [(
        "V12StdFrame_Hook V12DlgFrame_Hook V13WinGfx_Hook V13NoteWin_Hook; do",
        "V12StdFrame_Hook V12DlgFrame_Hook V13WinGfx_Hook V13NoteWin_Hook \\\n"
        "           V14StdFrame_Hook V14DlgFrame_Hook; do",
        1,
    )], None),

    ("build.bat", [(
        "V13WinGfx_Hook V13NoteWin_Hook) do (",
        "V13WinGfx_Hook V13NoteWin_Hook V14StdFrame_Hook V14DlgFrame_Hook) do (",
        1,
    )], None),
]


def main():
    problems = []
    out = []          # (path, bytes)

    # ---- 第一遍：全部在内存里改完，任何一个锚点对不上就整体不写盘 ----
    for rel, reps, append in PATCHES:
        path = os.path.join(HOOK, rel)
        raw = open(path, "rb").read()
        crlf = raw.count(b"\r\n")
        text = raw.decode("utf-8").replace("\r\n", "\n")
        before = text

        for old, new, want in reps:
            got = text.count(old)
            if got != want:
                problems.append("%s: 锚点命中 %d 次（期望 %d）：%r"
                                % (rel, got, want, old[:60]))
                continue
            text = text.replace(old, new)

        if append is not None:
            if "v13_set_tpl_C" not in text:
                problems.append("%s: 追加锚点缺失" % rel)
            elif "v14_std_frame_erase_C" in text:
                problems.append("%s: v14 内容已存在（勿重复打）" % rel)
            else:
                text = text.rstrip("\n") + "\n" + append

        if text == before:
            problems.append("%s: 内容无变化" % rel)
            continue

        if crlf and crlf == raw.count(b"\n"):
            text = text.replace("\n", "\r\n")

        out.append((path, rel, raw, text.encode("utf-8")))

    if problems:
        print("=== 失败，未写盘 ===")
        for p in problems:
            print("  ✗", p)
        return 1

    # ---- 第二遍：全部落盘 ----
    print("=== v14 补丁全部命中 ===")
    for path, rel, raw, blob in out:
        open(path, "wb").write(blob)
        print("  ✓ %-28s %6d → %6d B" % (rel, len(raw), len(blob)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
