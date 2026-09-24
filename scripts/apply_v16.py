# -*- coding: utf-8 -*-
"""v16 一次性补丁：把「文字与 UI 两个池子」这件事彻底拆掉。

病灶（两层，互相独立）：
  ① win_alloc.c:v10_pool_lo() 给**文字**单开了一个下限
       `P_CALLS == 0 ? V11_POOL_LO : P_TEXT`
     ⑤（UI）恒在 ① 复位 P_CALLS 之后被调 ⇒ 永远 lo = 池底（全区）；
     文字恒在 ⑤ 之后被调 ⇒ lo = P_TEXT（框之后），永不回卷到框前面。
     同一个数组、两个 [lo,hi) ⇒ 行为上就是两个池子。
     而且 `lo >= hi` 时 v8_alloc_core **直接 return 0**（连 v8_rebuild_live 都不跑）
     ⇒ 文字一旦被顶到上界就永久空白，哪怕池子空着。这就是「文字空、UI 不空」。

  ② UI 的框号只由 ⑤ 发放，而 ⑤ **全盘 14 个调用点里没有一个在领航员的窗口装载链上**
     （那条链只有 InitWindow(0x080685C2) → ①(0x080685CA) → ③(0x080685E0)）
     ⇒ 领航员的框读到 0x03000514 的**残值**，根本没过池子这关 ⇒ 池子再满也照画。

修法：
  A. v10_pool_lo() 恒返池底 —— 文字与 UI 只有一个 lo。
  B. tile_alloc.c 抽出**纯扫描** v8_scan_find（不取号/不改游标），
     新增 v8_frame_room(tpl) = 「池子当下还能不能给出一整段 V10_FRAME_SPAN 个连续可用砖」。
  C. entry.s 的两个 v14 跳板：门控从「槽 == 0」扩成「槽 == 0 **或** 池子给不出一个框」。

两遍式：先在内存改完，任一锚点对不上即整体不写盘。
按各文件原有换行风格回写。
"""
import io
import os
import sys

ROOT = r"C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\hook"

F_WIN = os.path.join(ROOT, "src", "text", "win_alloc.c")
F_TILE = os.path.join(ROOT, "src", "text", "tile_alloc.c")
F_HDR = os.path.join(ROOT, "include", "tile_alloc.h")
F_ENTRY = os.path.join(ROOT, "src", "text", "entry.s")


# ---------------------------------------------------------------- A. win_alloc.c
OLD_POOL_LO = """/* 号池起点（= 本窗口文字起址下限）：未发框 ⇒ 池底；发过框 ⇒ 框之后。
 * 由 `v8_alloc_core`（tile_alloc.c）作为 `lo` 使用 —— 框与文字因此共享同一条序列。 */
uint16_t v10_pool_lo(void)
{
    v10w_init_once();
    if (P_CALLS == 0u)
        return V11_POOL_LO;
    return P_TEXT;
}"""

NEW_POOL_LO = """/* 号池起点 —— **文字与 UI 唯一的 lo**（v16，2026-09-11）。
 *
 * 🔴 v13 的 `if (P_CALLS == 0) return V11_POOL_LO; return P_TEXT;` 是「文字专用下限」：
 *   ⑤（UI）恒在 ① 复位 P_CALLS 之后被调 ⇒ `P_CALLS == 0` ⇒ lo = 池底（全区）；
 *   文字恒在 ⑤ 之后被调 ⇒ lo = `P_TEXT`（框之后）⇒ 文字只能往后排，永不回卷。
 *   同一个数组、两个不同的 `[lo, hi)` ⇒ **行为上就是两个池子** ——
 *   这是「文字空、UI 不空」的直接算术原因，也正是用户反复点名的
 *   「文字有下限 = 偷偷搞高水位」（= 把 `[1, P_TEXT)` 对文字设成不可用区）。
 *   更糟：`lo >= hi` 时 `v8_alloc_core` **直接 `return 0`**，连 `v8_rebuild_live`
 *   都不跑 ⇒ 文字一旦被顶到上界就永久空白，哪怕池子空着。
 *
 * 🔴 框不需要靠「抬高文字起址」来避让：框那 `V10_FRAME_SPAN` 个砖由 `v8_take`
 *   记进活引用位图 + ours 账本，文字的候选校验（`v8_tile_usable`）天然跳过它们。
 * ⇒ lo 只有一个：池底。谁先来谁先拿，谁拿不到谁空。 */
uint16_t v10_pool_lo(void)
{
    v10w_init_once();
    return V11_POOL_LO;
}"""


