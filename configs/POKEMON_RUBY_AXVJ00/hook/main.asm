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

; 地图名弹窗：日版 StringLength 后仍 GetMapName(fill=10) 填 0x00。
; F9 槽 4B → 左/尾空格 + Mode2 双计 → 白边顶框。钩掉后直跳 MenuPrint。
; 旧 GetStringWidth@0x4CC0 为错址，已拆除。
.org DrawMapNamePopup_StringLength
    ldr r3, =(MapName_DisplayCellLength | 1)
    bx r3
.pool

; 等 A 箭头：FA/FB 不经 PrintNextChar；TILE_OFFSET 与 CURSOR 错位 → 双▼。
.org DrawInitialDownArrow
    ldr r3, =(WaitArrow_Prepare | 1)
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
