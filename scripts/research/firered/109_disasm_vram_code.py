#!/usr/bin/env python3
"""调研(109) 追唯一线索：0x08FE4874 引用了 OBJ VRAM 基址 0x06010000。

═══════════════════════════════════════════════════════════════════════════
【这是目前唯一「汉化新增代码 + 写 VRAM」的证据】
═══════════════════════════════════════════════════════════════════════════
(108) 扫 10 个汉化新增代码区，只有 1 处命中：
    区 0x08FE0000 偏移 +0x4874 → 文件偏移 0xFE4874 → ROM 0x08FE4874
    引用的常量是 **0x06010000**（OBJ 的 VRAM 基址）

⇒ 这段代码很可能就是「把字模写进 VRAM」的地方，或者是 OBJ 相关。

【本脚本】
 ① 反汇编 0x08FE4800..0x08FE4900 一带
 ② 找它的调用者（谁跳到这段）
 ③ 若是字模写入：接着看它从哪读字形数据

用法：python scripts/research/firered/109_disasm_vram_code.py
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
    b, e = TMP / "w.bin", TMP / "w.elf"
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


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    target = 0xFE4874          # 文件偏移
    rom_addr = BASE + target
    print("=" * 78)
    print(f"① 反汇编 0x{rom_addr:08X} 一带")
    print("=" * 78)
    for ln in dis(zh, rom_addr - 0x60, 0x140):
        print("  " + ln)

    # ── ② 原版该处是什么 ──────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 原版同一位置")
    print("=" * 78)
    seg_j = ja[target - 0x60: target + 0x100]
    seg_z = zh[target - 0x60: target + 0x100]
    print(f"  原版 64 字节: {seg_j[:64].hex(' ')}")
    print(f"  汉化 64 字节: {seg_z[:64].hex(' ')}")
    same = sum(1 for a, b in zip(seg_j, seg_z) if a == b)
    print(f"  相同字节 {same}/{len(seg_j)}")

    # ── ③ 找谁引用这段（调用者）────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 谁引用了 0x08FE48xx 这段代码")
    print("=" * 78)
    m = n // 4 * 4
    pz = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)
    # 搜指向 0x08FE4800..0x08FE4900 的 u32
    lo, hi = BASE + 0xFE4800, BASE + 0xFE4920
    hit = np.flatnonzero((pz >= lo) & (pz < hi))
    print(f"  指向该区的 u32：{len(hit)} 处")
    for h in hit.tolist()[:12]:
        off = h * 4
        v = int(pz[h])
        old = struct.unpack_from("<I", ja, off)[0]
        mark = "" if old == v else "  ← 汉化改的"
        print(f"    0x{BASE+off:08X} → 0x{v:08X}{mark}")

    # ── ④ 也找 bl 跳向该区的 ───────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 找 bl（FF F7 xx F8）跳向 0x08FE48xx 的")
    print("=" * 78)

    def decode_bl(rom: bytes, off: int):
        """若 off 处是 Thumb bl，返回目标地址。"""
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
        off2 = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
        if s:
            off2 -= (1 << 25)
        pc = (off + 4) & ~3
        return pc + off2

    found = []
    for off in range(0, n - 4, 2):
        t = decode_bl(zh, off)
        if t is not None and lo <= t < hi:
            found.append((off, t))
    print(f"  bl 跳向该区：{len(found)} 处")
    for off, t in found[:10]:
        old = struct.unpack_from("<H", ja, off)[0] if off + 2 <= len(ja) else 0
        new = struct.unpack_from("<H", zh, off)[0]
        print(f"    0x{BASE+off:08X} → 0x{t:08X}  "
              f"{'（汉化新增）' if old != new else ''}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
