@ =============================================================================
@ fixed_string entry：继续画面图鉴单位 → FixedString_Write（C）
@ 徽章单位在 hook_origin.s 原位跳过（不远跳）
@ =============================================================================

    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global ContinuePokedexUnit_Hook
    .thumb_func
    .type ContinuePokedexUnit_Hook, %function
    .extern FixedString_Write

@ Origin @ 0x08090FAA wrote ひき (1B 07 FF) at [r4].
ContinuePokedexUnit_Hook:
    push {lr}
    movs r0, #1                      @ FIXED_STR_CONTINUE_POKEDEX_UNIT
    adds r1, r4, #0
    bl FixedString_Write
    pop {r3}
    ldr r0, =0x08090FB7
    bx r0
    .pool
    .size ContinuePokedexUnit_Hook, .-ContinuePokedexUnit_Hook
