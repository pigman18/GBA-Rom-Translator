.arm
GetWindowAttributeHook:
    push {r0-r3, r6, r12, lr}
    cmp r4, #WINDOW_WIDTH
    bne GetAttr_Restore
    ldrb r12, [r0, #WIN_FONTNUM]
    cmp r12, #3
    bne GetAttr_Restore
    ldrb r12, [r0, #0x02]
    cmp r12, #30
    bhi GetAttr_ReturnAsIs
    lsl r12, r12, #1
    str r12, [sp, #0]
    pop {r0-r3, r6, r12, lr}
    bx lr
GetAttr_ReturnAsIs:
    str r12, [sp, #0]
    pop {r0-r3, r6, r12, lr}
    bx lr
GetAttr_Restore:
    pop {r0-r3, r6, r12, lr}
    lsrs r5, r5, #0x18
    lsls r3, r3, #0x18
    lsrs r3, r3, #0x18
    lsls r1, r1, #0x18
    ldr r12, =GetWindowAttribute_Continue
    bx r12
.pool
