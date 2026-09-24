#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_v19_static.py — v19（LZ77→VRAM 装载总闸）静态复核。退出码 = 结论。

L1 静态层（不采 gdb、不跑模拟器）：
  A. 注入区（0x08800000）逐字节 == out/game.bin
  B. 桩形态：0x081B1298..0F == `00 4b 18 47 <Hook|1 LE>`（8B 不碰栈纯跳转）
  C. 被覆盖 8 字节的**左右邻居**必须逐字节 == 原盘：
       0x081B1290..0x081B1297（前一函数尾）
       0x081B12A0..0x081B12AF（svc 0x0F / svc 0x15 两条蹦床 —— 实测各被 5/13 处调用）
  D. 跳板语义（反汇编自证，不比编码）：
       push {r4,lr} / push {r0,r1} / bl v19_lz_gate_C / pop {r0,r1}
       三分支：0→movs r0,#0 / 2→svc 0x11 / 其余→svc 0x12
       三条出口都是 `pop {r4,pc}` ⇒ push 1 次、pop 2 次（1 次 {r0,r1} + 1 次出口）
  E. 符号：V19LzGate_Hook 在 game_syms.asm，且桩里的字面量 == 该符号 | 1
  F. lz_gate.c 源码级：V18_UI_ON 受控、只清 VRAM、LZ77 头解析正确
  G. LZ 调用面证据：`bl 0x081B1298` == 118 / `bl 0x081B129C` == 42（原盘）
  H. 注入区无 `mov lr, pc`（Thumb UNDEF 老坑）

