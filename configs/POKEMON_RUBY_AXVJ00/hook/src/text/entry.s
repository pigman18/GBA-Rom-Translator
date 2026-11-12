@ =============================================================================
@ src/text/entry.s — 引擎唯一入口跳板（r0=win 直进 C）
@
@ main.asm 在 GameBinAddresses 处贴标签 JP2CHS_Entry 并把 P01 订到此；
@ 本文件对象必须排链接首位：game.bin 起点 = EngineEntry。
@ （link/game.ld 的 KEEP(*entry.o(.text*)) 会匹配 text_entry.o。）
@
@ 2026-11-11 晚重写配套注释：
@   - 引擎改为纯函数 tile 网格（tile = TILE_BASE+(row&7)*62+col*2），
@     12px 跨列共享由运行时逐像素合成；无页表 / 无 PHYS 池 / 无 EWRAM 相位表；
@   - 旧 Hook3 跳板、WaitArrow_Prepare_Hook、GlyphIwtdTramp（P24）早已移除，
@     不再复建。
@
@ ⚠️ lr 契约（决定引擎能否回落原版）：
@   P01 桩用 bx（不是 bl）进 EngineEntry，EngineEntry 又用 bx 进 C，
@   所以 PrintNextChar_Hook 的 lr = 原版调用者返回地址。
@   此时再从 C 里 bl PrintNextChar_Origin 会多压一层 {r4,lr}，
@   与原版函数自身 pop {r4-r7,pc} 深度不匹配 → 栈失衡。
@   故该桩当前**不被调用**，仅作为 P01 8B 覆盖的回放契约文档保留；
@   页表缺失 / 动态流 / 未命中一律走「消费但不绘制」（见设计 §5.1 判断 D）。
@ =============================================================================
    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global EngineEntry
    .thumb_func
    .type EngineEntry, %function
    .global PrintNextChar_Origin
    .thumb_func
    .type PrintNextChar_Origin, %function
    .extern PrintNextChar_Hook

@ -----------------------------------------------------------------------------
@ 原生帧驱动 call PrintNextChar@0x080032F8（r0=win）直进的引擎入口。
@ 返回值契约：可印=1 / FF=0 / FA·FB·FD·FE=2 / FC=子结果。
@ -----------------------------------------------------------------------------
EngineEntry:
    ldr r1, =PrintNextChar_Hook
    bx  r1
    .pool
    .size EngineEntry, .-EngineEntry

@ -----------------------------------------------------------------------------
@ PrintNextChar_Origin — 回放被 P01 覆盖的 4 条序言后续跑原版。
@ 禁止 .incbin 整函数到 0x0880xxxx：函数内 bl 为 PC 相对，搬家后跳飞。
@ P01 只盖 8B，从 0x08003300 起仍是原指令。
@ -----------------------------------------------------------------------------
PrintNextChar_Origin:
    push    {r4, lr}
    adds    r4, r0, #0
    ldrh    r0, [r4, #0x14]
    adds    r1, r0, #1
    ldr     r2, =0x08003301
    bx      r2
    .pool
    .size PrintNextChar_Origin, .-PrintNextChar_Origin

.end
