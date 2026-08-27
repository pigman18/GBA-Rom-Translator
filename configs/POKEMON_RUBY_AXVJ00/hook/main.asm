; =============================================================================
; AXVJ 补丁入口：main.asm —— 纯装配骨架
; -----------------------------------------------------------------------------
; 结构分层：
;   [地址] game_addrs.asm            所有 equ 唯一事实来源
;   [符号] out/game_syms.asm         gcc 符号回填（build.bat / Makefile 生成）
;   [复杂钩] src/{域}/hooks_origin.s 订址桩；逻辑在 src/{域}/entry.s + *_hook.c
;                                    （gcc 编入 out/game.bin）
;   [文本引擎] src/text.c 只 hook PrintNextChar：入口 src/entry.s（EngineEntry）+
;                                    订址桩 src/text/hook_origin.s（P01）
;   [纯值]   patches/*.asm           就地指令/数据改写，无 C 依赖
;   [装载]   game.bin @0x08800000 + fonts + slot 表
; 补丁 ID 索引与逐条说明：docs/PATCHES_INVENTORY.md
; =============================================================================
.gba
.thumb
.loadtable "./charmap.txt"
.create "./output.gba",0x08000000
.close
.open "./baserom.gba","./output.gba",0x08000000

.include "./game_addrs.asm"
.include "./out/game_syms.asm"

; ---- 复杂钩子订址桩（JMP 类） ----
.include "./src/text/hook_origin.s"
.include "./src/map_name_popup/hooks_origin.s"
.include "./src/battle/hooks_origin.s"
.include "./src/pokedex/hooks_origin.s"
.include "./src/option/hooks_origin.s"

; ---- 纯值补丁（INS/DATA/NOP 类） ----
.include "./patches/player.asm"
.include "./patches/player_pc.asm"
.include "./patches/initialpoke.asm"
.include "./patches/pokedex.asm"
.include "./patches/start_menu.asm"

; ---- C 文本引擎（jp2chs 全面接管）/ 字库 / slot 表 ----
.org GameBinAddresses
JP2CHS_Entry:               ; = text/entry.s EngineEntry = 引擎入口跳板
.incbin "out/game.bin"

.include "./graphic/fonts.s"

; type=slot：JP hex → 中文 F9 流查找表（PrintNextChar 运行时拦截，v2 分桶 'SLT2'）
.include "./gen/translated_slot.asm"
