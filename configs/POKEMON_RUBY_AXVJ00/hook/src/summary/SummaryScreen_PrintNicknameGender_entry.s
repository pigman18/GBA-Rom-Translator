@ game.bin: r0=speciesName, r1=mon → 印 ♂/♀ @ (4+ceil(width/8), 14)
    .cpu arm7tdmi
    .syntax unified
    .thumb
    .text
    .align 2

    .global SummaryScreen_NameLayoutTiles_Hook
    .thumb_func
    .type SummaryScreen_NameLayoutTiles_Hook, %function
    .extern SummaryScreen_NameLayoutTiles_hook_C

SummaryScreen_NameLayoutTiles_Hook:
    push {lr}
    bl SummaryScreen_NameLayoutTiles_hook_C
    pop {r1}
    bx r1
    .size SummaryScreen_NameLayoutTiles_Hook, .-SummaryScreen_NameLayoutTiles_Hook
