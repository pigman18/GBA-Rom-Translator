#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_v20_static.py — v20 静态复核（退出码即结论）。

v20 = 常规 UI 的 LZ77→VRAM 装载总闸（按**调用点 lr** 作用域）。
判据分组：
  A  注入区 == game.bin（需要打包后的 ROM）
  B  桩 8B 形态 == ldr r3,[pc,#0] / bx r3 / .word(Hook|1)   （需要 ROM：桩写在代码区）
  C  桩外逐字节 == 原盘 / 原盘那 8 字节 == 两条 BIOS 蹦床
  D  跳板语义（反汇编**文本** + 机器码**字节**双轨）
      D1 push {r4,lr}   D2 `mov r2, lr`（v20 的关键：把调用点交给 C）
      D3 push {r0,r1}   D4 bl 目标在注入区   D5 pop {r0,r1}
      D6/D7 cmp #0 / #2 各配 beq
      D8 svc 0x12(df12) 恰 1 次、svc 0x11(df11) 恰 1 次
      D9 三条出口都是 pop {r4,pc}（恰 3 次）   D10 push 恰 2 次
  E  符号存在
  F  白名单（include/lz_ui_sites.h，脚本生成）
  G  调用面 == 原盘（bl 0x081B1298 118 处 / bl 0x081B129C 42 处）
  H  跳板里**没有** `mov lr, pc`（机器码 0x4686）—— 铁律 6：
     模拟 bl 会读到「本指令+4」，bit0 恒 0 ⇒ 被调方 `bx lr` 时切 ARM ⇒ UNDEF。

⚠ 本脚本的两处踩坑记录（都是脚本自身 bug，别重犯）：
  1) objdump 一行的字段是 `地址: <tab> 机器码 <tab> 助记符 <tab> 操作数`
     ⇒ split('\t') 后 **[0] 是机器码**，助记符在 [1]。v20 首跑把 [0] 当助记符，
        14 项判据全假 FAIL。
  2) objdump 把 `svc 0x12` 打印成**十进制** `svc 18` ⇒ svc 一律用机器码(df12/df11)判。

用法：python scripts/verify_v20_static.py [ROM]
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBJDUMP = (r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi"
           r"\14.2 rel1\bin\arm-none-eabi-objdump.exe")
TMP = os.path.join(ROOT, ".tmp")
HOOKDIR = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook")
GAMEBIN = os.path.join(HOOKDIR, "out", "game.bin")
SYMS = os.path.join(HOOKDIR, "out", "game_syms.asm")
SRC_H = os.path.join(HOOKDIR, "include", "lz_ui_sites.h")
SRC_C = os.path.join(HOOKDIR, "src", "text", "lz_ui.c")
SRC_THUNK = os.path.join(HOOKDIR, "src", "text", "entry.s")
ORIG = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")

INJ = 0x08800000
STUB = 0x081B1298
LZ_V, LZ_W = 0x081B1298, 0x081B129C

PASS = FAIL = 0


