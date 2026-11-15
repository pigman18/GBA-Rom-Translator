@ game.bin: bump TM/berry name print left then resume 0x080A0770
@ r2 = Menu_PrintText left（原 TM 传 0x10，与 No. 图块叠）→ 至少 0x13
@ stub 8B → resume 0x080A0778
    .cpu arm7tdmi
    .syntax unified
    .thumb
    .text
    .align 2

    .global Bag_PrintTMName_Hook
    .thumb_func
    .type Bag_PrintTMName_Hook, %function

Bag_PrintTMName_Hook:
    cmp r2, #0x13
    bhs 1f
    movs r2, #0x13
1:
    /* stolen 0x080A0770..0777 */
    push {r4, r5, r6, lr}
    mov r6, sb
    mov r5, r8
    push {r5, r6}
    ldr r3, =(0x080A0778 | 1)
    bx r3
    .pool

    .size Bag_PrintTMName_Hook, .-Bag_PrintTMName_Hook
