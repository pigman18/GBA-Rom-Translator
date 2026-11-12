; =============================================================================
; [P19~P23] 图鉴列表页名字列间距（纯值，5 处共用常量）
; pokeruby: src/pokedex.c 列表页 CreateMonName(0, col, row*2)
; 常量唯一来源: game_addrs.asm DEX_NAME_COLUMN（原 0x17=23）
; =============================================================================

.org 0x0808AA00
    mov r1, DEX_NAME_COLUMN

.org 0x0808AA24
    mov r1, DEX_NAME_COLUMN

.org 0x0808AB34
    mov r1, DEX_NAME_COLUMN

.org 0x0808ABDA
    mov r1, DEX_NAME_COLUMN

.org 0x0808ABFE
    mov r1, DEX_NAME_COLUMN

; =============================================================================
; [P24] 图鉴列表名字终止符：让拷贝循环把源串的 0xFF 一并写进栈缓冲
; -----------------------------------------------------------------------------
; CreateMonName @0x0808AD44（pokeruby src/pokedex.c 列表页名字列）原逻辑：
;     buf[r4] = src[r4];  r4++;
;     if (src[r4] == 0xFF) goto end;      <-- 只 break，不把 FF 写进 buf
;     if (r4 <= 0x17) goto loop;
;   end: Menu_PrintText(buf, left, top);
; 终止符靠 0x0808AD72 预置的 `strb 0xFF,[buf+5]` —— 日版 5 假名 = 5 字节，
; 刚好不覆盖它。译名是 F7 00 hi lo 4B/字，2 字就覆盖 buf[5]，4 字（16B）
; 之后整条流**没有终止符**：读穿 buf[16..23] 的 0x00 空格和 buf[24..31] 的
; 栈垃圾，把相邻的 FC/FC/FB 控制码与 D=2 红色填充字一起画出来。
; DIAG 实测：名字行只剩 3 个汉字 + 怪字 + 红填充字（docs §10 取证）。
;
; 修法：把 0x0808ADB2 的 `beq end`(0x0FD0) 改成 `nop`(0x46C0 = mov r8,r8)。
; 遇 FF 不再提前跳出，循环按既有 `cmp r4,#0x17 / bls` 继续，下一轮自然把
; src[r4] 的 FF 写进 buf[r4]；名字表槽尾部全是 FF，故 buf[名字末尾] 就是
; 正确的终止符。短名（2~3 字）同理，buf[8]/buf[12] 处终止。
; 破折号占位分支 (r5==0, 0x0808ADC0) 不经过此循环，仍用 buf[5] 的 FF，
; 不受影响。零新增 hook、零场景门控、零译名改动。
; =============================================================================
.org 0x0808ADB2
    .dh 0x46C0
