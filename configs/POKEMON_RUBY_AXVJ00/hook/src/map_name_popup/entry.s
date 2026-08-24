@ =============================================================================
@ map_name_popup/entry.s — 地名弹窗居中跳板（P04，挂 DrawMapNamePopup 位点）。
@ .c 只写逻辑，寄存器/lr 约定在这里；ROM 订址桩见 hooks_origin.s。
@
@ DrawMapNamePopup @0x0809F67E（原 bl StringLength 位点）：
@ native 0809F67C `mov r0,sp` 已把 20B 缓冲区放入 r0；ROM 桩只用 r3 转跳
@ （严禁 ldr r0 —— v1~v3 历史根因：覆盖 r0 后 C 把跳板自身机器码当名字量宽）。
@ r5=地图头指针必须保活（C 按 AAPCS 自动保 r5）。
@ C 侧按引擎真实步进算居中留白（只读），返回留白 px；跳板注入
@ r1 = 原生 x 基准 1 + 留白px（curX 像素语义，见 MapNamePopup_hook.c 头注）。
@ 落点 0x0809F6CE 跳过 movs r1,#1，其后 bl MenuPrint 自设 lr。
@ =============================================================================
    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global MapName_DisplayCellLength
    .thumb_func
    .type MapName_DisplayCellLength, %function
    .extern MapNamePopup_CalcLeftPx

MapName_DisplayCellLength:
    push {r0, lr}                 @ r0=缓冲区指针必须保活
    bl   MapNamePopup_CalcLeftPx
    adds r2, r0, #0               @ 留白 px 暂存（thumb 禁低寄存器间 mov）
    pop  {r0, r3}                 @ r0=缓冲区（MenuPrint 参数），r3=官方返回址弃
    movs r1, #1                   @ 原生 x 基准（=1px）
    adds r1, r1, r2               @ x = 1 + 留白px
    ldr  r3, =0x0809F6CF          @ 落点 0x0809F6CE (movs r2,#1) | thumb
    bx   r3
    .pool
    .size MapName_DisplayCellLength, .-MapName_DisplayCellLength

.end
