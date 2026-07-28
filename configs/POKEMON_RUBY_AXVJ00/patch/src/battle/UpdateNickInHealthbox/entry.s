@ =============================================================================
@ game.bin：UpdateNickInHealthbox 域入口（常量助手；原盘池见 hook_origin.s）
@ =============================================================================

    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global HealthboxNickCpusetCtrl_Entry
    .thumb_func
    .type HealthboxNickCpusetCtrl_Entry, %function
    .extern HealthboxNickCpusetCtrl

@ Thin export so the C unit is always linked (map / future BL from origin).
HealthboxNickCpusetCtrl_Entry:
    push {lr}
    bl HealthboxNickCpusetCtrl
    pop {r1}
    bx r1
    .size HealthboxNickCpusetCtrl_Entry, .-HealthboxNickCpusetCtrl_Entry
