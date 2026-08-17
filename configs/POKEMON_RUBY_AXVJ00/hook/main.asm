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

; 等 A 箭头：FA/FB 不经 PrintNextChar；TILE_OFFSET 与 CURSOR 错位 → 双▼。
.org DrawInitialDownArrow
    ldr r3, =(WaitArrow_Prepare | 1)
    bx r3
.pool

; 初始宠 label 擦除：日版按假名宽度擦 left+8 列，中文名字(12px)比假名(8px)宽，
; 超出的右半 tile 没被 erase → 切 label 时残留右半碎字。
; 把 adds r2,#8（右边界=left+8）改成 movs r2,#29（右边界固定 29=菜单窗口最右列）。
; 屏上同时只显示一个 label，擦到窗口最右不会误伤其它 label。
.org 0x081053D0
    mov r2, 0x1D

; 图鉴条目屏分类名行：UnusedPrintMonName 右对齐到占位符宽度（中文 12px vs
; 问号 8px 覆盖不齐）。改为直接拼接「宝可梦」左对齐打印。
.org UnusedPrintMonName
    ldr r0, =(UnusedPrintMonName_Hook | 1)
    bx r0
.pool

; =============================================================================
; B06 初始宠 label 第一行「分类+宝可梦」栈溢出 → 宝可梦名重复打印
; -----------------------------------------------------------------------------
; CreateStarterPokemonLabel @0x081053A8 栈帧 sub sp,#0x20：
;   sp[0..15]=第一行 buffer，sp[16..31]=第二行 buffer。
; 第一行 = 颜色码(5)+分类假名(≤5)+「ポケモン」拷贝(5B)+FF，恰好 16B。
; 汉化把「ポケモン」→「宝可梦」=F9 00×3+FF=13B（指针 0x08105534 被 pointer_redirect
; 重定向到扩展区），但该函数是「读指针所指字节直接拷贝」，固定拷 5B：
;   a) 固定 5B 只拷到 f9 00 01 63 f9，第二组 F9 序列悬空，PrintNextChar 把
;      缓冲区外的字节当 F9 短语码去查表 → 随机乱码（14~16.png 字符乱飞）。
;   b) 若改成整串拷入，第一行膨胀到 5+5+13+1=24B，超出 16B 写进第二行 buffer，
;      打印第一行时吃掉第二行颜色码后把名字打出来 → 名字重复（5~13.png）。
; 修复：两件事必须同时做——
;   1) 栈帧 0x20→0x60，第二行 buffer 从 sp+0x10 移到 sp+0x30，两行各 48B 隔离；
;   2) 「ポケモン」拷贝从固定 5B 改为拷到 0xFF（上限 0x11），整串 F9 序列完整
;      落入第一行 buffer，其后 FF 让打印干净收尾，无悬空 F9、无溢出。
; =============================================================================
.org 0x081053B2
    sub sp, 0x60

.org 0x08105416
    add r1, sp, 0x30

.org 0x0810551C
    add sp, 0x60

; 0x0810544C：ポケモン拷贝循环（原固定 5B：cmp r7,#4 / bls）
; 替换为「拷到 0xFF，上限 0x11」，字节数与原循环一致（0x1A）。
.org 0x0810544C
StarterPokeCopyLoop:
    mov r0, sp
    add r1, r0, r4
    add r0, r7, r2
    ldrb r0, [r0, #0]
    strb r0, [r1, #0]
    cmp r0, #0xFF
    beq StarterPokeCopyDone
    add r7, #1
    add r4, #1
    cmp r7, #0x11
    bls StarterPokeCopyLoop
    nop
    nop
StarterPokeCopyDone:

; =============================================================================
; 图鉴列表页：名字列（NoXXX 与宝可梦名间距）。
; 唯一来源 DEX_NAME_COLUMN（game_addrs.asm），5 处 movr1 共用；原 0x17=23。
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

.org GameBinAddresses
PrintNextChar:
.incbin "out/game.bin"

.include "./graphic/fonts.s"

; type=hook：扩展区正文 + 指针槽重定向（由 meowth.pointer_redirect 生成）
.include "./gen/pointer_redirect.asm"

.close
