@ =============================================================================
@ game.bin: UpdateNickInHealthbox helpers (pools patched in *_hook_origin.s)
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

HealthboxNickCpusetCtrl_Entry:
    push {lr}
    bl HealthboxNickCpusetCtrl
    pop {r1}
    bx r1
    .size HealthboxNickCpusetCtrl_Entry, .-HealthboxNickCpusetCtrl_Entry
