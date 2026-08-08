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

; 地图名弹窗：日版用 StringLength（字节数）按 10 格居中，不是 GetStringWidth。
; F9 地点名槽仅 4B，会左侧空格顶满、右侧溢出 → 改为按绘制像素折算格数。
; 旧 GetStringWidth@0x4CC0 为错址（无 BL，且破坏指针表指向的真函数），已拆除。
.org DrawMapNamePopup_StringLength
    ldr r3, =(MapName_DisplayCellLength | 1)
    bx r3
.pool

; 战斗 HP 条昵称：遮罩 tile CpuSet 32B→24B（只开 nick，不开 Safari / PSS）
.include "./src/battle/UpdateNickInHealthbox/hook_origin.s"

; 继续画面单位：ひき/こ → C FixedString（固定译表，非 texts.json）
.include "./src/ui/fixed_string/hook_origin.s"

.org GameBinAddresses
PrintNextChar:
.incbin "out/game.bin"

.include "./graphic/fonts.s"

; type=hook：扩展区正文 + 指针槽重定向（由 meowth.pointer_redirect 生成）
.include "./gen/pointer_redirect.asm"

.close
