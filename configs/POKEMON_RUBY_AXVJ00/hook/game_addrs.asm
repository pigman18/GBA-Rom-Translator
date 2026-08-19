; AXVJ (Pocket Monsters Ruby JP) — master address & constant file
; ROM SHA1: 5C5E546720300B99AE45D2AA35C646C8B8FF5C56
; Single source of truth for hook addresses. Referenced by:
;   - main.asm / src/*.s  (equ, via .include "./game_addrs.asm")
;   - game.h ADDR_*       (via scripts/gen_game_h_from_addrs.py, `; C:` markers)
; 2026-08 purged: only equ actually referenced by hook (asm .org/call or
; C game.h ADDR_*). Removed addresses → symbols/pokeruby_jp.sym UNVERIFIED.

; --- Core text printer ---
; ProcessCurrentChar ≈ pret/pokeruby PrintNextChar (src/text.c)
ProcessCurrentChar                     equ 0x080032F8
ProcessCurrentChar_RegularGlyph        equ 0x0800336E
CallViaR2                              equ 0x081B12DC  ; C: ADDR_CALL_VIA_R2
FontFuncTable                          equ 0x081BB3AC  ; C: ADDR_FONT_FUNC_TABLE

; --- Glyph draw / blit (C layer via ADDR_* in src/game.h) ---
CopyGlyph1bppTo4bpp                    equ 0x08003830  ; C: ADDR_COPY_GLYPH_1BPP_4BPP
CopyGlyph2bppTo4bpp                    equ 0x080038A0  ; C: ADDR_COPY_GLYPH_2BPP_4BPP
GetGlyphTilePointers                   equ 0x08003730  ; C: ADDR_GET_GLYPH_TILE_PTRS
UpdateTilemap                          equ 0x080036DC  ; C: ADDR_UPDATE_TILEMAP
; FA/FB → DrawInitialDownArrow：画等 A 的 ▼（再进 state 8/9）
DrawInitialDownArrow                   equ 0x08003F4C

; --- String util ---
StringLength                           equ 0x0800436C

; --- 图鉴分类名行（UnusedPrintMonName，参数 name/left/top）---
UnusedPrintMonName                     equ 0x0808DD60
; 图鉴「???」占位串（AC*5 + F9 80 03 + FA FF）
DexTextUnknownPoke                     equ 0x083E9688  ; C: ADDR_DEX_TEXT_UNKNOWN_POKE

; --- Menu (shop/bag InitMenu ▶) ---
Menu_PrintText                         equ 0x0806F16C  ; C: ADDR_MENU_PRINT_TEXT
DrawOptionMenuChoice                   equ 0x080889F0  ; 设置窗口选项绘制（dst[2]=style）

; --- 图鉴列表页名字列（唯一来源，C 里 DEX_NAME_COLUMN 同步此值）---
DEX_NAME_COLUMN                        equ 0x16

; --- Width / map-name popup ---
; GetGlyphWidth/GetStringWidth @ 0x4B1C/0x4CC0 曾为 proximity 错猜（无调用方）；勿再整函数替换。
; 日版 DrawMapNamePopup：StringLength 后仍 GetMapName(fill=10) 填 0x00；
; 钩 StringLength 位点并跳过 pad+二次 GetMapName → MenuPrint。
DrawMapNamePopup                       equ 0x0809F654
DrawMapNamePopup_StringLength          equ 0x0809F67E
; --- 扩展区 / game.bin 装入点 ---
GameBinAddresses                       equ 0x08800000  ; C: ADDR_GAME_BIN
; StyleLeft 表已移除（宝可梦名起笔左移 = hook 常量 CHS_NAME_PHRASE_LEFT）
; PhraseOffsets / PhraseTable：短语表固定 VMA（phrase_data.asm .org 标签同名）
; ⚠️ 勿命名为 PhraseOffsets/PhraseTable——与 phrase_data.asm 标签冲突。
PhraseOffsetsVMA                        equ 0x08810000  ; C: ADDR_PHRASE_OFFSETS
PhraseTableVMA                          equ 0x08820000  ; C: ADDR_PHRASE_TABLE
FontChsNormal                          equ 0x09000000  ; C: ADDR_FONT_CHS_NORMAL
; Sym punct: free ROM after Small; Font3 8x16 4bpp U+L (not 16x16 2bpp)
PokeRSFontChsSymAddress                equ 0x091E0000  ; C: ADDR_FONT_CHS_SYM
; EWRAM pitch slots (JP+CN share CHS pool; do not dual-path FontFunc):
;   ChsPitchCtrl  @ 0x0203FF80 (16B): cur, gen, pad[2], age[8]
;   ChineseTileState slots[8] @ 0x0203FF90 (64B)
ChsPitchCtrl                           equ 0x0203FF80  ; C: ADDR_CHS_PITCH_CTRL
ChsPitchSlots                          equ 0x0203FF90  ; C: ADDR_CHS_PITCH_SLOTS
; 遗留单槽（hook 未用，供 docs/config）
ChineseTileState                       equ 0x0203FFF8  ; C: ADDR_CHINESE_TILE_STATE
; DrawOptionMenuChoice 选中调色板覆盖（避开 FFF0/F7F8）
OptPaletteOverride                     equ 0x0203FFD0  ; C: ADDR_OPT_PALETTE_OVERRIDE
OptFgColor                             equ 0x0203FFD1  ; C: ADDR_OPT_FG_COLOR
; AXVJ gMenu @ IWRAM — InitMenu(left, top, n); Redraw prints ▶
GMenu                                  equ 0x03000618  ; C: ADDR_GMENU
; eBattleInterfaceGfxBuffer (AXVJ literal; docs/ref only — 门控 textMode==2)
BattleIfGfx                            equ 0x02020004  ; C: ADDR_BATTLE_IF_GFX

; --- Healthbox ---
; JP nick 遮罩：CpuSet 共享长度池 0x04000008→0x04000006（见 HookInOrigin/UpdateNickInHealthbox.s）
; 勿用美版 0x080451A0 / 错误 Δ 0x08045138（JP 上该址不是本函数）
UpdateNickInHealthbox                  equ 0x08042B14
UpdateNickInHealthbox_Pool             equ 0x08042C38
UpdateNickInHealthbox_Alt1_Pool        equ 0x08041760
UpdateNickInHealthbox_Alt2_Pool        equ 0x08042620

; --- HW / lib ---
CpuSet                                 equ 0x081B1294