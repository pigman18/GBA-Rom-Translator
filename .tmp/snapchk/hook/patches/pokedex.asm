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