def chk(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS  %s%s" % (name, ("  [%s]" % detail) if detail else ""))
    else:
        FAIL += 1
        print("  FAIL  %s%s" % (name, ("  [%s]" % detail) if detail else ""))
    return cond


def dis(blob: bytes, addr: int):
    """反汇编；返回 [(addr, mnemonic, operand_text)]。
    ⚠ [0] 是机器码字段，助记符在 [1]（v20 首跑栽在这里）。"""
    os.makedirs(TMP, exist_ok=True)
    f = os.path.join(TMP, "v20_dis.bin")
    with open(f, "wb") as fh:
        fh.write(blob)
    out = subprocess.run([OBJDUMP, "-D", "-b", "binary", "-m", "arm",
                          "-M", "force-thumb", "--adjust-vma=0x%08X" % addr, f],
                         capture_output=True, text=True, errors="replace")
    ins, started = [], False
    for ln in out.stdout.splitlines():
        if ln.startswith("Disassembly"):
            started = True
            continue
        if not started:
            continue
        m = re.match(r"^\s*([0-9a-f]{6,8}):\t(.*)$", ln)
        if not m:
            continue
        a = int(m.group(1), 16)
        parts = m.group(2).split("\t")
        if len(parts) < 2:
            continue
        mn = parts[1].strip()
        op = parts[2].strip() if len(parts) > 2 else ""
        if not mn:
            continue
        ins.append((a, mn, op))
    return ins


# v20 跳板结构（每条 2 字节，除 bl 是 4 字节）：
#   push {r4,lr} / mov r2,lr / push {r0,r1} / bl(4) / adds r4,r0,#0 / pop {r0,r1}
#   cmp r4,#0 / beq / cmp r4,#2 / beq / svc12 / pop{r4,pc}
#   svc11 / pop{r4,pc} / movs r0,#0 / pop{r4,pc}
#   = 30*... 实为 0x20 字节，且**没有 .pool**（跳板用 bl，不用 ldr 字面量）。
V20_EXITS = 3          # 三条出口：svc 0x12 / svc 0x11 / blank


def thunk_span(blob: bytes, n_exit: int = V20_EXITS, cap: int = 0x60) -> int:
    """从机器码自推跳板长度。
    判据 = 扫到**第 n_exit 个** `pop {.., pc}` 为止。
    ⚠ 不能「遇到第一个 pop{..,pc} 就停」：v20 跳板有三条出口，第一条在中间
      （svc 0x12 之上）。也不能写死长度（v17.2 血案：写死 0x26 多读 2 字节，
      正好吃进下一个函数的 push ⇒ 判据误报「push == 2」）。"""
    i = 0
    seen = 0
    while i < cap:
        hw = blob[i] | (blob[i + 1] << 8)
        if (hw & 0xF800) == 0xF000:            # 32bit（BL/BLX）
            i += 4
            continue
        i += 2
        if (hw & 0xFF00) == 0xBD00:            # pop {.., pc}
            seen += 1
            if seen >= n_exit:
                break
    return i                                   # ⚠ 不对齐到 4：跳板没有 .pool，
                                               #   多读 2 字节就会吃进下一个函数的
                                               #   对齐填充（v17.2 血案的同一类坑）。


def bl_target(blob: bytes, off: int, base: int) -> int:
    """解 Thumb BL 目标。base = 跳板起始地址（⚠ 不是桩地址 —— v20 首跑栽在这）。"""
    h1 = blob[off] | (blob[off + 1] << 8)
    h2 = blob[off + 2] | (blob[off + 3] << 8)
    S = (h1 >> 10) & 1
    imm10 = h1 & 0x3FF
    J1 = (h2 >> 13) & 1
    J2 = (h2 >> 11) & 1
    imm11 = h2 & 0x7FF
    I1 = (~(J1 ^ S)) & 1
    I2 = (~(J2 ^ S)) & 1
    o = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
    if o & 0x01000000:
        o -= 0x02000000
    return (base + off + 4 + o) & 0xFFFFFFFF


def count_bl(rom: bytes, target: int) -> int:
    n = 0
    for i in range(0, len(rom) - 3, 2):
        h1 = rom[i] | (rom[i + 1] << 8)
        h2 = rom[i + 2] | (rom[i + 3] << 8)
        if (h1 & 0xF800) == 0xF000 and (h2 & 0xD000) == 0xD000:
            S = (h1 >> 10) & 1
            imm10 = h1 & 0x3FF
            J1 = (h2 >> 13) & 1
            J2 = (h2 >> 11) & 1
            imm11 = h2 & 0x7FF
            I1 = (~(J1 ^ S)) & 1
            I2 = (~(J2 ^ S)) & 1
            o = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
            if o & 0x01000000:
                o -= 0x02000000
            site = 0x08000000 + i
            if ((site + 4 + o) & 0xFFFFFFFF) == target:
                n += 1
    return n


def sym_addr(path: str, name: str):
    for ln in io.open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*%s\s+equ\s+0x([0-9A-Fa-f]+)" % re.escape(name), ln)
        if m:
            return int(m.group(1), 16)
    return None


def main() -> int:
    print("=" * 74)
    print("v20 静态复核")
    print("=" * 74)

    gb = io.open(GAMEBIN, "rb").read()
    orig = io.open(ORIG, "rb").read()
    rom = None
    if len(sys.argv) > 1:
        rp = sys.argv[1]
        if not os.path.isabs(rp):
            rp = os.path.join(ROOT, rp)
        rom = io.open(rp, "rb").read()
        print("ROM %s  (%d B)" % (os.path.basename(rp), len(rom)))
    print("game.bin %d B   |  原盘 %d B" % (len(gb), len(orig)))
    print()

    # ---- A / B / C ----
    print("[A/B/C] 桩与注入区（需要打包后的 ROM）")
    if rom is None:
        print("  skip  （未给 ROM —— 桩写在代码区 0x081B1298，"
              "game.bin 只是注入区镜像，不含桩）")
    else:
        o = INJ - 0x08000000
        chk("A. 注入区 == game.bin", rom[o:o + len(gb)] == gb)
    hook = sym_addr(SYMS, "V20LzUi_Hook")
    chk("B0. 符号 V20LzUi_Hook 存在", hook is not None,
        ("0x%08X" % hook) if hook else "缺")
    if hook is None:
        return 1
    if rom is not None:
        so = STUB - 0x08000000
        stub = rom[so:so + 8]
        chk("B. 桩 8B == ldr r3,[pc,#0] / bx r3 / .word(Hook|1)",
            stub == bytes([0x00, 0x4B, 0x18, 0x47]) +
                    (hook | 1).to_bytes(4, "little"),
            " ".join("%02x" % b for b in stub))
        chk("C. 左邻 0x081B1290..97 == 原盘",
            rom[0x081B1290 - 0x08000000:0x081B1298 - 0x08000000] ==
            orig[0x081B1290 - 0x08000000:0x081B1298 - 0x08000000])
        chk("C. 右邻 0x081B12A0..AF == 原盘（0x081B12A0/A4 不能被吃）",
            rom[0x081B12A0 - 0x08000000:0x081B12B0 - 0x08000000] ==
            orig[0x081B12A0 - 0x08000000:0x081B12B0 - 0x08000000])
    chk("C2. 原盘那 8 字节 == 两条 BIOS 蹦床",
        orig[LZ_V - 0x08000000:LZ_V - 0x08000000 + 8] ==
        bytes([0x12, 0xDF, 0x70, 0x47, 0x11, 0xDF, 0x70, 0x47]),
        " ".join("%02x" % b for b in
                 orig[LZ_V - 0x08000000:LZ_V - 0x08000000 + 8]))
    print()

    # ---- D ----
    print("[D] 跳板语义（0x%08X）" % hook)
    span = thunk_span(gb[hook - INJ:])
    tk = gb[hook - INJ:hook - INJ + span]
    ins = dis(tk, hook)
    for a, mn, op in ins:
        print("      %08X  %-9s %s" % (a, mn, op))
    txt = [("%s %s" % (mn, op)).strip() for _, mn, op in ins]
    joined = "\n".join(txt)
    chk("D0. 跳板长度 %d B（3 条出口自推）" % span, span > 0, "0x%X" % span)
    chk("D1. push {r4, lr}", any(t.startswith("push") and "lr" in t for t in txt))
    chk("D2. `mov r2, lr`（把调用点交给 C —— v20 的关键）",
        any(t == "mov r2, lr" for t in txt), " | ".join(t for t in txt if "lr" in t))
    chk("D3. push {r0, r1}（保参数）",
        any(t.startswith("push") and "r0" in t and "r1" in t for t in txt))
    bt = None
    for i in range(0, len(tk) - 3, 2):
        if (tk[i] | (tk[i + 1] << 8)) & 0xF800 == 0xF000:
            if (tk[i + 2] | (tk[i + 3] << 8)) & 0xD000 == 0xD000:
                bt = bl_target(tk, i, hook)
                break
    chk("D4. bl 目标在注入区（= v20_lz_ui_C）",
        bt is not None and INJ <= bt < INJ + len(gb),
        ("0x%08X" % bt) if bt else "未找到")
    chk("D5. pop {r0, r1}",
        any(t.startswith("pop") and "r0" in t and "r1" in t for t in txt))
    chk("D6. cmp r4,#0 + beq", any(t.startswith("cmp r4, #0") for t in txt)
        and joined.count("beq") >= 2, "beq x%d" % joined.count("beq"))
    chk("D7. cmp r4,#2 + beq", any(t.startswith("cmp r4, #2") for t in txt))
    # ⚠ 字节序：`svc 0x12` 的半字是 0xDF12 ⇒ 落到字节流是 `12 df`。
    #   首跑写成 `tk[i]==0xDF and tk[i+1]==0x12` ⇒ df12 x0 / df11 x0（全假）。
    n12 = sum(1 for i in range(0, len(tk) - 1, 2)
              if tk[i] == 0x12 and tk[i + 1] == 0xDF)
    n11 = sum(1 for i in range(0, len(tk) - 1, 2)
              if tk[i] == 0x11 and tk[i + 1] == 0xDF)
    chk("D8. svc 0x12(df12) 与 svc 0x11(df11) 各恰 1 次",
        n12 == 1 and n11 == 1, "df12 x%d / df11 x%d" % (n12, n11))
    n_exit = sum(1 for t in txt
                 if t.startswith("pop") and "r4" in t and "pc" in t)
    chk("D9. 三条出口都是 pop {r4, pc}", n_exit == V20_EXITS, "实际 %d" % n_exit)
    n_push = sum(1 for t in txt if t.startswith("push"))
    chk("D10. push 恰 2 次（栈净额配平的前半）", n_push == 2, "实际 %d" % n_push)
    n_mov_pc = sum(1 for i in range(0, len(tk) - 1, 2)
                   if (tk[i] | (tk[i + 1] << 8)) == 0x4686)
    chk("H. 跳板里没有 `mov lr, pc`（机器码 0x4686）—— 铁律 6",
        n_mov_pc == 0, "0x4686 x%d" % n_mov_pc)
    print()

    # ---- E ----
    print("[E] 符号")
    c_addr = sym_addr(SYMS, "v20_lz_ui_C")
    print("      V20LzUi_Hook = 0x%08X" % hook)
    chk("E1. bl 目标 == game_syms 里的 v20_lz_ui_C（若列了）",
        True if c_addr is None else (bt == c_addr),
        ("sym: 0x%08X" % c_addr) if c_addr else
        "sym 未列（生成清单只收 Hook 符号，属正常）")
    print()

    # ---- F ----
    print("[F] 白名单 include/lz_ui_sites.h")
    h = io.open(SRC_H, encoding="utf-8", errors="replace").read()
    m = re.search(r"#define\s+V20_UI_SITE_COUNT\s+(\d+)", h)
    cnt = int(m.group(1)) if m else -1
    chk("F1. V20_UI_SITE_COUNT == 104", cnt == 104, "实际 %d" % cnt)
    lrs = [int(x, 16) for x in re.findall(r"0x([0-9A-F]{8})u,", h)]
    chk("F2. 条目数 == COUNT", len(lrs) == cnt, "实际 %d" % len(lrs))
    chk("F2b. 不含包装函数 lr 0x0800A776（lr 被所有转发调用共享）",
        0x0800A776 not in lrs)
    wild = [0x0811039E + 4, 0x081103A6 + 4, 0x0811E28A + 4,
            0x080077DE + 4, 0x080077E6 + 4, 0x08008660 + 4, 0x08008668 + 4]
    chk("F3. 不含野外 tileset 的任一 lr",
        all(w not in lrs for w in wild),
        "命中 %s" % [hex(w) for w in wild if w in lrs])
    chk("F4. 无重复 lr", len(set(lrs)) == len(lrs),
        "重复 %d" % (len(lrs) - len(set(lrs))))
    chk("F5. 全部 lr 落在代码区", all(0x08000000 <= x < 0x0A000000 for x in lrs))
    c = io.open(SRC_C, encoding="utf-8", errors="replace").read()
    chk("F6. lz_ui.c 用 V18_UI_ON 开关", "V18_UI_ON" in c)
    chk("F7. lz_ui.c 有「dst 不落 VRAM 就原样」的运行时保险",
        "V20_VRAM_LO" in c and "V20_VRAM_HI" in c and "in_vram" in c)
    chk("F8. lz_ui.c 解不出 LZ 头就原样放行（不乱清）", "size == 0u" in c)
    print()

    # ---- G ----
    print("[G] 调用面（原盘）")
    nv, nw = count_bl(orig, LZ_V), count_bl(orig, LZ_W)
    chk("G. bl LZ77UnCompVram == 118", nv == 118, "实际 %d" % nv)
    chk("G2. bl LZ77UnCompWram == 42", nw == 42, "实际 %d" % nw)
    print()

    print("=" * 74)
    print("PASS %d / FAIL %d   EXIT=%d" % (PASS, FAIL, 1 if FAIL else 0))
    print("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
