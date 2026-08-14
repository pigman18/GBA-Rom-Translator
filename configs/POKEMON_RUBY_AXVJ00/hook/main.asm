; =============================================================================
; AXVJ 补丁入口：main.asm / game.bin / game_addrs.asm
; pokeRS 算法 + F900/F980 通道（gcc → out/game.bin）
; =============================================================================
.gba
.thumb
.loadtable "./charmap.txt"
.create "./output.gba",0x08000000
.close
.open "./baserom.gba","./output.gba",0x08000000

.include "./game_addrs.asm"
.include "./out/game_syms.asm"

; 常规字形 → PrintNextChar（F9 00 / F9 80 + pokeRS 绘制）
.org ProcessCurrentChar_RegularGlyph
    ldr r0, =(PrintNextChar | 1)
    bx r0
.pool

; 战斗 HP 条昵称：遮罩 tile CpuSet 32B→24B（pokeRS / 增益版）
.include "./src/battle/UpdateNickInHealthbox_hook_origin.s"

; 地图名弹窗：跳过 StringLength pad + 二次 GetMapName(fill=10)，
; 直跳 MenuPrint。否则中文 F9 短语被 fill 顶出 → 白空格(Bug1)+重复(Bug2)。
.org DrawMapNamePopup_StringLength
    ldr r0, =(MapName_DisplayCellLength | 1)
    bx r0
.pool

.org GameBinAddresses
PrintNextChar:
.incbin "out/game.bin"

.include "./graphic/fonts.s"

; type=hook：扩展区正文 + 指针槽重定向（由 meowth.pointer_redirect 生成）
.include "./gen/pointer_redirect.asm"

.close
