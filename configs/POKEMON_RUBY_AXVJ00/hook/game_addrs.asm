; AXVJ (Pocket Monsters Ruby JP) — master address & constant file
; ROM SHA1: 5C5E546720300B99AE45D2AA35C646C8B8FF5C56
; Single source of truth for hook addresses. Referenced by:
;   - main.asm / src/*.s  (equ, via .include "./game_addrs.asm")
;   - game.h ADDR_*       (via scripts/gen_game_h_from_addrs.py, `; C:` markers)
; 2026-08 purged: only equ actually referenced by hook (asm .org/call or
; C game.h ADDR_*). Removed addresses → symbols/pokeruby_jp.sym UNVERIFIED.

; --- Core text printer ---
; PrintNextChar ≈ pret/pokeruby PrintNextChar (src/text.c)；P01 订其入口整函数替换
PrintNextChar                          equ 0x080032F8
; InitTextPrinter：文本块开始（r0=win, r1=text, r2=tile_base, r3=cur_x,
; 第5参数 cur_y @[sp+0x18]，入口已 push {r4,r5,r6,lr}+{r5,r6} 共 6 寄存器）。
; P0x 订其入口 8B（B570 464E 4645 B460）→ 块边界钩子，复位 ChsPhase 相位。
InitTextPrinter                        equ 0x08002C68  ; C: ADDR_INIT_TEXT_PRINTER
TilePtrTm3                             equ 0x080034E0  ; C: ADDR_TILE_PTR_TM3
CallViaR2                              equ 0x081B12DC  ; C: ADDR_CALL_VIA_R2
FontFuncTable                          equ 0x081BB3AC  ; C: ADDR_FONT_FUNC_TABLE

; --- Glyph draw / blit (C layer via ADDR_* in src/game.h) ---
CopyGlyph1bppTo4bpp                    equ 0x08003830  ; C: ADDR_COPY_GLYPH_1BPP_4BPP
CopyGlyph2bppTo4bpp                    equ 0x080038A0  ; C: ADDR_COPY_GLYPH_2BPP_4BPP
GetGlyphTilePointers                   equ 0x08003730  ; C: ADDR_GET_GLYPH_TILE_PTRS
UpdateTilemap                          equ 0x080036DC  ; C: ADDR_UPDATE_TILEMAP
; pokeruby WriteGlyphTilemap 内调 GetCursorTilemapPointer；日版同构独立函数：
;   r0=win → r0=&tilemap[((CY+TY)<<5)+(CX+TX)]（×2 字节）
GetCursorTilemapPointer                equ 0x08003708  ; C: ADDR_GET_CURSOR_TILEMAP_PTR
; 原生 tm1 等宽打印（FontFuncTable[1] @0x081BB3AC[1]）：FontSubTable[fontNum]
; 写预渲染字体 tile 表项 + [win+0x1B](cursorTileX)+=1。PCS 字形分发专用。
PrintGlyph_TextMode1_Origin            equ 0x0800360C  ; C: ADDR_PRINT_GLYPH_TM1_ORIGIN
; --- v5 FontFuncTable 原生处理器（2026-08-31 反汇编实证，tail-call 目标）---
; FontFuncTable@0x081BB3AC 共 4 项（thumb 位已置）：
;   [0]=tm0 0x08003569 [1]=tm1 0x0800360D [2]=tm2 0x0800338D [3]=tm3 0x08003495
;   二级 FontSubTable@0x081BB3BC（fontNum 0..6，7 项）。
; tm0 处理器：blit@tileData[(TILE_BASE+TILE_OFFSET)*32]（8px 列对）
;   → UpdateTilemap(upper, upper|0x10000)（写 tilemap 列 left+cursorTileX，
;   不推进任何游标）→ TILE_OFFSET+=2、cursorTileX+=1。
; tm2/tm3 处理器：2D(30 列/行)布局，画后 cursorTileX+=1。
FontFuncTm0_Origin                     equ 0x08003568  ; C: ADDR_FONT_FUNC_TM0_ORIGIN
FontFuncTm2_Origin                     equ 0x0800338C  ; C: ADDR_FONT_FUNC_TM2_ORIGIN
FontFuncTm3_Origin                     equ 0x08003494  ; C: ADDR_FONT_FUNC_TM3_ORIGIN
; 分区器（多帧字库加载 worker，(tpl, startOffset, glyphIdx)——gdb 采集 2656 命中
; 实证 JP 与美版同址；窗体初始化=旧文本作废=CHS 页游标复位点）。
InitWindowTileData                     equ 0x08002A50  ; C: ADDR_INIT_WINDOW_TILE_DATA
; FA/FB → DrawInitialDownArrow：画等 A 的 ▼（再进 state 8/9）
DrawInitialDownArrow                   equ 0x08003F4C  ; C: ADDR_DRAW_INITIAL_DOWN_ARROW
; P05 桩已折入 text.c static DrawInitialDownArrow（2026-08-24，入口不再订址）：
; 相位同步后尾跳原版主体延续点（原跳板 ldr r3,=0x08003DAD 同源；equ 取偶址）。
DrawInitialDownArrow_Body              equ 0x08003DAC  ; C: ADDR_DRAW_INITIAL_DOWN_ARROW_BODY

; --- text_jp2chs.c 全面接管所需的其余原生态（2026-08-23 反汇编定案） ---
Text_ClearWindow                       equ 0x08003BA8  ; C: ADDR_TEXT_CLEAR_WINDOW
PlayBGM                                equ 0x080724AC  ; C: ADDR_PLAY_BGM
PlaySE                                 equ 0x080724CC  ; C: ADDR_PLAY_SE

; --- String util ---
StringLength                           equ 0x0800436C
; GetGlyphWidth/GetStringWidth：AXVJ 无原生函数，勿再订址（2026-08-22 反汇编定论）
; - 0x08004228 实为 {u32,u32} 表查映射（表@0x081BB8D4，6 callers），非宽度；
; - 0x08004530 实为 FA~FF 控制码字符串展开复制（125 callers），非宽度；
; - 日版打印步进由 FontFuncTable 各处理器硬编码（FontFunc[0]@0x08003568 画后 [win+0x18]+=2）；
; - 全 ROM 无 FC 控制码 switch 比较链、无 cmp#0x16 的 GetExtCtrlCodeLength 特征；
; - 美版才有（US=0x080048E8/0x08004BCC，pokeRS 挂 +2/+0x100）；中文宽度由 PrintNextChar_C 自管。

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
; 宽度函数定论见上方 String util 节注释（0x4B1C/0x4CC0 亦为 proximity 错猜）。
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
; 8px 小汉库（meowth 管线生成，与 Normal 同 128B/字 容器；队伍名等小字窗使用）
FontChsSmall                           equ 0x09100000  ; C: ADDR_FONT_CHS_SMALL
; FontFunc[1] 二级分发表 / font1/4 配对表（文档参考）
FontSubTable                           equ 0x081BB3BC  ; C: ADDR_FONT_SUBTABLE
FontType1Map                           equ 0x081B34A8  ; C: ADDR_FONT_TYPE1_MAP
; Sym punct: free ROM after Small; Font3 8x16 4bpp U+L (not 16x16 2bpp)
PokeRSFontChsSymAddress                equ 0x091E0000  ; C: ADDR_FONT_CHS_SYM
; SlotTable: type=slot 查找表（JP hex → 中文 F9 流，PrintNextChar 运行时拦截）
SlotTableVMA                         equ 0x09EA0000  ; C: ADDR_SLOT_TABLE
; tm1 中文行 tile 分配：图鉴列表窗口模板（tile_alloc 配置表键，v4 期 gdb 实证）：
;   InitWindowTileData 预渲染占 tile 1..512；初始 tilemap 最大引用 254；
;   tile 513..1023 全程无引用 → 513 起 16 slot × 24 tile 为验证空闲区。
DexListWindowTemplate                 equ 0x081BB784  ; C: ADDR_TPL_DEX_LIST
; FD 占位符官方展开对（2026-08-29 反汇编实证）：
;   RESOLVER(id≤13 查 0x081BBAC8 函数表，>13 自带分支) → 返回变量串指针
;   SUBPRINT(win, str) = 官方内联子打印：换 text/index 跑快径循环打完整串后恢复
FdResolver                            equ 0x080046D4  ; C: ADDR_FD_RESOLVER
FdSubprint                            equ 0x08002DB4  ; C: ADDR_FD_SUBPRINT
; EWRAM pitch slots (JP+CN share CHS pool; do not dual-path FontFunc):
;   ChsPitchCtrl  @ 0x0203FF80 (16B): cur, gen, pad[2], age[8]
;   ChineseTileState slots[8] @ 0x0203FF90 (64B)
ChsPitchCtrl                           equ 0x0203FF80  ; C: ADDR_CHS_PITCH_CTRL
ChsPitchSlots                          equ 0x0203FF90  ; C: ADDR_CHS_PITCH_SLOTS
; 遗留单槽（hook 未用，供 docs/config）；2026-08-23 起复用为首字存 EWRAM 变量：
;   mode1 动态 tile 分配游标（text_jp2chs AllocGlyphTiles）——引擎静态变量会落
;   BSS，而 game.bin 无运行时加载器（写 ROM 被忽略/读为垃圾），必须放 EWRAM。
ChineseTileState                       equ 0x0203FFF8  ; C: ADDR_GLYPH_ALLOC_NEXT
; CHS scratch 页游标表（2026-08-25）：{u16 tilemap_lo, u16 cursor} × 8。
; 扫描实证 0x0203FFD2-0x0203FFF7 无游戏字面量引用（FFD0/D1 为调色板覆盖变量）。
GlyphPageCurTab                        equ 0x0203FFD2  ; C: ADDR_GLYPH_PAGE_CURTAB
; DrawOptionMenuChoice 选中调色板覆盖（避开 FFF0/F7F8）
OptPaletteOverride                     equ 0x0203FFD0  ; C: ADDR_OPT_PALETTE_OVERRIDE
OptFgColor                             equ 0x0203FFD1  ; C: ADDR_OPT_FG_COLOR
; AXVJ gMenu @ IWRAM — InitMenu(left, top, n); Redraw prints ▶
GMenu                                  equ 0x03000618  ; C: ADDR_GMENU
; eBattleInterfaceGfxBuffer (AXVJ literal; docs/ref only — 门控 textMode==2)
BattleIfGfx                            equ 0x02020004  ; C: ADDR_BATTLE_IF_GFX

; --- Healthbox ---
; JP nick 遮罩：池→0x04000006（chrome）；OBJ LDR 旁路仍用 0x04000008（见 battle/hooks_origin.s）
; 勿用美版 0x080451A0 / 错误 Δ 0x08045138（JP 上该址不是本函数）
UpdateNickInHealthbox                  equ 0x08042B14
UpdateNickInHealthbox_Pool             equ 0x08042C38
UpdateNickInHealthbox_Alt1_Pool        equ 0x08041760
UpdateNickInHealthbox_Alt2_Pool        equ 0x08042620

; --- HW / lib ---
CpuSet                                 equ 0x081B1294