# -------------------------------------------------------------- B. tile_alloc.c
OLD_SCAN = """/* 确定性顺序遍历 [lo, hi)，逐候选过 v8_tile_usable；
 * 第一遍从上次游标起，第二遍回卷到 lo 重扫。找不到 → 0。 */
static uint16_t v8_alloc_scan(uint16_t n, uint16_t lo, uint16_t hi,
                              volatile uint8_t *bm, const void *vram)
{
    uint16_t start = *(volatile uint16_t *)ADDR_V8_CURSOR;
    uint16_t t;
    unsigned i;

    if (start < lo || start >= hi)
        start = lo;

    for (t = start; (unsigned)t + n <= (unsigned)hi; t++) {
        int ok = 1;
        for (i = 0; i < n; i++)
            if (!v8_tile_usable(bm, vram, (uint16_t)(t + i))) { ok = 0; break; }
        if (ok) { v8_take(bm, t, n); return t; }
    }
    for (t = lo; (unsigned)t + n <= (unsigned)hi; t++) {
        int ok = 1;
        for (i = 0; i < n; i++)
            if (!v8_tile_usable(bm, vram, (uint16_t)(t + i))) { ok = 0; break; }
        if (ok) { v8_take(bm, t, n); return t; }
    }
    return 0u;
}"""

NEW_SCAN = """/* 确定性顺序遍历 [lo, hi)，逐候选过 v8_tile_usable；**纯读 —— 不取号、
 * 不改游标、不进 ours**（v16 抽出，给「框还发不发得出」的判定复用）。
 * 第一遍从上次游标起，第二遍回卷到 lo 重扫。找不到 → 0。
 * ⚠ 会经由 v8_tile_usable 写「负缓存」（非空且非 ours 的砖一次判定后标进位图）——
 *   这是**单向收窄**，正是要的：可用集合只会少、不会多。 */
static uint16_t v8_scan_find(uint16_t n, uint16_t lo, uint16_t hi,
                             volatile uint8_t *bm, const void *vram)
{
    uint16_t start = *(volatile uint16_t *)ADDR_V8_CURSOR;
    uint16_t t;
    unsigned i;

    if (start < lo || start >= hi)
        start = lo;

    for (t = start; (unsigned)t + n <= (unsigned)hi; t++) {
        int ok = 1;
        for (i = 0; i < n; i++)
            if (!v8_tile_usable(bm, vram, (uint16_t)(t + i))) { ok = 0; break; }
        if (ok) return t;
    }
    for (t = lo; (unsigned)t + n <= (unsigned)hi; t++) {
        int ok = 1;
        for (i = 0; i < n; i++)
            if (!v8_tile_usable(bm, vram, (uint16_t)(t + i))) { ok = 0; break; }
        if (ok) return t;
    }
    return 0u;
}

/* 取号版 = 纯扫描 + v8_take（唯一改动：把 take 提出来，行为与 v13 逐字节等价）。 */
static uint16_t v8_alloc_scan(uint16_t n, uint16_t lo, uint16_t hi,
                              volatile uint8_t *bm, const void *vram)
{
    uint16_t t = v8_scan_find(n, lo, hi, bm, vram);
    if (t != 0u)
        v8_take(bm, t, n);
    return t;
}"""

ANCHOR_UI = """/* ② UI 分配：与文本完全同一条路径（同一个 v8_alloc_core）。 */
uint16_t v8_alloc_ui(uint8_t *tpl, uint16_t n)
{
    return v8_alloc_core(tpl, n);
}"""

ADD_FRAME_ROOM = ANCHOR_UI + """

/* ============================================================================
 * v16（2026-09-11）：「这个框号现在还归池子管吗？」—— 框与文字同权的**判定口**。
 *
 * 为什么必须有它（第二层真凶）：
 *   UI 的框号只由 ⑤ `TextWindow_SetBaseTileNum` 发放，而 ⑤ **全盘只有 14 个
 *   调用点**，其中**没有一个在领航员（PokéNav）的窗口装载链上** —— 那条链只有
 *       InitWindow(0x080685C2) → ① InitWindowTileData(0x080685CA) → ③(0x080685E0)
 *   ⇒ 领航员的框读到的 `0x03000514` 是**别的窗口留下的残值** ⇒ 它根本没过池子
 *   这一关 ⇒ 池子再满也照样画得出来。这是「文字空、UI 独活」的第二个独立成因
 *   （第一个是 `v10_pool_lo` 给文字单开的「框之后」下限）。
 *
 * 语义：在同一个 `[lo,hi)` 里找**一整段** `V10_FRAME_SPAN` 个连续可用砖。
 *   纯扫描 —— 不取号、不改游标、不进 ours。找不到 ⇒ 池子给不出一个框
 *   ⇒ 调用方（⑨b / 对话框包装）把框擦掉。
 * ⚠ 框要的是**连续 23 个**砖，比文字（2~4 个）苛刻 ⇒ 框会比文字更早被判「给不出」。
 *   这是正确方向（先耗尽的先空），不是不平等：两者用的是**同一个 lo、同一张位图**。
 * ==========================================================================*/
int v8_frame_room(uint8_t *tpl)
{
    volatile uint8_t *bm = v8_bitmap();
    const void *vram;
    uint16_t lo, hi;

    if (!tpl)
        return 0;
    vram = (const void *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!vram)
        return 0;
    hi = v8_alloc_hi(tpl[TPL_CHARBASE]);
    lo = v10_pool_lo();
    if (lo >= hi || (unsigned)(hi - lo) < V10_FRAME_SPAN)
        return 0;
    return v8_scan_find(V10_FRAME_SPAN, lo, hi, bm, vram) != 0u;
}"""


