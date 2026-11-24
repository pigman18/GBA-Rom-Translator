@ =============================================================================
@ NickFullName_entry.s — 战斗血条名字：完整中文名 + 跳过日文字模二次覆盖
@
@ ── 权威源码（tools/pokeruby/src/battle_interface.c:1495 sub_80451A0）────────
@ 完整流程（这是唯一权威）：
@
@   u8 nickname[POKEMON_NAME_LENGTH];                       // 10
@   StringCopy(gDisplayedStringBattle, "{HIGHLIGHT RED}");   // 3B 前缀
@   GetMonData(pkmn, MON_DATA_NICKNAME, nickname);
@   StringGetEnd10(nickname);                               // 硬截断 10B
@   ptr = StringCopy(gDisplayedStringBattle + 3, nickname); // ← hook A (0x08042440)
@   ptr[0..] = FC 03 02 / FC 01 0A|0B / FC 13 37
@   ptr = &eBattleInterfaceGfxBuffer[0x520 + pos * 0x180];   // = 0x02000520 + pos*0x180
@   RenderTextHandleBold(ptr, gDisplayedStringBattle);       // 强制 tm=2 buffered
@   // ↓ 日文 8x8 字模二次覆盖（见 hook B）
@   if (LANGUAGE==1 && !isEgg) { while(*p!=EOS) { ... CpuCopy32(elem 0x2B, ptr+0x40*i, 32); i++; p++; } }
@   for (; i < 7; i++) CpuCopy32(elem 0x2B, ptr+64*i, 32);
@
@ ── AXVJ 反汇编（全部实测）──────────────────────────────────────────────
@   0x0804243A  adds r4, #3              ; r4 = gDisplayedStringBattle + 3
@   0x0804243C  adds r0, r4              ; r0 = dst
@   0x0804243E  mov  r1, sp              ; r1 = 局部 nickname（10B）
@   0x08042440  bl   0x080042E8          ; StringCopy(dst, nickname)  ← hook A
@   0x08042444  adds r6, r0              ; r6 = EOS 地址 ★ 依赖返回值
@
@   0x080424D8  ldr  r0, =0x02000520     ; eBattleInterfaceGfxBuffer + 0x520
@   0x080424DA  adds r6, r1, r0          ; r6 = 0x02000520 + pos*0x180
@   0x0804252C  mov  r8, r0              ; r8 = StringLength(buf+3) - 6
@   0x0804252E  adds r0, r6              ; r0 = tileData
@   0x08042530  adds r1, r4              ; r1 = gDisplayedStringBattle
@   0x08042532  bl   0x08002CC0          ; RenderTextHandleBold（强制 tm=2）
@   0x08042536  movs r5, #3              ; ★ 0x2B 覆盖循环起点
@   0x0804253A  cmp  r7, r8 / bcs 0x80425A8
@   0x0804253E  ldr  r0, =0x0202362C     ; 名字串
@   0x08042542  ldrb r1, [r0]            ; 每字节画一个 8x8 块
@   0x08042598  bl   0x081B1294          ; CpuSet(elem, dst, 32B)
@   0x080425A8  ... 第二段：EWRAM → VRAM
@
@ ── 为什么名字必须由 hook A 写（不能用原版 nickname）──────────────────
@ nickname[10] 是 Gen3 存档定长字段。中文 3 字 = 12B 塞不下：
@   StringGetEnd10 硬截断 → 第 3 字的 hi lo 丢失
@   GDB 实测：f7 00 0b bd | f7 00 0d 8c | f7 00        ← 只剩 2 字节
@ 而 dst = gDisplayedStringBattle + 3 是全局缓冲，空间充足，写 12B 安全。
@ ⇒ hook A 用 species 查中文名表，直接写完整名到 dst。
@ 存档完全不碰 → 串回日版不乱码（与队伍 BUG-13、P12 同一原则）。
@
@ ── 为什么还要 hook B（跳过 0x2B 覆盖）────────────────────────────────
@ 我们的 buffered 引擎（PrintNextChar_hook.c）已经按 rel*64B 把中文画进
@ EWRAM 缓冲，每个字占 1 个 64B 单元（上下两片 8x8）。
@ 而原版这段循环是给「日文 6 字节名」设计的：
@   · 中文 F7 00 hi lo 被当 4 个独立字节 → 1 汉字吃掉 4 次 i++
@   · 3 汉字 = 12 次 >> 上限 7
@   · elem 0x2B 是「擦格子的底色条」（实测行2-7 = 6/7/3/2 四色渐变）
@ ⇒ 它把已经画好的中文上半截盖成横条，就是 BUG-12 的真根因。
@
@ 修法：在 0x08042536 处跳过整个第一段（0x2B 覆盖），直接到 0x080425A8
@ 的第二段（EWRAM → VRAM 拷贝）—— 那一段是我们需要的。
@
@ ── 为什么不用 0x08042430（GetMonData）────────────────────────────────
@ 0x0804242E `mov r2, sp` 的 sp 是 sub_80451A0 的局部 nickname[10]
@ （源码 1497 行），只有 10 字节。长名字往这里写会溢出，压坏紧跟其后的
@ gender/species/language/ptr（源码 1498-1504）。旧版 hook 在这里，方向就错了。
@
@ ── 铁律 ─────────────────────────────────────────────────────────────
@ 所有 `ldr r3, =0x08xxxxxx` 必须 |1（Thumb 位）；bx 到偶数会切 ARM 模式跑飞。
@ =============================================================================

    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global NickFullName_Hook
    .thumb_func
    .type NickFullName_Hook, %function

