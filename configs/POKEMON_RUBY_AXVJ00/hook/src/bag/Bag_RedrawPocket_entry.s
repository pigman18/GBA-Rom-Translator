@ game.bin: scrub bag list arena then resume JP pocket redraw @ 0x080A0BF4
@ hooks_origin stub = ldr+bx+.pool = 8B → resume 0x080A0BFC（asrs；lsls 在钩内）.
@ Stolen first 8B used PC-relative ldr — re-issue with absolute pocket ptr.
    .cpu arm7tdmi
    .syntax unified
    .thumb
    .text
    .align 2

    .global Bag_RedrawPocket_Hook
    .thumb_func
    .type Bag_RedrawPocket_Hook, %function
    .extern Bag_RedrawPocket_Prep_C

Bag_RedrawPocket_Hook:
    push {lr}
    bl Bag_RedrawPocket_Prep_C
    pop {r3}
    mov lr, r3
    /* stolen 0x080A0BF4..BFB: push/ldr/ldrb/lsls；接着 asrs @BFC */
    push {lr}
    ldr r0, =0x02038258
    ldrb r0, [r0]
    lsls r0, r0, #24
    ldr r3, =(0x080A0BFC | 1)
    bx r3
    .pool

    .size Bag_RedrawPocket_Hook, .-Bag_RedrawPocket_Hook
