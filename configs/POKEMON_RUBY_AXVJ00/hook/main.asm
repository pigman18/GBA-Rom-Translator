; =============================================================================
; AXVJ 补丁入口：main.asm / game.bin / game_addrs.asm
; =============================================================================
.gba
.thumb
.loadtable "./charmap.txt"
.create "./output.gba",0x08000000
.close
.open "./baserom.gba","./output.gba",0x08000000

.include "./game_addrs.asm"
.include "./out/game_syms.asm"

; 唯一启用 hook：ProcessCurrentChar 常规字形 → PrintNextChar（pokeruby 名）
.org ProcessCurrentChar_RegularGlyph
    ldr r0, =(PrintNextChar | 1)
    bx r0
.pool

; GetStringWidth：薄壳跳进 game.bin（避开旧 BL 超范围）
; 整函数入口替换；F9 按 CHS_GLYPH_ADVANCE_PX 计宽
.org GetStringWidth
    ldr r3, =(GetStringWidthChinese | 1)
    bx r3
.pool

; 战斗 HP 条昵称：遮罩 tile CpuSet 32B→24B（只开 nick，不开 Safari / PSS）
.include "./src/battle/UpdateNickInHealthbox/hook_origin.s"

.org GameBinAddresses
PrintNextChar:
.incbin "out/game.bin"

.include "./graphic/fonts.s"

.close