# ---------------------------------------------------------------- C. tile_alloc.h
OLD_UI_DECL = """uint16_t v8_alloc_ui(uint8_t *tpl, uint16_t n);

/* 当前队列游标（调试/埋点用）。 */"""

NEW_UI_DECL = """uint16_t v8_alloc_ui(uint8_t *tpl, uint16_t n);

/* v16（2026-09-11）：框与文字同权 —— 「池子当下还能不能给出一整个框？」
 *
 *   门控口。UI 的框号只由 ⑤ 发放，而 ⑤ 的 14 个调用点里**没有一个在领航员的
 *   窗口装载链上**（InitWindow → ① → ③）⇒ 领航员读到的是别的窗口留下的残值，
 *   根本没过池子这关 ⇒ 池子满也照画 = 「文字空、UI 独活」的第二个成因。
 *   现在 ⑨b / 对话框包装在**每次画框前**都调本函数：给不出 ⇒ 擦掉框。
 *
 *   纯扫描：不取号、不改游标、不进 ours。与文字共用同一个 lo
 *   （`v10_pool_lo()` 恒返池底）。 */
int v8_frame_room(uint8_t *tpl);

/* 当前队列游标（调试/埋点用）。 */"""


# ------------------------------------------------------------------- D. entry.s
OLD_STD_HEAD = """    .global V14StdFrame_Hook
    .thumb_func
    .type V14StdFrame_Hook, %function
    .extern v14_std_frame_erase_C
V14StdFrame_Hook:
    ldr     r1, =0x03000514            @ 重放 0x08062154（官方框号槽，⑤ 写）
    ldrh    r1, [r1]                   @ 重放 0x08062156 → r1 = 框号
    cmp     r1, #0                     @ 0 = 池子没发出号
    bne     StdFrameTmap_Resume
"""

NEW_STD_HEAD = """    .global V14StdFrame_Hook
    .thumb_func
    .type V14StdFrame_Hook, %function
    .extern v14_std_frame_erase_C
    .extern v8_frame_room
V14StdFrame_Hook:
    ldr     r1, =0x03000514            @ 重放 0x08062154（官方框号槽，⑤ 写）
    ldrh    r1, [r1]                   @ 重放 0x08062156 → r1 = 框号
    cmp     r1, #0                     @ 0 = 池子没发出号
    beq     StdFrameTmap_Erase
    @ 🔴 v16：槽非 0 也要再过一关 —— 「这个号现在还归池子管吗？」
    @   ⑤ 只在本窗装载时发号，而**有些窗口的装载链根本不调 ⑤**
    @   （领航员：InitWindow → ① → ③）⇒ 它读到的 0x03000514 是别的窗口的残值
    @   ⇒ 框不用过池子就能画 ⇒ 「文字空、UI 独活」的第二个成因。
    @   判定 = 「池子当下还能不能给出一整段 V10_FRAME_SPAN 个连续可用砖」。
    ldr     r2, =0x03000328            @ gTplSlot（① / 姊妹路径 / v13.2 都在维护）
    ldr     r2, [r2]
    cmp     r2, #0
    beq     StdFrameTmap_Erase
    push    {r0, r4, r5, r6}           @ 16B：保 tilemap + 矩形（C 会砸 r0-r3）
    adds    r0, r2, #0                 @ r0 = tpl
    bl      v8_frame_room              @ → r0 = 1（给得出）/ 0（给不出）
    cmp     r0, #0                     @ ⚠ pop 不改标志，cmp 必须排在 pop 前
    pop     {r0, r4, r5, r6}           @ 还原（16B ⇒ 8 对齐不变）
    beq     StdFrameTmap_Erase
    b       StdFrameTmap_Resume
    @ 🔴 零栈操作（擦除路径）：钩点在 ⑨b 体内，r4/r5/r6 由 ⑨b 自己的 epilogue
    @    从它栈帧还原；⑨b 的返回地址也取自它栈上那份 lr（`pop {r0}; bx r0`）
    @    ⇒ 活 lr 可砸。
StdFrameTmap_Erase:
"""

