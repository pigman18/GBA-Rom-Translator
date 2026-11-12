; =============================================================================
; src/text/hooks_origin.s — 文本引擎 ROM 订址桩（armips 专用，main.asm include）
; 逻辑侧: src/text/entry.s（EngineEntry 跳板）+ PrintNextChar_hook.c（串页渲染器）
; ID: P01（docs/PATCHES_INVENTORY.md）
;
; 2026-11-11 重写：
;   - 文件名按 README §3.2 与其他域统一为复数 hooks_origin.s（旧 hook_origin.s 作废）；
;   - 引擎改为纯函数 tile 网格：F7 00 统一协议、零运行时分配；
;     相关桩（P02/P04/P05/P24 等）早已移除，此处不再有第二处订址。
;
; 全 ROM 只此一处 hook：PrintNextChar@0x080032F8 整函数接管。
; 只盖 8B（ldr + bx + pool）；0x08003300 起的原指令保持原样，
; entry.s 的 PrintNextChar_Origin 回放序言后可续跑（当前引擎不调用，见设计 §5.1 D）。
; =============================================================================

; --- [P01] 全面接管：原生 PrintNextChar 整函数替换 ---
; pokeruby: src/text.c PrintNextChar()；AXVJ @0x080032F8（含 FA-FF 控制码跳表）。
; 原版字节: 70 b5 82 b0 04 1c ...（push {r4,r5,lr} / sub sp,#8 / adds r4,r0,#0）
; r0=win 按 AAPCS 原样进 C；r1 为 caller-saved 可作转跳暂存。
; 返回值契约：可印=1 / FF=0 / FA·FB·FD·FE=2 / FC=子结果。
; 回滚: 删除本节即恢复原版。
.org PrintNextChar
    ldr r1, =(JP2CHS_Entry | 1)
    bx r1
.pool
