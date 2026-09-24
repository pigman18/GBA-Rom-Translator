; =============================================================================
; [P06 P09~P12] 初始宠选择 label（纯值/就地改写，无 C 依赖）
; pokeruby: src/starter_choose.c CreateStarterPokemonLabel() @0x081053A8
; =============================================================================

; --- [P06] label 擦除右边界：left+8 -> 固定 29 列 ---
; 日版按假名宽度擦 left+8 列，中文名(12px)更宽 -> 右半 tile 残留碎字。
; 屏上同时只显示一个 label，擦到窗口最右不误伤。
.org 0x081053D0
    mov r2, 0x1D            ; 原 adds r2,#8

; --- [P09~P12] B06 第一行栈溢出 -> 宝可梦名重复打印 ---
; 栈帧 0x20->0x60 两行 buffer 隔离；「ポケモン」拷贝从固定 5B 改为拷到
; 0xFF（上限 0x11），F9 序列完整落盘，无悬空 F9、无溢出。
.org 0x081053B2
    sub sp, 0x60            ; 原 sub sp,0x20

.org 0x08105416
    add r1, sp, 0x30        ; 第二行 buffer sp+0x10 -> sp+0x30

.org 0x0810551C
    add sp, 0x60            ; 配对还原

; 0x0810544C 拷贝循环重写（原固定 5B：cmp r7,#4/bls），总字节数不变(0x1A)
.org 0x0810544C
StarterPokeCopyLoop:
    mov r0, sp
    add r1, r0, r4
    add r0, r7, r2
    ldrb r0, [r0, #0]
    strb r0, [r1, #0]
    cmp r0, #0xFF
    beq StarterPokeCopyDone
    add r7, #1
    add r4, #1
    cmp r7, #0x11
    bls StarterPokeCopyLoop
    nop
    nop
StarterPokeCopyDone:
