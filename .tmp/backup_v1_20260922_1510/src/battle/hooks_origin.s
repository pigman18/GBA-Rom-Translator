; =============================================================================
; [P03] 对战 HP 条昵称遮罩：缩短顶盖，且不饿死 OBJ 整列拷贝
; pokeruby: src/battle_interface.c UpdateNickInHealthbox()
; IDs: P03
; =============================================================================
;
; Font Patch 思路：chrome CpuSet 0x04000008（32B/8 行）→ 0x04000006（24B/6 行），
; 避免盖住 12px 汉字上沿（墨水约从 row6 起）。
;
; 日版陷阱：同一字面量池同时被
;   (1) 0x2B/2C/2D chrome 遮罩  (2) 列缓冲 → OBJ VRAM 的 CpuSet
; 共用。只改池 → OBJ 也只拷 24B/半列，row6..7（汉字顶）永远上不了精灵。
;
; 修法：
;   · 三处 nick 池保持 0x04000006（chrome LDR 仍指向它们）
;   · 四处 OBJ LDR 改指 ROM 内其它仍为 0x04000008 的字面量
;
; 池址：
;   Alt1  0x08041760    Alt2  0x08042620    主符号 0x08042C38
; =============================================================================

; --- chrome 用短长度（24B = row0..5）---
.org UpdateNickInHealthbox_Alt1_Pool
    .word 0x04000006

.org UpdateNickInHealthbox_Alt2_Pool
    .word 0x04000006

.org UpdateNickInHealthbox_Pool
    .word 0x04000006

; --- OBJ 拷贝改回满 32B：LDR 改指旁路 0x04000008 字面量 ---
; Alt1 @0x08041690  was ldr r2, [pool]  →  @0x080417B0
.org 0x08041690
    .halfword 0x4A47

; Alt1 @0x08041758  was ldr r2, [pool]  →  @0x080417B0
.org 0x08041758
    .halfword 0x4A15

; Alt2 @0x080425D6  was ldr r7, [pool]  →  @0x080426B8
.org 0x080425D6
    .halfword 0x4F38

; Main @0x08042BCA  was ldr r0, [pool]  →  @0x08042D04
.org 0x08042BCA
    .halfword 0x484E
