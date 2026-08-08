; AXVJ (Pocket Monsters Ruby JP) — master address & constant file
; ROM SHA1: 5C5E546720300B99AE45D2AA35C646C8B8FF5C56
; Pipeline auto-generates a different version at include/axvj_addrs.asm;
; this one at config root is included by main.asm and has everything.

; --- Core text printer ---
; ProcessCurrentChar ≈ pret/pokeruby PrintNextChar (src/text.c)
ProcessCurrentChar                     equ 0x080032F8
ProcessCurrentChar_RegularGlyph        equ 0x0800336E
InitTextPrinter                        equ 0x08002C68
RunTextPrinter                         equ 0x08002DE8
CallViaR2                              equ 0x081B12DC
FontFuncTable                          equ 0x081BB3AC

; --- Glyph draw / blit ---
DrawGlyph_Font0                        equ 0x08003520
DrawGlyph_Font0_Wrapper                equ 0x08003568
DrawGlyph_Font3_Wrapper                equ 0x08003494
CopyGlyph1bppTo4bpp                    equ 0x08003830
CopyGlyph2bppTo4bpp                    equ 0x080038A0
BlitGlyphTiles                         equ 0x08003630
GetGlyphTilePointers                   equ 0x08003730
UpdateTilemap                          equ 0x080036DC
GetCursorTilemapPointer                equ 0x08003708
GetWindowPaletteBits                   equ 0x08003728
GetBlankTileNum                        equ 0x080041BC
Text_ClearWindow                       equ 0x08003BA8

; --- String util ---
StringCopy                             equ 0x080042E8
StringAppend                           equ 0x08004308
StringLength                           equ 0x0800436C
StringExpandPlaceholders               equ 0x08004530

; --- Width / map-name popup ---
; GetGlyphWidth/GetStringWidth @ 0x4B1C/0x4CC0 曾为 proximity 错猜（无调用方）；勿再整函数替换。
; 日版 DrawMapNamePopup：StringLength 居中（10 半角格），BL 位点如下。
DrawMapNamePopup                       equ 0x0809F654
DrawMapNamePopup_StringLength          equ 0x0809F67E

; --- 扩展区 / game.bin 装入点 ---
GameBinAddresses                       equ 0x08800000  ; main.asm .incbin game.bin（≤0xF000）
HackFunctionAddresses                  equ GameBinAddresses  ; 旧名兼容
; StyleLeft：styles_data.asm（.org 0x0880F000）
; PhraseOffsets / PhraseTable：phrase_data.asm（.org 0x08810000 / 0x08820000）
FontChsNormal                          equ 0x09000000
FontChsSmall                           equ 0x09100000
PokeRSFontChsNormal                    equ FontChsNormal
PokeRSFontChsSmall                     equ FontChsSmall
; JP Font3 body (GetGlyphTilePointers type3) — do NOT overlay Latin Sym here
gFont3JapaneseGlyphs                   equ 0x081B6D2C
; Sym punct: free ROM after Small; Font3 8x16 4bpp U+L (not 16x16 2bpp)
PokeRSFontChsSymAddress                equ 0x091E0000
; IWRAM ChineseTileState @ 0x0203FFF8 (8B):
; +0 char_base +1 write_op +2 base_tx +3 last_adv +4 pitch_key(u16) +6 chs_px(u16)
ChineseTileState                       equ 0x0203FFF8
ChineseTileCursor                      equ 0x0203FFFC
CHS_ESCAPE                             equ 0xF9

; --- Healthbox ---
; JP nick 遮罩：CpuSet 共享长度池 0x04000008→0x04000006（见 HookInOrigin/UpdateNickInHealthbox.s）
; 勿用美版 0x080451A0 / 错误 Δ 0x08045138（JP 上该址不是本函数）
UpdateNickInHealthbox                  equ 0x08042B14
UpdateNickInHealthbox_Alt1             equ 0x080415A0
UpdateNickInHealthbox_Alt2             equ 0x08042408
UpdateNickInHealthbox_Pool             equ 0x08042C38
UpdateNickInHealthbox_Alt1_Pool        equ 0x08041760
UpdateNickInHealthbox_Alt2_Pool        equ 0x08042620
; Safari（本轮不启用；址仍为待核猜测）
UpdateSafariBallsTextInHealthbox       equ 0x08045848
UpdateLeftNoOfBallsTextOnHealthbox     equ 0x08045930

; --- Battle UI / Storage (TODO GDB: Δ=-0x68 from US) ---
sub_8097F58                            equ 0x08097EF0
PrintDisplayMonInfo                    equ 0x08098188

; --- Battle text pointers (TODO GDB: need JP offsets) ---
BattleText_SafariBalls                 equ 0x08400dd6
BattleText_SafariBallsLeft             equ 0x08400de6
BattleText_HighlightRed                equ 0x08400df0

; --- Graphic (TODO GDB: need JP offsets) ---
gMiscBlank_Gfx                         equ 0x082089dc
gPSSMenuHeader_Tilemap                 equ 0x08e8e128

; --- HW / lib (TODO GDB: need JP offsets) ---
CpuSet                                 equ 0x081e07ec
GetBattlerPosition                     equ 0x08078828

; --- Window attribute ---
GetWindowAttribute                     equ 0x0800414C
GetWindowAttribute_Continue            equ 0x08004154 | 1
WINDOW_WIDTH                           equ 1

; --- Font constants ---
FONT_NORMAL_UNSHADOWED                 equ 0
FONT_SMALL_UNSHADOWED                  equ 1
FONT_SMALL_COPY_UNSHADOWED             equ 2
FONT_NORMAL_SHADOWED                   equ 3
FONT_SMALL_SHADOWED                    equ 4
FONT_SMALL_COPY_SHADOWED               equ 5
FONT_BRAILLE                           equ 6
LANGUAGE_JAPANESE                      equ 1
LANGUAGE_ENGLISH                       equ 2

; --- Window / TextPrinter field offsets (JP RS layout) ---
WIN_TEMPLATE                           equ 0x00
WIN_STATE                              equ 0x04
WIN_FONTNUM                            equ 0x0A
WIN_COLOR_B                            equ 0x0B
WIN_COLOR_C                            equ 0x0C
WIN_COLOR_D                            equ 0x0D
WIN_COLOR_E                            equ 0x0E
WIN_PALETTE                            equ 0x0F
WIN_TEXT_PTR                           equ 0x10
WIN_TEXT_INDEX                         equ 0x14
WIN_TILE_BASE                          equ 0x16
WIN_TILE_OFFSET                        equ 0x18
WIN_CURSOR_X                           equ 0x1A
WIN_CURSOR_TILE_X                      equ 0x1B
WIN_CURSOR_Y                           equ 0x1C
WIN_CURSOR_TILE_Y                      equ 0x1D