@ ── hook A：0x08042440  StringCopy(dst=gDSB+3, src=nickname) ─────────────
@ 进入：r0 = dst, r1 = src(局部 nickname), r5 = mon
@ 退出：r0 = EOS 地址（与 StringCopy 契约一致，0x08042444 的 adds r6,r0 依赖它）
NickFullName_Hook:
    push {r4, r5, r6, lr}
    sub  sp, #32                    @ GetMonData(..,11,..) 的 dst 需 >=32B

    adds r4, r0, #0                 @ r4 = dst
    adds r6, r1, #0                 @ r6 = src（默认原 nickname）

    @ ① species = GetMonData(mon, MON_DATA_SPECIES=11, tmp)
    adds r0, r5, #0
    movs r1, #11
    add  r2, sp, #0
    ldr  r3, =0x08039F25            @ ★ |1
    bl   _Nick_bx_r3
    @ r0 = species

    @ ② 范围检查 1..411；越界回退原 nickname
    @    412 = 206<<1，避免 ldr =411 引入字面量池
    cmp  r0, #1
    blt  _Nick_copy
    movs r1, #206
    lsls r1, r1, #1                 @ r1 = 412
    cmp  r0, r1
    bge  _Nick_copy

    @ ③ src = 中文名表 + species*24
    ldr  r6, =0x09EB0AF4
    lsls r1, r0, #1
    adds r1, r1, r0                 @ species*3
    lsls r1, r1, #3                 @ species*24
    adds r6, r6, r1

    @ ④ 逐字节拷到 dst，遇 FF 停（含 FF）
    @
    @ ★ 3 字上限（2026-11-24 B 方案）：名字区只有 0x180 = 384 字节
    @   = 3 个 128B 单元。第 4 个字会写到名字区之外（踩 HP 条/框体装饰），
    @   所以在这里就截断，并把 FF 补在第 3 字之后。
    @   中文名 3 字占 12B（F7 00 hi lo × 3），第 13 字节写 FF。
    @   超过 3 字的物种名（罕见）显示前 3 字，不越界、不花屏。
_Nick_copy:
    movs r2, #0
_Nick_loop:
    cmp  r2, #12                    @ 12B = 3 个汉字
    bge  _Nick_trunc
    ldrb r0, [r6, r2]
    strb r0, [r4, r2]
    adds r2, #1
    cmp  r0, #255
    bne  _Nick_loop
    b    _Nick_eos

_Nick_trunc:
    movs r0, #255                   @ 超长：第 13 字节补 FF
    strb r0, [r4, r2]
    adds r2, #1

_Nick_eos:
    @ ⑤ 返回 EOS 地址 = dst + (r2 - 1)
    subs r1, r2, #1
    adds r0, r4, r1

    add  sp, #32
    pop  {r4, r5, r6}
    pop  {r1}
    bx   r1

_Nick_bx_r3:
    bx   r3

    .align 2
    .size NickFullName_Hook, .-NickFullName_Hook


@ ── hook B：0x08042536  跳过 0x2B 日文字模覆盖段 ───────────────────────
@ 进入：r8 = 循环次数（len-6），r6 = EWRAM tile 缓冲基址，r4 = 名字串
@ 任务：直接跳到 0x080425A8（第二段 EWRAM→VRAM 拷贝）
@
@ 为什么能整体跳过：0x08042536..0x080425A6 整段只做「把 elem 0x2B 写进
@ EWRAM 缓冲」，没有任何后续依赖的副作用（r5/r7 只在本段内用）。
@ 0x080425A8 起读 r4(名字串)/sl(战斗槽)/sp+12，这些在 0x08042536 前已就绪。
    .global NickSkipTiler_Hook
    .thumb_func
    .type NickSkipTiler_Hook, %function
