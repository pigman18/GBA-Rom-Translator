#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_v19.py — v19：LZ77→VRAM 装载总闸（常规 UI 的收敛层）

背景（用户指令）：
  「接管的 UI 目前好像只有对话框那种 UI，常规 UI 都没接管到，估计的研读一下
   pokeruby，然后参考获取其他 hook 点」
  「不需要单一 hook 点啊，本来就是多个点申请 tile」

调研结论（本脚本落地的依据，全部反汇编实证）：
  · 常规 UI（队伍菜单 / 宝可梦信息页 / 领航员 / PC 箱子 / 简易聊天）的**图形**
    统统经 BIOS `LZ77UnCompVram` 解压进 VRAM：
        LZ77UnCompVram @0x081B1298 = `12df 7047` = `svc 0x12 ; bx lr`
        LZ77UnCompWram @0x081B129C = `11df 7047` = `svc 0x11 ; bx lr`
    `bl 0x081B1298` 全盘 **118 个**（`bl 0x081B129C` 42 个）。
  · 紧邻的 0x081B12A0 / 0x081B12A4（svc 0x0F / 0x15）各被 5 / 13 处调用
    ⇒ **不能吃**，只能吃 0x081B1298..0x081B129F 这 8 字节。
  · 两种 SWI 解出的**字节内容完全一致**，只差写粒度（VRAM 必须半字写）
    ⇒ 桩吃掉两个入口、由跳板按 dst 分派 SWI：**字节级永远正确**。
  · 只把**图形（tile data）清成 0** 就够：UI 的 tilemap 就算照写，
    也只会指向空砖 ⇒ 屏幕上自然没有内容（不必再逐个门控 tilemap 路径）。

改动 7 个文件：
  1. hook/game_addrs.asm                  + LZ77UnCompVram equ（唯一事实来源）
  2. hook/src/text/hooks_origin.s         + 8B「不碰栈」纯跳转桩 @LZ77UnCompVram
  3. hook/src/text/entry.s                + V19LzGate_Hook（跳板）
  4. hook/include/lz_gate.h               （新）
  5. hook/src/text/lz_gate.c              （新）
  6. hook/build_sh_equiv.sh               + 编译/链接/符号表
  7. hook/build.bat                       + 同上

用法：python scripts/apply_v19.py
"""
from __future__ import annotations

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook")

ADDRS = os.path.join(HOOK, "game_addrs.asm")
STUBS = os.path.join(HOOK, "src", "text", "hooks_origin.s")
ENTRY = os.path.join(HOOK, "src", "text", "entry.s")
HDR = os.path.join(HOOK, "include", "lz_gate.h")
SRC = os.path.join(HOOK, "src", "text", "lz_gate.c")
SH = os.path.join(HOOK, "build_sh_equiv.sh")
BAT = os.path.join(HOOK, "build.bat")


def load(path: str):
    raw = io.open(path, "rb").read()
    crlf = b"\r\n" in raw
    return raw.decode("utf-8").replace("\r\n", "\n"), crlf


def save(path: str, text: str, crlf: bool):
    out = text.replace("\n", "\r\n") if crlf else text
    io.open(path, "wb").write(out.encode("utf-8"))


def rep(text: str, old: str, new: str, tag: str) -> str:
    n = text.count(old)
    assert n == 1, "[%s] count=%d（期望 1）" % (tag, n)
    return text.replace(old, new)


# ---------------------------------------------------------------- 文本块
ADDRS_BLOCK = """
; --- [v19] LZ77→VRAM 装载总闸（2026-09-12）----------------------------------
; `LZ77UnCompVram` @0x081B1298 = `12df 7047` = `svc 0x12 ; bx lr`（BIOS 蹦床）
; `LZ77UnCompWram` @0x081B129C = `11df 7047` = `svc 0x11 ; bx lr`
; 全盘 `bl 0x081B1298` **118 处**（`bl 0x081B129C` 42 处）—— 常规 UI
; （队伍菜单 / 信息页 / 领航员 / PC 箱子 / 简易聊天）的**图形**统统从这里
; 解压进 VRAM。这是「多个申请点」背后的收敛层。
; ⚠ 紧邻的 0x081B12A0(svc 0x0F) / 0x081B12A4(svc 0x15) 各被 5 / 13 处调用
;   ⇒ 桩只能吃 0x081B1298..0x081B129F 这 8 字节（两个入口一起）。
;   两种 SWI 解出的**字节内容一致**，只差写粒度 ⇒ 跳板按 dst 分派，永远正确。
LZ77UnCompVram                         equ 0x081B1298
"""

STUB_BLOCK = """
; =============================================================================
; [v19] LZ77→VRAM 装载总闸 —— 覆盖 0x081B1298..0x081B129F（2026-09-12）
; -----------------------------------------------------------------------------
; 覆盖掉的是两条 4 字节 BIOS 蹦床：
;   0x081B1298: 12df 7047   svc 0x12 / bx lr   = LZ77UnCompVram
;   0x081B129C: 11df 7047   svc 0x11 / bx lr   = LZ77UnCompWram
; 桩型 = **8B「不碰栈」纯跳转**（ldr r3 / bx r3 / .pool），与原体零栈账：
;   原体两条蹦床都不碰栈、不改 lr（`svc` 只写 r0、`bx lr` 直接回调用者）
;   ⇒ 入口 lr = 调用者返回地址，桩不碰它 ⇒ 跳板可以 `pop {r4, pc}` 直接返回。
; 为什么可以两个入口共用一条跳板：两种 SWI 解压出的**字节内容完全相同**，
;   差别只在写粒度（VRAM 只能半字写）⇒ 跳板按 dst 是否在 VRAM 分派
;   svc 0x12 / svc 0x11，**字节级永远正确**，没有任何调用方会被改变行为。
; =============================================================================

