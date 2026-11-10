#!/usr/bin/env python3
"""调研㊻ 渲染协议③：火红字模的真身 —— 从 F7 的串表一路追到字形数据。

═══════════════════════════════════════════════════════════════════════════
【㊺ 解出的解码函数（0x081DB800）】
═══════════════════════════════════════════════════════════════════════════
这是一个**转码/展开**函数，不是字形绘制：

    ch = *src
    if ch == 0xFF           → 结束
    if ch == 0xF7:                       ; 2 字节形式
        hi = src[1]
        ptr = table[hi]                  ; 表项为 4 字节指针
        src += 2
        while (*ptr != 0xFF) *dst++ = *ptr++;   ; 展开成原版单字节串
    if ch == 0xF8 and src[1] == 0xF7:    ; 4 字节形式
        dst[0]=0xF7; dst[1]=src[2]; dst[2]=src[3]; dst+=3; src+=4
    else: *dst++ = *src++                ; 原样

⇒ **关键结论：`F7 hi` 是 2 字节索引，指向「原版单字节串」。**
  汉化并没有新造 2000+ 字形，它是把中文词**映射回已有的原版字符**。
  这解释了为什么找不到「中文字模」——**根本没有新字模！**

  而 `F8 F7 hi lo` 是 4 字节形式，展开成 `F7 hi lo`，是给「需要逐字节
  精确控制」的场合用的（比如名字表，要保证字节数不变）。

═══════════════════════════════════════════════════════════════════════════
【本脚本要坐实】
═══════════════════════════════════════════════════════════════════════════
 ① 反汇编 0x081DB698（0x081DB660 里的 F7 分支）与 0x081DB800 是否同一逻辑
 ② 从 0x081DB85C 的 r7（表基址）反推：那个 `movt r2,#3` 附近是什么值
 ③ 用表基址读 table[0], table[1]... 看指向什么
 ④ 验证：table[i] 指向的串，是不是**原版单字节日文**

用法：python scripts/research/firered/46_glyph_truth.py
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


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def dis(rom: bytes, addr: int, size: int = 0x100) -> list[str]:
    off = addr - BASE
    TMP.mkdir(parents=True, exist_ok=True)
    b, e = TMP / "r3.bin", TMP / "r3.elf"
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

    print("=" * 78)
    print("① 0x081DB836 用的表基址 r7 是什么")
    print("=" * 78)
    # 81db806: 4f15  ldr r7,[pc,#84]  → 字面量在 81db806+4+84 = 81db85e? 
    # Thumb: 字面量地址 = ALIGN4(addr+4) + imm*4
    for addr, imm, label in ((0x081DB806, 84, "0x081DB800 里的 ldr r7"),
                             (0x081DB666, 112, "0x081DB660 里的 ldr r7")):
        lit = ((addr + 4) // 4) * 4 + imm
        val = u32(zh, lit - BASE)
        val_o = u32(ja, lit - BASE)
        print(f"  {label}: 字面量@0x{lit:08X} = 汉化 0x{val:08X} / "
              f"原版 0x{val_o:08X}")

    print("\n" + "=" * 78)
    print("② 反汇编 0x081DB698（0x081DB660 的 F7 分支）")
    print("=" * 78)
    for ln in dis(zh, 0x081DB690, 0x90):
        print("  " + ln)

    # ── ③ 找真正指向串表的基址 ────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 找「指针表」：连续多个 u32 都指向原版单字节串")
    print("=" * 78)
    m = n // 4 * 4
    pz = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)
    pa = np.frombuffer(ja[:m], dtype=np.uint32).astype(np.uint64)

    # 先看 0x081DB85C 附近到底读到了什么
    for lit in (0x081DB85C, 0x081DB6D8):
        v = u32(zh, lit - BASE)
        print(f"  字面量 0x{lit:08X} = 0x{v:08X}"
              f"（{'ROM 内' if BASE <= v < BASE + n else '非法'}）")

    # 扫「指向 0x083Dxxxx 或 0x083Exxxx（原版日文文本区）的密集指针数组」
    print(f"\n  扫「指向 0x083DDxxx 一带」的指针数组：")
    lo, hi = BASE + 0x3DD000, BASE + 0x3E0000
    hit = np.zeros(len(pz), dtype=bool)
    hit = (pz >= lo) & (pz < hi)
    runs = []
    i = 0
    while i < len(hit):
        if hit[i]:
            j = i
            while j + 1 < len(hit) and hit[j + 1]:
                j += 1
            runs.append((i * 4, j - i + 1))
            i = j + 1
        else:
            i += 1
    runs.sort(key=lambda x: -x[1])
    print(f"    连续 run：{len(runs)} 个，最长的 10 个：")
    for off, cnt in runs[:10]:
        first = int(pz[off // 4]) - BASE
        print(f"      0x{BASE+off:08X}  {cnt:>5} 个 → 首项 0x{BASE+first:08X}"
              f"  原版此槽 0x{u32(ja,off):08X}")

    # ── ④ 验证：表项指向的是不是原版单字节日文 ────────────────────
    if runs:
        off = runs[0][0]
        cnt = min(runs[0][1], 20)
        print(f"\n  验证表 @0x{BASE+off:08X}（前 {cnt} 项）：")
        print(f"    {'#':>3} {'指向':>12} {'原版该处内容':>30} {'汉化该处内容'}")
        for k in range(cnt):
            v = int(pz[(off + k * 4) // 4]) - BASE
            e = ja.find(b"\xff", v, v + 40)
            cj = ja[v:e] if e > 0 else ja[v:v + 12]
            ez = zh.find(b"\xff", v, v + 40)
            cz = zh[v:ez] if ez > 0 else zh[v:v + 12]
            print(f"    {k:>3} 0x{BASE+v:08X} {cj.hex(' '):>30}  {cz.hex(' ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
