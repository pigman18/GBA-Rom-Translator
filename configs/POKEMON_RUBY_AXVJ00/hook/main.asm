; =============================================================================
; AXVJ 补丁入口：main.asm —— 纯装配骨架
; -----------------------------------------------------------------------------
; 结构分层：
;   [地址] game_addrs.asm            所有 equ 唯一事实来源
;   [符号] out/game_syms.asm         gcc 符号回填（build.bat / Makefile 生成）
;   [复杂钩] src/{域}/hooks_origin.s 订址桩；逻辑在 src/{域}/entry.s + *_hook.c
;                                    （gcc 编入 out/game.bin）
;   [文本引擎] src/text/ 三件套：entry.s（EngineEntry，game.bin 起点）+
;                                PrintNextChar_hook.c（纯函数 tile 网格渲染器）+
;                                hooks_origin.s（P01 订址桩，只 hook PrintNextChar）
;              tile = TILE_BASE+(row&7)*62+col*2，字库 0x09000000 由 font_patch
;              装入；构建期零页表、零 PHYS 池，见 docs/DESIGN_TEXT_12PX_GRID.md
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
.include "./src/text/hooks_origin.s"
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

; type=slot：JP hex → 中文流查找表（PrintNextChar 运行时拦截；历史桩）
.include "./gen/translated_slot.asm"
; 串页方案已整体退役：不建页表、不后置烙入、不 include 任何 text_page 产物。
; armips 只装 main.asm include 的桩 / 纯值补丁 / game.bin / 字库 / slot 表。
