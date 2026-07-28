; =============================================================================
; armips only（不进 gcc）：对战 HP 条昵称遮罩 CpuSet 长度 32B → 24B
;
; Font Patch（美版）在 UpdateNickInHealthbox 共享池：
;   0x04000008（8 word = 32B）→ 0x04000006（6 word = 24B）
; 整 tile 拷 32B 会盖住 10/12px 汉字上半；增益版用 24B。
;
; 日版：禁止盲贴美版 +0x1EA / +0x228。
; GetHealthboxElementGfxPtr(0x2B/0x2C/0x2D) + CpuSet 三处平行 nick 遮罩：
;   Alt1  0x080415A0  pool 0x08041760
;   Alt2  0x08042408  pool 0x08042620
;   主符号 0x08042B14  pool 0x08042C38
; =============================================================================

.org UpdateNickInHealthbox_Alt1_Pool
    .word 0x04000006

.org UpdateNickInHealthbox_Alt2_Pool
    .word 0x04000006

.org UpdateNickInHealthbox_Pool
    .word 0x04000006
