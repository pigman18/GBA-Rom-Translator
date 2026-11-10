#!/usr/bin/env python3
"""调研(139) 反汇编 0x08000DA6 / 0x08000DF4 —— 这是写 VRAM 的代码。

═══════════════════════════════════════════════════════════════════════════
【(138) 抓到的证据】
═══════════════════════════════════════════════════════════════════════════
watchpoint 命中的 PC：
    0x08000DA6    LR=0x0800076B    r2=0x06004000
    0x08000DF4    LR=0x0800076B    r2=0x06000000
    0x08000DA6    r1=0x00001100
    0x08000DF4    r1=0x80000000

⇒ 这两个地址是「写 VRAM」的代码。
   但 r1（源）= 0x00001100 / 0x80000000，不像字形数据地址。

   r3 = 0x0200453C（EWRAM），可能是参数结构体 —— 里面有真正的源地址。

【本脚本】
 ① 反汇编 0x08000D80..0x08000E20
 ② 分析它从哪取源地址
 ③ 读 r3 指向的 EWRAM 结构体（若还能复现）

用法：python scripts/research/firered/139_disasm_vram_writer.py
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
BASE = 0x08000000
TMP = ROOT / "work" / "_probe" / "dis"


def dis(rom: bytes, addr: int, size: int = 0xC0) -> list[str]:
    off = addr - BASE
    TMP.mkdir(parents=True, exist_ok=True)
    b, e = TMP / "vw.bin", TMP / "vw.elf"
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

    print("=" * 78)
    print("① 反汇编 0x08000D60..0x08000E40（含命中的两个 PC）")
    print("=" * 78)
    for ln in dis(zh, 0x08000D60, 0xE0):
        print("  " + ln)

    print("\n" + "=" * 78)
    print("② 反汇编 0x08000740..0x080007A0（LR=0x0800076B 的调用者）")
    print("=" * 78)
    for ln in dis(zh, 0x08000740, 0x70):
        print("  " + ln)

    print("\n" + "=" * 78)
    print("③ 反汇编 0x08000D30..0x08000D70（函数入口）")
    print("=" * 78)
    for ln in dis(zh, 0x08000D20, 0x60):
        print("  " + ln)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
