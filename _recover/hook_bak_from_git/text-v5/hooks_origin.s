; =============================================================================
; text/hooks_origin.s — v5 文本引擎 ROM 订址桩（FontFuncTable 表项重定向）
; armips 专用（main.asm include），不进 gcc；
; 逻辑侧: src/text/fontfunc_hook.c（4 个 thunk + NativeDispatch）
; ID: P25（docs/PATCHES_INVENTORY.md）
; =============================================================================
; 官方 PrintNextChar 只拦 0xFA-0xFF 控制码，可印字符（含 0xF9）分发
; FontFuncTable[textMode](win, c)。4 个表项改指我方 thunk：
;   TranslateHandleChar（F9 协议/SLT2 slot 替换）未消费 → 尾调原生处理器。
; 恰 0x10 字节，止于二级 FontSubTable@0x081BB3BC（fontNum 0..6）——
; 二级表不触碰（tm1 的 font4 等宽路径仍走原生 FontType1Map）。
; v4 的 P01（PrintNextChar 整替换）随本补丁废止。
.org FontFuncTable
    .word FontFuncTm0_Hook | 1
    .word FontFuncTm1_Hook | 1
    .word FontFuncTm2_Hook | 1
    .word FontFuncTm3_Hook | 1