.org LZ77UnCompVram
    ldr  r3, =(V19LzGate_Hook | 1)
    bx   r3
.pool
"""

ENTRY_BLOCK = """@ =============================================================================
@ [v19] LZ77→VRAM 装载总闸（2026-09-12）
@ -----------------------------------------------------------------------------
@ 为什么在这：常规 UI（队伍菜单 / 宝可梦信息页 / 领航员 / PC 箱子 / 简易聊天）
@ 的**图形**不经过窗口分配器 —— 它们由 BIOS `LZ77UnCompVram`(0x081B1298,
@ `svc 0x12; bx lr`) 解压到**固定 VRAM 地址**，全盘 118 个调用点。
@ 用户判定「常规 UI 都没接管到」成立；这一层就是那些「多个申请点」的收敛层。
@
@ 语义（与文字 / 框 / 底色完全一致）：
@   V18_UI_ON == 1 ⇒ 照官方解压（只按 dst 分派 SWI）；
@   V18_UI_ON == 0 ⇒ 把**本应写入的那整块**清成 0 ⇒ 屏幕无内容可显示。
@   🔴 只清「图形」就够：UI 的 tilemap 照样写，但只会指向空砖。
@
@ 桩型 = 8B「不碰栈」纯跳转（覆盖两个入口，见 hooks_origin.s）：
@   0x081B1298 = LZ77UnCompVram / 0x081B129C = LZ77UnCompWram。
@   原体两条蹦床都**不 push、不改 lr** ⇒ 入口 lr = 调用者返回地址。
@   本跳板自己 push {r4,lr} 保住它，返回时 `pop {r4, pc}` 弹回调用者，栈净 0。
@ =============================================================================
    .global V19LzGate_Hook
    .thumb_func
    .type V19LzGate_Hook, %function
    .extern v19_lz_gate_C
V19LzGate_Hook:
    push    {r4, lr}                   @ 保 lr（原体没有 push，lr 就是调用者的返回地址）
    push    {r0, r1}                   @ 保参数：r0=源 r1=目的（C 会砸）
    bl      v19_lz_gate_C              @ → 0=清成空白 / 1=svc 0x12 / 2=svc 0x11
    adds    r4, r0, #0                 @ r4 = 判定
    pop     {r0, r1}                   @ 还原参数（下面真正的 SWI 要用）
    cmp     r4, #0
    beq     LzGate_Blank
    cmp     r4, #2
    beq     LzGate_Wram
    svc     #0x12                      @ 官方 LZ77UnCompVram（半字写，目标在 VRAM）
    pop     {r4, pc}
LzGate_Wram:
    svc     #0x11                      @ 官方 LZ77UnCompWram（字节写，目标不在 VRAM）
    pop     {r4, pc}
LzGate_Blank:
    movs    r0, #0                     @ 目标块已清成 0 ⇒ 不解压，屏幕无内容
    pop     {r4, pc}                   @ 栈上正是入口那份 lr = 调用者返回地址
    .size V19LzGate_Hook, .-V19LzGate_Hook
    .pool