NickSkipTiler_Hook:
    ldr  r3, =0x080425A9            @ ★ |1，第二段入口
    bx   r3
    .align 2
    .size NickSkipTiler_Hook, .-NickSkipTiler_Hook



@ ── hook C：0x080425CC  第二段循环次数 r8 = ceil(字数 x 9 / 8) ────────────
@
@ ★ 为什么必须接管 r8（2026-11-24 实测）：
@   原版 r8 = StringLength(gDSB+3) - 6。对日文 6 字节名 = 0（不补空格）。
@   中文名 3 字 = 3 + 12 + 3 + 1 + 1 = 20B  →  r8 = 14
@   14 x 64B = 896B 写进只有 384B（0x180）的名字区
@   ⇒ 越界覆盖 HP 条与框体装饰，实机表现为血条上方整块白斑。
@
@ 正确值：Small 每字 9px（adv=9），一个单元 8px 宽，所以
@   1字→2  2字→3  3字→4  4字→5  5字→6  6字→7 单元
@   即 r8 = ceil(chars * 9 / 8)，硬上限 6（名字区 0x180 = 6 个 64B 单元）。
@   名字区最多容纳 5 个汉字（5*9=45px → ceil(45/8)=6）。
@
@ 每轮仍是原版 64B 步进（r5 = 0..r8-1），渲染侧 p0/p1 咬合逻辑
@ 负责让相邻字共享边界单元（PrintNextChar_hook.c 的 grid_emit buffered 分支）。
@
@ ⚠ bl 挂在 0x080425CC（原指令 ），返回地址是 0x080425D0（bge），
@   会跳过 r5 初始化 ⇒ 必须手动重放  +  再跳 bge。
    .global NickCopyCells_Hook
    .thumb_func
    .type NickCopyCells_Hook, %function
NickCopyCells_Hook:
    push {r4, r5, r6, lr}

    ldr  r4, =0x0202362F            @ gDisplayedStringBattle + 3
    movs r5, #0                     @ 汉字计数
    movs r6, #0                     @ 字节偏移

_Nc_scan:
    ldrb r0, [r4, r6]
    cmp  r0, #255                   @ FF = EOS
    beq  _Nc_calc
    cmp  r5, #5                     @ 名字区最多 5 字
    bge  _Nc_calc

    cmp  r0, #0xF7                  @ F7 00 hi lo = 一个汉字（4B）
    bne  _Nc_ctrl
    adds r3, r6, #1
    ldrb r0, [r4, r3]
    cmp  r0, #0
    bne  _Nc_plain
    adds r6, #4
    adds r5, #1
    b    _Nc_scan

_Nc_ctrl:
    cmp  r0, #0xFC                  @ FC xx yy = 扩展控制码（3B）
    bne  _Nc_plain
    adds r6, #3
    b    _Nc_scan

_Nc_plain:
    adds r6, #1                     @ 其它单字节不计数（性别图标等）
    b    _Nc_scan

_Nc_calc:
    @ r8 = ceil(r5 * 9 / 8) = (r5*9 + 7) >> 3
    movs r0, #9
    muls r0, r5, r0
    adds r0, #7
    lsrs r0, r0, #3
    cmp  r0, #6                     @ 硬上限 6 个单元
    ble  _Nc_set
    movs r0, #6
_Nc_set:
    mov  r8, r0

    pop  {r4, r5, r6}
    pop  {r0}

    @ 重放被 bl 覆盖的两条原指令，再跳到 bge
    movs r5, #0
    cmp  r5, r8
    ldr  r3, =0x080425D1            @ ★ |1
    bx   r3
    .align 2
    .size NickCopyCells_Hook, .-NickCopyCells_Hook


