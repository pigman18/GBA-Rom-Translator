#!/usr/bin/env python3
"""调研(111) 追偏移表：0x08FE4860 的偏移指向哪，完整字库在哪。

═══════════════════════════════════════════════════════════════════════════
【重新理解 (110) 的反汇编】
═══════════════════════════════════════════════════════════════════════════
     8fe4816: ldr  r5,[pc,#92]   → 0x06010000   (VRAM 基址)
     8fe4818: adds r5,r5,r0      ← ★ **r0 是入参偏移**（不是 0）
     8fe481a: ldr  r0,[pc,#84]   → 0x08FE4660   (源数据)
     8fe481c: ldr  r3,[pc,#88]   → 0x08FE4860   (偏移表)
     8fe481e: ldr  r1,[r3,#0]    → 0x2C0
     8fe4820: adds r1,r1,r5      → 目标 = 0x06010000 + r0 + 0x2C0
     8fe4822: movs r2,#8         → 拷贝 8 个 u32 = 32 字节
     8fe4824: bl   0x08FE4852

 ⇒ 这段代码每次只拷贝 **4 个 tile（128 字节）**，
    源是 0x08FE4660（一个固定的小缓冲区），
    目标是 VRAM 0x06010000 + r0 + {0x2C0, 0x2E0, 0xA00, 0xA20}。

 ⇒ 这是「把一个预先算好的 4-tile 字形块搬进 VRAM」的**辅助函数**，
    不是字库本身。0x08FE4660 只是一次搬运的临时区。

【真正的问题：0x08FE4660 的内容是谁写的？】
 它在 ROM 里是静态数据（原版全 FF，汉化填了 128 字节）。
 这 128 字节对应 ROM 里的**一份固定字形**，被反复搬到不同 VRAM 位置。

 ⇒ 要找完整字库，得找调用这段代码的地方，看 r0（目标偏移）怎么算、
   以及源数据有没有被改写成别的字形。

【本脚本】
 ① 找谁调用 0x08FE4814
 ② 看调用点附近的逻辑（r0 从哪来）
 ③ 总结：字库是按需生成还是静态表

用法：python scripts/research/firered/111_trace_caller.py
"""
from __future__ import annotations

import struct
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
TMP = ROOT / "work" / "_probe" / "dis"


def dis(rom: bytes, addr: int, size: int = 0x100) -> list[str]:
    off = addr - BASE
    TMP.mkdir(parents=True, exist_ok=True)
    b, e = TMP / "t.bin", TMP / "t.elf"
    b.write_bytes(rom[off:off + size])
    subprocess.run(["arm-none-eabi-objcopy", "-I", "binary", "-O",
                    "elf32-littlearm", "-B", "arm",
                    "--rename-section", ".data=.text", str(b), str(e)],
                   capture_output=True)
    r = subprocess.run(["arm-none-eabi-objdump", "-d",
                        "--adjust-vma=" + hex(addr), "-M", "force-thumb",
                        str(e)], capture_output=True, text=True)
    return [ln.rstrip() for ln in r.stdout.splitlines()
            if "file format" not in ln and "Disassembly" not in ln and ln.strip()]


def decode_bl(rom: bytes, off: int):
    if off + 4 > len(rom):
        return None
    b0, b1, b2, b3 = rom[off], rom[off + 1], rom[off + 2], rom[off + 3]
    if (b1 & 0xF8) != 0xF0 or (b3 & 0xF8) != 0xF8:
        return None
    s = (b1 >> 2) & 1
    imm10 = ((b1 & 3) << 8) | b0
    imm11 = b2
    j1 = (b3 >> 5) & 1
    j2 = (b3 >> 3) & 1
    i1 = 1 - (j1 ^ s)
    i2 = 1 - (j2 ^ s)
    o = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    if s:
        o -= (1 << 25)
    pc = (off + 4) & ~3
    return pc + o


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("① 找谁 bl 到 0x08FE4814（字形搬运函数）")
    print("=" * 78)
    target = 0x8FE4814
    callers = []
    for off in range(0, n - 4, 2):
        t = decode_bl(zh, off)
        if t is not None and abs(t - target) <= 4:
            callers.append(off)
    print(f"  找到 {len(callers)} 个调用点")
    for off in callers[:10]:
        print(f"    0x{BASE+off:08X}"
              f"  {'★汉化新增' if zh[off:off+4] != ja[off:off+4] else ''}")

    # ── ② 也找指向 0x08FE4814 或附近的 u32（函数指针）───────────
    print("\n" + "=" * 78)
    print("② 找指向该函数的函数指针")
    print("=" * 78)
    m = n // 4 * 4
    pz = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)
    for tgt in (0x8FE4814, 0x8FE4815, 0x8FE4800, 0x8FE4810):
        h = np.flatnonzero(pz == tgt)
        if len(h):
            print(f"  0x{tgt:08X}: {len(h)} 处 → "
                  f"{[f'0x{BASE+x*4:08X}' for x in h[:5]]}")

    # ── ③ 反汇编调用点 ─────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 反汇编调用点附近")
    print("=" * 78)
    for off in callers[:3]:
        a = BASE + max(0, off - 0x50)
        print(f"\n  ---- 调用点 0x{BASE+off:08X} ----")
        for ln in dis(zh, a, 0xC0)[:22]:
            print("    " + ln)

    # ── ④ 看 0x08FE4600..0x08FE4660 是什么（搬运函数的入参区）──
    print("\n" + "=" * 78)
    print("④ 0x08FE4560..0x08FE4900 全貌")
    print("=" * 78)
    for off in range(0xFE4560, 0xFE4900, 0x40):
        blob = zh[off:off + 0x40]
        nz = sum(1 for b in blob if b != 0xFF)
        print(f"  0x{BASE+off:08X}: 非FF {nz:>2}/64  {blob[:32].hex(' ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
