@ game.bin entry for CreateMonName hook (long jump from ROM).
    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified
    .global CreateMonName_Entry
    .thumb_func
    .type CreateMonName_Entry, %function
    .extern CreateMonName_Chinese

CreateMonName_Entry:
    push {lr}
    bl CreateMonName_Chinese
    pop {r1}
    bx r1
    .size CreateMonName_Entry, .-CreateMonName_Entry