@ ── hook D：0x0804264A  敌方路径（备用）的 r8 定型 ────────────────────────
@
@ ★ 2026-11-24 BUG-12 真根因（静态 + RAM 实测双向确认）：
@   sub_80451A0 有**两条**「EWRAM → VRAM」拷贝路径：
@     主路径  0x080425CC（我方）：up = tileNum + i + 2，dn = tileNum + i + 10
@     备用路径 0x0804264A（敌方）：up = tileNum + i + 1，dn = tileNum + i + 9
@   走哪条由 0x080425B8 的守卫决定：
@     0x080425B8  bl GetBattlerSide → cmp r0,#0 → bne 0x0804262C（→ 备用路径）
@   ⇒ 敌方 side=1，**永远走备用路径**。而 hook C 只补在主路径 0x080425CC，
@     备用路径的 r8 一直是原版值 = StringLength(gDSB) - 6。
@
@   实测（产物 ba623905，帧 011，写死敌方 species=288）：
@     gDSB = fc0202 | 3x(f7 00 hi lo) | fc010b b5 | ff  ⇒ StringLength=20
@     r8 = 20 - 6 = 14
@     ⇒ 14 轮 × 64B = 896B 写进只有 0x180(384B) 的名字区：
@        第 14 字节起就在读名字区之外（0x02000820 之后），
@        VRAM tile144 实测等于 RAM 0x02000880（越界 96B）——
@        那里的值 6/7/8 正是血条框的绿色渐变 ⇒ 用户看到的「绿色涂块」。
@     且备用路径 up/dn 两个区间只差 8 格：
@        up = 129..142、dn = 137..150 ⇒ **137..142 重叠**，
@        后半程 up 把前半程已写好的 dn 覆盖掉
@        ⇒ 实测 VRAM 129..141 全是 cell0..12.up（13/13 命中），
@           cell0..4.dn 一个都没留下 ⇒ 汉字下半截全部丢失（破碎残字）。
@
@   对照 origin：ジグザグマ 6 字节 → StringLength=14 → r8=8
@     up = 129..136、dn = 137..144，**不重叠**，正好覆盖 16 格。
@
@   修法：备用路径也接管 r8，用与主路径相同的「字数 → 单元数」公式。
@   进入时 r5 尚未初始化（0x0804264A 后紧跟 movs r5,#0），
@   所以直接复用共享体，再重放 movs r5,#0 / cmp r5,r8 后跳 0x0804264F。
@   0x0804264A: 00 25 45 45 = movs r5,#0 ; cmp r5,r8
@   ⇒ 覆盖 4 字节，返回后重放这两条，落点是 0x0804264E(bge)。
    .global NickCopyCellsAlt_Hook
    .thumb_func
    .type NickCopyCellsAlt_Hook, %function
NickCopyCellsAlt_Hook:
    push {r4, r5, r6, lr}

    ldr  r4, =0x0202362F            @ gDisplayedStringBattle + 3
    movs r5, #0                     @ 汉字计数
    movs r6, #0                     @ 字节偏移

_Na_scan:
    ldrb r0, [r4, r6]
    cmp  r0, #255                   @ FF = EOS
    beq  _Na_calc
    cmp  r5, #5                     @ 名字区最多 5 字
    bge  _Na_calc

    cmp  r0, #0xF7                  @ F7 00 hi lo = 一个汉字（4B）
    bne  _Na_ctrl
    adds r3, r6, #1
    ldrb r0, [r4, r3]
    cmp  r0, #0
    bne  _Na_plain
    adds r6, #4
    adds r5, #1
    b    _Na_scan

_Na_ctrl:
    cmp  r0, #0xFC                  @ FC xx yy = 扩展控制码（3B）
    bne  _Na_plain
    adds r6, #3
    b    _Na_scan

_Na_plain:
    adds r6, #1                     @ 其它单字节不计数（性别图标等）
    b    _Na_scan

_Na_calc:
    @ 备用路径的 up/dn 只差 8 格（比主路径的 8 格少 1 个错位），
    @ 因此重叠区间是 [dn_start, up_end] = [i+9, i+1+n-1] ⇒ 只要 n>=9 就重叠。
    @ 用「n 个单元」= ceil(字数*9/8) 并硬限 6，两条路径区间都安全：
    @   n=6 ⇒ up=+1..+6, dn=+9..+14 ⇒ 无重叠，正好 6 个汉字的上/下片。
    movs r0, #9
    muls r0, r5, r0
    adds r0, #7
    lsrs r0, r0, #3
    cmp  r0, #6                     @ 硬上限 6 个单元（名字区 0x180 = 6 单元）
    ble  _Na_set
    movs r0, #6
_Na_set:
    mov  r8, r0

    pop  {r4, r5, r6}
    pop  {r0}

    @ 重放被覆盖的两条原指令（movs r5,#0 / cmp r5,r8），再跳 bge
    movs r5, #0
    cmp  r5, r8
    ldr  r3, =0x0804264F            @ ★ |1（0x0804264E 是 bge.n，|1 才是 Thumb）
    bx   r3
    .align 2
    .size NickCopyCellsAlt_Hook, .-NickCopyCellsAlt_Hook