"""

HDR_TEXT = """/* ============================================================================
 * lz_gate.h — v19（2026-09-12）：LZ77→VRAM 装载总闸
 *
 * 「常规 UI 没接管到」的解法。那些 UI（队伍菜单 / 宝可梦信息页 / 领航员 /
 * PC 箱子 / 简易聊天）的**图形**不走窗口分配器，而是由 BIOS
 * `LZ77UnCompVram` @0x081B1298（`svc 0x12; bx lr`）解压到**固定 VRAM 地址**
 * —— 全盘 118 个调用点。这一层就是那些「多个申请点」的收敛层。
 *
 * 返回给跳板（entry.s 的 V19LzGate_Hook）的三态：
 *   0 = 目标块已清成 0，**不要再解压**（UI 关 / 屏幕应当空白）；
 *   1 = 走 `svc 0x12`（LZ77UnCompVram，目标在 VRAM，必须半字写）；
 *   2 = 走 `svc 0x11`（LZ77UnCompWram，目标不在 VRAM）。
 *
 * 🔴 为什么 1/2 由 dst 决定而不是由「进的是哪个入口」决定：
 *   桩一次吃掉两个入口（0x081B1298 / 0x081B129C，8 字节），跳板看不到是谁调的。
 *   但两个 SWI 解压出的**字节内容完全一致**，差别只在写粒度，而写粒度只对
 *   VRAM 有约束 ⇒ 「dst 在 VRAM 用 0x12、否则 0x11」在**字节级永远正确**。
 * ==========================================================================*/
#ifndef LZ_GATE_H
#define LZ_GATE_H

#include <stdint.h>

/* r0=源（LZ77 压缩数据） r1=目的 —— 与 BIOS `LZ77UnCompVram` 同签名。 */
int v19_lz_gate_C(uint32_t src, uint32_t dst);

#endif /* LZ_GATE_H */
"""

SRC_TEXT = """/* ============================================================================
 * lz_gate.c — v19（2026-09-12）：LZ77→VRAM 装载总闸
 *   被 entry.s 的 V19LzGate_Hook 调用（桩在 hooks_origin.s @0x081B1298）。
 *
 * 常规 UI 的图形全部经 BIOS `LZ77UnCompVram` 解压进 VRAM —— 118 个调用点。
 * 把它闸住，比逐个去门控每个 UI 的装载点（队伍菜单 DMA / 信息页 blob /
 * 领航员 sub_8095C8C）少得多、也不会漏。
 *
 * 🔴 为什么只清「图形」就够（不必再门控 tilemap）：
 *   UI 的 tilemap 写在别处（静态 blob / 常量表），但它引用的是**砖号**。
 *   砖号指向的那块图形被清成 0 ⇒ 屏幕上那格就是空白。
 * ==========================================================================*/
#include "lz_gate.h"
#include "tile_alloc.h"        /* V18_UI_ON */

#define V19_VRAM_LO    0x06000000u
#define V19_VRAM_HI    0x06018000u   /* 96 KB VRAM（BG + OBJ 全区） */
#define V19_MAX_SIZE   0x8000u       /* 单次空白上限 32 KB，防头异常 */

/* 从 LZ77 头取「解压后字节数」：byte0 = 0x10（压缩类型），byte1..3 = 大小(LE24)。 */
static uint32_t v19_lz_size(uint32_t src)
{
    const uint8_t *p;

    if (src < 0x08000000u || src >= 0x0A000000u)
        return 0u;
    p = (const uint8_t *)(uintptr_t)src;
    if (p[0] != 0x10u)
        return 0u;
    return (uint32_t)p[1] | ((uint32_t)p[2] << 8) | ((uint32_t)p[3] << 16);
}

/* VRAM 只能半字写 ⇒ 用 u16 清零（size 已对齐到 4）。 */
static void v19_zero_vram(uint32_t dst, uint32_t size)
{
    volatile uint16_t *p = (volatile uint16_t *)(uintptr_t)dst;
    uint32_t n = size >> 1;

    while (n--)
        *p++ = 0u;
}