用法：python scripts/verify_v19_static.py
"""
from __future__ import annotations

import io
import os
import re
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM_OUT = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.gba")
# 允许指定待检 ROM（打包时若 mGBA 占着 _translated.gba，成品会落到 _new.gba）
if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
    ROM_OUT = sys.argv[1] if os.path.isabs(sys.argv[1]) else os.path.join(ROOT, sys.argv[1])
ROM_ORG = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
GB = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook", "out", "game.bin")
SYMS = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook", "out", "game_syms.asm")
LZG = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook", "src", "text", "lz_gate.c")
ENTRY = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook", "src", "text", "entry.s")

INJ = 0x08800000
LZ = 0x081B1298
OBJDUMP = (r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi"
           r"\14.2 rel1\bin\arm-none-eabi-objdump.exe")
TMP = os.path.join(ROOT, ".tmp")

FAILS: list[str] = []
OKS: list[str] = []


def chk(name: str, cond: bool, extra: str = "") -> None:
    (OKS if cond else FAILS).append(name + (("  [" + extra + "]") if extra else ""))


def off(a: int) -> int:
    return a - 0x08000000


def hx(b: bytes) -> str:
    return " ".join("%02x" % x for x in b)


def dis(blob: bytes, vma: int) -> list[str]:
    """objdump force-thumb 反汇编，返回「机器码 + 助记符」整行文本。

    ⚠ objdump 输出首行是 `<path>:     file format binary`（含冒号！），
      按冒号切会把 "C" 当十六进制地址收进来（v19 首跑就是这么误报 D1 的）。
      这里改为：只收「含 tab 且 tab 前是 16 进制地址」的行，正文取 tab 之后全部。
    """
    os.makedirs(TMP, exist_ok=True)
    f = os.path.join(TMP, "v19_dis.bin")
    with open(f, "wb") as fh:
        fh.write(blob)
    out = subprocess.run(
        [OBJDUMP, "-D", "-b", "binary", "-m", "arm", "-M", "force-thumb",
         "--adjust-vma=0x%08X" % vma, f],
        capture_output=True, text=True, errors="replace")
    res = []
    for ln in out.stdout.splitlines():
        parts = ln.split("\t")
        if len(parts) < 2:                      # file-format 行 / 空行
            continue
        if not re.fullmatch(r"\s*[0-9a-fA-F]+:\s*", parts[0]):
            continue
        body = " ".join(p.strip() for p in parts[1:] if p.strip())
        if body:
            res.append(body)
    return res


def main() -> int:
    for p in (ROM_OUT, ROM_ORG, GB, SYMS, LZG, ENTRY):
        if not os.path.exists(p):
            print("缺文件: %s" % p)
            return 2
    rom = io.open(ROM_OUT, "rb").read()
    org = io.open(ROM_ORG, "rb").read()
    gb = io.open(GB, "rb").read()
    syms = io.open(SYMS, encoding="utf-8", errors="replace").read()
    src = io.open(LZG, encoding="utf-8").read()
    ent = io.open(ENTRY, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

    print("ROM   %s  %d B" % (os.path.basename(ROM_OUT), len(rom)))
    print("orig  %s  %d B" % (os.path.basename(ROM_ORG), len(org)))
    print("game.bin %d B" % len(gb))
    print()

    # ---- A. 注入区 == game.bin ----
    inj = rom[off(INJ):off(INJ) + len(gb)]
    chk("A. 注入区逐字节 == out/game.bin (%d B)" % len(gb), inj == gb)

    # ---- E. 符号 ----
    m = re.search(r"V19LzGate_Hook\s+equ\s+0x([0-9A-Fa-f]+)", syms)
    hook = int(m.group(1), 16) if m else 0
    chk("E1. game_syms.asm 有 V19LzGate_Hook", bool(m),
        ("0x%08X" % hook) if m else "缺失")
    chk("E2. 符号落在注入区", INJ <= hook < INJ + len(gb), "0x%08X" % hook)

    # ---- B. 桩形态 ----
    stub = rom[off(LZ):off(LZ) + 8]
    exp = bytes([0x00, 0x4B, 0x18, 0x47]) + struct.pack("<I", (hook | 1) & 0xFFFFFFFF)
    chk("B. 桩 8B == ldr r3,[pc,#0] / bx r3 / word(Hook|1)", stub == exp,
        "实际 " + hx(stub))

    # ---- C. 邻居必须未动 ----
    for a, n, label in ((LZ - 8, 8, "0x081B1290..97 前一函数尾"),
                        (LZ + 8, 16, "0x081B12A0..AF svc0F/svc15 蹦床")):
        same = rom[off(a):off(a) + n] == org[off(a):off(a) + n]
        chk("C. %s 逐字节 == 原盘" % label, same,
            hx(rom[off(a):off(a) + n]) if not same else "")

    # 原盘那 8 字节确实是两条 LZ 蹦床（再次自证）
    o8 = org[off(LZ):off(LZ) + 8]
    chk("C2. 原盘 0x081B1298..9F == svc0x12/bx lr + svc0x11/bx lr",
        o8 == bytes([0x12, 0xDF, 0x70, 0x47, 0x11, 0xDF, 0x70, 0x47]),
        hx(o8))

    # ---- D. 跳板语义（长度自推，别写死）----
    span = thunk_span(gb, hook, INJ)
    print("跳板长度（自推）= %d B (0x%X)" % (span, span))
    chk("D0. 跳板长度自推符合预期 0x20（15 条 2B + 1 条 4B bl）", span == 0x20,
        "实际 0x%X" % span)
    blk = gb[hook - INJ: hook - INJ + span]
    ins = dis(blk, hook)
    txt = "\n".join(ins)

    def has(pat: str) -> bool:
        return bool(re.search(pat, txt))

    chk("D1. 跳板 push {r4,lr}", bool(ins) and has(r"\bpush\b\s*\{r4, lr\}"),
        ins[0] if ins else "")
    chk("D2. 跳板 push {r0,r1} 保参数",
        has(r"\bpush\b\s*\{r0, r1\}"),
        " | ".join(i for i in ins if "push" in i))
    c_target = _find_c(gb, hook, INJ)
    chk("D3. 跳板 bl 目标在注入区（= v19_lz_gate_C）",
        INJ <= c_target < INJ + len(gb), "0x%08X" % c_target)
    n_push = sum(1 for i in ins if re.search(r"\bpush\b", i))
    n_pop = sum(1 for i in ins if re.search(r"\bpop\b", i))
    chk("D4. push 恰好 2 次（push {r4,lr} + push {r0,r1}）", n_push == 2,
        "实际 %d" % n_push)
    chk("D5. pop 恰好 4 次（pop {r0,r1} + 三条出口各 pop {r4,pc}）",
        n_pop == 4, "实际 %d" % n_pop)
    chk("D6. 含 svc 0x12(df12) 与 svc 0x11(df11) 各一次",
        txt.count("df12") == 1 and txt.count("df11") == 1,
        " | ".join(i for i in ins if re.search(r"\bsvc\b", i)))
    chk("D7. 空白路径 movs r0,#0 存在",
        has(r"\bmovs\b\s*r0, #0"),
        " | ".join(i for i in ins if re.search(r"\bmovs\b", i)))
    chk("D8. 三条出口都是 pop {r4, pc}",
        sum(1 for i in ins if re.search(r"\bpop\b\s*\{r4, pc\}", i)) == 3,
        " | ".join(i for i in ins if re.search(r"\bpop\b", i)))

    # ---- F. 源码级 ----
    chk("F1. lz_gate.c 受 V18_UI_ON 控制", "V18_UI_ON" in src)
    chk("F2. lz_gate.c 只清 VRAM（有 VRAM 区间上下界）",
        "0x06000000" in src and "0x06018000" in src)
    chk("F3. lz_gate.c 解析 LZ77 头（类型字节 0x10 + 24bit 大小）",
        "0x10u" in src and "<< 16" in src)
    chk("F4. lz_gate.c 用半字清零（VRAM 不能字节写）",
        "volatile uint16_t" in src and ">> 1" in src)
    chk("F5. 跳板源码不重放原体（原体无 push，桩不碰 lr）",
        "V19LzGate_Hook" in ent and "pop     {r4, pc}" in ent)

    # ---- G. 调用面 ----
    bls = bl_targets(org)
    c12 = sum(1 for _, t in bls if t == 0x081B1298)
    c11 = sum(1 for _, t in bls if t == 0x081B129C)
    chk("G. `bl LZ77UnCompVram` == 118（收敛层规模）", c12 == 118, "实际 %d" % c12)
    chk("G2. `bl LZ77UnCompWram` == 42（必须被跳板按 dst 分派覆盖）", c11 == 42,
        "实际 %d" % c11)

    # ---- H. 无 mov lr, pc ----
    hits = [i for i in dis(blk, hook) if re.search(r"mov\s+lr,\s*pc", i)]
    chk("H. 跳板区无 mov lr, pc", not hits, " | ".join(hits))

    print("=" * 74)
    for s in OKS:
        print("  ✅ " + s)
    for s in FAILS:
        print("  ❌ " + s)
    print("=" * 74)
    print("PASS %d / FAIL %d" % (len(OKS), len(FAILS)))
    return 0 if not FAILS else 1


def thunk_span(gb: bytes, base: int, inj: int, cap: int = 0x80) -> int:
    """从机器码自推跳板字节长度（v17.2 教训：区间既不能写死、也不能靠相邻符号推）。

    线性扫半字（BL/BLX 占 4 字节，其余 2 字节）；记下最近一条 `pop {..., pc}`
    （编码 0xBD00 掩码 —— bit8 = P = pc，所以 `pop {r0,r1}`=0xBC03 不会误中）；
    一旦在某条 `pop {...,pc}` 之后又碰到 `push`（0xB4xx/0xB5xx）＝已经走进下一个
    函数的 prologue ⇒ 停。返回最后那条 `pop {...,pc}` 的结束偏移。
    """
    b = gb[base - inj: base - inj + cap]
    i = 0
    last_pop_pc = -1
    while i + 1 < len(b):
        hw = b[i] | (b[i + 1] << 8)
        if (hw & 0xF800) == 0xF000 and i + 3 < len(b):
            hw2 = b[i + 2] | (b[i + 3] << 8)
            if (hw2 & 0xD000) == 0xD000:            # BL / BLX
                i += 4
                continue
        if (hw & 0xFF00) == 0xBD00:                 # pop {..., pc}
            last_pop_pc = i
        elif (hw & 0xFE00) == 0xB400 and last_pop_pc >= 0:
            break                                   # 下一个函数，收工
        i += 2
    return 0 if last_pop_pc < 0 else last_pop_pc + 2


def _find_c(gb: bytes, hook: int, inj: int) -> int:
    """从跳板里解出 bl 目标（Thumb BL T1）。"""
    span = thunk_span(gb, hook, inj) or 0x24
    b = gb[hook - inj: hook - inj + span]
    for k in range(0, len(b) - 3, 2):
        h1 = b[k] | (b[k + 1] << 8)
        h2 = b[k + 2] | (b[k + 3] << 8)
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
            return (hook + k + 4 + o) & 0xFFFFFFFF
    return 0


def bl_targets(rom: bytes):
    out = []
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
            out.append((site, (site + 4 + o) & 0xFFFFFFFF))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
