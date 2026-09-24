; =============================================================================
; AXVJ 补丁入口：main.asm —— 纯装配骨架
; -----------------------------------------------------------------------------
; 结构分层：
;   [地址] game_addrs.asm            所有 equ 唯一事实来源
;   [符号] out/game_syms.asm         gcc 符号回填（build.bat / Makefile 生成）
;   [复杂钩] src/{域}/hooks_origin.s 订址桩；逻辑在 src/{域}/entry.s + *_hook.c
;                                    （gcc 编入 out/game.bin）
;   [文本引擎] v6：唯一 hook = PrintNextChar@0x080032F8（P01）→
;                                    entry.s EngineEntry → PrintNextChar_Hook；
;                                    FontFuncTable 不再重定向；
;                                    渲染件 src/text/text_render.c，
;                                    F9 协议 src/text/text_translater.c
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
; [P32] —— 🔴🔴 2026-09-21 **已停用**（保留文件以便快速回退，但不得再 include）
;
; 停用原因是**实机冷启动 A/B 实证**（不是推理）：
;   P32 把 0x080029E0「日文字形预取 worker」短接成 `movs r0,#1; bx lr`，
;   而该 worker 对 tm==1 的窗口做的事是**把整串字形的字模预画进
;   `tpl->tileData + start*32 + idx*64`（即该 charBlock 的低号段）**。
;   它不是「可选优化」，而是 tm1 的**唯一字模来源**：
;   tm1 的逐字处理器（FontSubTable）只写 tilemap，从不碰 VRAM。
;
;   于是「engine 自己画、不经我们 PrintNextChar」的那部分文字全部变空白。
;   实测（队伍页，冷启动 + .sav）：
;     · P32 开：BG0 cb1 非零 tile 158 个，tiles 112..131 全 0
;       ⇒ 血数字 `128／128`、等级 `Lv36` 全部消失（用户 2026-09-21 报的第 2 条）
;     · P32 关：BG0 cb1 非零 tile 370 个，map 与**原盘逐格一致**
;       ⇒ 数字全部回来，中文名照常
;     · 设置页（22 块，我们号最密的一页）P32 关/开**都正常** ⇒ 停用无副作用
;
;   为什么当初会加它：v21 时期我们的号池固定在 [0,384)，预取正好盖在上面。
;   v22 方案 H 已经改成「按位置散号 + 越界折叠」，不再有「固定池被盖」的问题；
;   而且预取只在窗口初始化时跑一次，我们的字在之后每帧重画，落笔顺序对我们有利。
;   ⇒ 结论：预取不再是污染源，反而是我们必须依赖的引擎行为。
;   原始头注（含逐指令依据）仍保留在 patches/prefetch_off.asm。
;
; .include "./patches/prefetch_off.asm"   ; ← 已停用，见上

; ---- C 文本引擎（v6 PrintNextChar）/ 字库 / slot 表 ----
.org GameBinAddresses
JP2CHS_Entry:               ; = EngineEntry（text/entry.s 必须 link 第一）
.incbin "out/game.bin"

.include "./graphic/fonts.s"

; type=slot：JP hex → 中文 F9 流查找表（PrintNextChar 运行时拦截，v2 分桶 'SLT2'）
.include "./gen/translated_slot.asm"