# 擦除块里那句「零栈操作」注释已被搬到上面，这里删掉避免重复
OLD_ERASE_NOTE = """    @ 🔴 零栈操作：钩点在 ⑨b 体内，r4/r5/r6 由 ⑨b 自己的 epilogue 从它栈帧还原；
    @    ⑨b 的返回地址也取自它栈上那份 lr（`pop {r0}; bx r0`）⇒ 活 lr 可砸。
"""

OLD_DLG_HEAD = """V14DlgFrame_Hook:
    ldr     r1, =0x03000516            @ 官方对话框框号槽（⑥ 写）
    ldrh    r1, [r1]
    cmp     r1, #0                     @ 0 = 池子没发出号
    bne     DlgFrameTmap_Resume
    ldr     r1, =0x131C0E01            @ packed：left 1 | top 14<<8 | right 28<<16 | bottom 19<<24
"""

NEW_DLG_HEAD = """V14DlgFrame_Hook:
    ldr     r1, =0x03000516            @ 官方对话框框号槽（⑥ 写）
    ldrh    r1, [r1]
    cmp     r1, #0                     @ 0 = 池子没发出号
    beq     DlgFrameTmap_Erase
    @ v16：同一个「号还在不在池子里」关 —— 与标准框完全一致。
    ldr     r1, =0x03000328            @ gTplSlot
    ldr     r1, [r1]
    cmp     r1, #0
    beq     DlgFrameTmap_Erase
    @ ⚠ v4T 的 Thumb 没有 `pop {r4,lr}`（无 32 位 Thumb）⇒ 用 r5 手工保 lr。
    push    {r4, r5}                   @ 8B：r4 = win，r5 = lr
    adds    r4, r0, #0                 @ r4 = win（erase 路径要用 r0 = win）
    mov     r5, lr
    adds    r0, r1, #0                 @ r0 = tpl
    bl      v8_frame_room
    adds    r2, r0, #0                 @ r2 = 1 / 0
    adds    r0, r4, #0                 @ r0 = win
    mov     lr, r5                     @ 还原 lr
    pop     {r4, r5}                   @ pop 不改标志 ⇒ cmp 必须排在后面
    cmp     r2, #0
    beq     DlgFrameTmap_Erase
    b       DlgFrameTmap_Resume
DlgFrameTmap_Erase:
    ldr     r1, =0x131C0E01            @ packed：left 1 | top 14<<8 | right 28<<16 | bottom 19<<24
"""


EDITS = [
    (F_WIN, [(OLD_POOL_LO, NEW_POOL_LO)]),
    (F_TILE, [(OLD_SCAN, NEW_SCAN), (ANCHOR_UI, ADD_FRAME_ROOM)]),
    (F_HDR, [(OLD_UI_DECL, NEW_UI_DECL)]),
    (F_ENTRY, [(OLD_STD_HEAD, NEW_STD_HEAD), (OLD_ERASE_NOTE, ""),
               (OLD_DLG_HEAD, NEW_DLG_HEAD)]),
]


def main():
    plan = []
    problems = []

    for path, subs in EDITS:
        with io.open(path, "rb") as fh:
            raw = fh.read()
        crlf = b"\r\n" in raw
        text = raw.decode("utf-8").replace("\r\n", "\n")
        for old, new in subs:
            n = text.count(old)
            if n != 1:
                problems.append("%s : 锚点命中 %d 次（应为 1）\n    %.90s"
                                % (os.path.basename(path), n, old.replace("\n", " ")))
                continue
            text = text.replace(old, new, 1)
        plan.append((path, text, crlf))

    if problems:
        print("!! 锚点不匹配，整体不写盘：")
        for p in problems:
            print("   " + p)
        return 1

    # 第二遍：全部锚点 OK 才落盘
    for path, text, crlf in plan:
        data = text.replace("\n", "\r\n") if crlf else text
        with io.open(path, "wb") as fh:
            fh.write(data.encode("utf-8"))
        print("OK  %-30s %d -> %d B  (%s)"
              % (os.path.basename(path), os.path.getsize(path), len(data),
                 "CRLF" if crlf else "LF"))

    # 自检：确认新内容真的在盘上
    checks = [
        (F_WIN, "return V11_POOL_LO;"),
        (F_TILE, "int v8_frame_room(uint8_t *tpl)"),
        (F_TILE, "static uint16_t v8_scan_find("),
        (F_HDR, "int v8_frame_room(uint8_t *tpl);"),
        (F_ENTRY, "StdFrameTmap_Erase:"),
        (F_ENTRY, "DlgFrameTmap_Erase:"),
        (F_ENTRY, "bl      v8_frame_room"),
    ]
    bad = 0
    for path, needle in checks:
        with io.open(path, "rb") as fh:
            blob = fh.read().decode("utf-8")
        ok = needle in blob
        if not ok:
            bad += 1
        print("   %s  %-14s  %s" % ("OK " if ok else "!! ", needle[:28],
                                    os.path.basename(path)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