int v19_lz_gate_C(uint32_t src, uint32_t dst)
{
    int in_vram = (dst >= V19_VRAM_LO) && (dst < V19_VRAM_HI);

    if (V18_UI_ON)
        return in_vram ? 1 : 2;      /* UI 开：完全照官方，只分派 SWI */

    if (!in_vram)
        return 2;                    /* 目标不在 VRAM：不是屏幕上看得见的东西 */

    {
        uint32_t size = v19_lz_size(src);

        if (size == 0u || size > V19_MAX_SIZE)
            return 1;                /* 头不合法 / 异常 ⇒ 不碰，照官方 */
        size = (size + 3u) & ~3u;
        if (dst + size > V19_VRAM_HI)
            size = V19_VRAM_HI - dst;
        v19_zero_vram(dst, size);
    }
    return 0;                        /* 不要解压 —— 那块已经空了 */
}
"""


def main() -> int:
    edits = []

    # ---------------------------------------------------------- 1. game_addrs.asm
    # 🔴 哨兵必须认「equ 那一行」而不是裸名字：本文件里**本来就有**一行
    #   带 `LZ77UnCompVram` 的注释（line 77），用裸名字判断会把整块静默跳过
    #    —— 2026-09-12 首跑就是这么栽的（armips 报 Undefined label）。
    t, crlf = load(ADDRS)
    if "LZ77UnCompVram                         equ" not in t:
        t = t.rstrip("\n") + "\n" + ADDRS_BLOCK
    edits.append((ADDRS, t, crlf, "game_addrs.asm"))

    # ------------------------------------------------- 2. hooks_origin.s（桩）
    t, crlf = load(STUBS)
    if "V19LzGate_Hook" not in t:
        t = t.rstrip("\n") + "\n" + STUB_BLOCK
    edits.append((STUBS, t, crlf, "hooks_origin.s"))

    # ------------------------------------------------- 3. entry.s（跳板）
    t, crlf = load(ENTRY)
    if "V19LzGate_Hook" not in t:
        t = rep(t, "\n.end\n", "\n" + ENTRY_BLOCK + ".end\n", "entry.s 插到 .end 前")
    edits.append((ENTRY, t, crlf, "entry.s"))

    # ------------------------------------------------- 4/5. 新文件
    for path, body in ((HDR, HDR_TEXT), (SRC, SRC_TEXT)):
        if not os.path.exists(path):
            io.open(path, "wb").write(body.replace("\n", "\r\n").encode("utf-8"))
            print("NEW  %s" % os.path.relpath(path, ROOT))
        else:
            print("SKIP %s（已存在）" % os.path.relpath(path, ROOT))

    # ------------------------------------------------- 6. build_sh_equiv.sh
    t, crlf = load(SH)
    if "lz_gate.c" not in t:
        t = rep(t,
                "$CC $CFLAGS  $TEXT/win_alloc.c                   -o $BUILD/win_alloc.o\n",
                "$CC $CFLAGS  $TEXT/win_alloc.c                   -o $BUILD/win_alloc.o\n"
                "$CC $CFLAGS  $TEXT/lz_gate.c                     -o $BUILD/lz_gate.o\n",
                "sh 编译行")
        t = rep(t,
                "  $BUILD/win_alloc.o \\\n",
                "  $BUILD/win_alloc.o \\\n  $BUILD/lz_gate.o \\\n",
                "sh 链接行")
        t = rep(t, "V17BlankTile_Hook; do", "V17BlankTile_Hook V19LzGate_Hook; do",
                "sh 符号表")
    edits.append((SH, t, crlf, "build_sh_equiv.sh"))

    # ------------------------------------------------- 7. build.bat
    t, crlf = load(BAT)
    if "lz_gate.c" not in t:
        t = rep(t,
                "echo === Assembling map_name_popup\\entry.s ===\n",
                "echo === Compiling text\\lz_gate.c (v19 LZ gate) ===\n"
                "%CC% %CFLAGS% %TEXT%\\lz_gate.c -o %BUILD%\\lz_gate.o\n"
                "if errorlevel 1 exit /b 1\n"
                "\n"
                "echo === Assembling map_name_popup\\entry.s ===\n",
                "bat 编译块")
        t = rep(t,
                "  %BUILD%/win_alloc.o ^\n",
                "  %BUILD%/win_alloc.o ^\n  %BUILD%/lz_gate.o ^\n",
                "bat 链接行")
        t = rep(t, "V17BlankTile_Hook)", "V17BlankTile_Hook V19LzGate_Hook)",
                "bat 符号表")
    edits.append((BAT, t, crlf, "build.bat"))

    for path, text, crlf, tag in edits:
        save(path, text, crlf)
        print("OK   %-24s %7d B  (CRLF=%s)" % (
            tag, os.path.getsize(path), crlf))

    print("\nv19 补丁落盘完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
