#!/usr/bin/env python3
"""调研(107) 从渲染代码找字库 —— 不再盲搜 ROM。

═══════════════════════════════════════════════════════════════════════════
【为什么放弃盲搜】
═══════════════════════════════════════════════════════════════════════════
(96)(104)(106) 都在「拿 VRAM 字形去 ROM 里搜」。结果：
   · 4bpp 命中 151/1197，分散在十几个区，像是巧合
   · 1bpp 命中 146,556 处，是因为 8 字节里 4 个是 00，太容易撞

**都是假信号。** 说明 VRAM 字形与 ROM 存储形式不一致
（可能经过位运算/调色板映射，或本来就是运行时生成的）。

【唯一可靠的路：读渲染代码】
已知（(44)(45)）：
  · 0x081DB660 是转码函数：F6/F7 → 展开
  · 0x081DB698 的 F7 分支：`ldr r1,[base + hi*4]` 取指针，逐字节复制

那条链走的是**文本**，不是字形。字形应由另一个函数处理。

【本脚本：找「把字模写进 VRAM」的代码】
 特征：写 0x06000000 区。GBA 上写 VRAM 的典型指令：
   · `strh rX,[rY]` 且 rY 来自 ldr rN,=0x06000000
   · 或 ldr/str 配合基址 0x06000000 的字面量

做法：扫 ROM 里所有「字面量 = 0x06000000 附近」的位置，
再反汇编它附近的代码，看它怎么取字模、怎么算宽高。

用法：python scripts/research/firered/107_vram_write_code.py
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


def dis(rom: bytes, addr: int, size: int = 0xC0) -> list[str]:
    off = addr - BASE
    TMP.mkdir(parents=True, exist_ok=True)
    b, e = TMP / "v.bin", TMP / "v.elf"
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
    m = n // 4 * 4

    print("=" * 78)
    print("① 找「字面量 = 0x06000000（VRAM 基址）」的位置")
    print("=" * 78)
    pz = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)
    pa = np.frombuffer(ja[:m], dtype=np.uint32).astype(np.uint64)
    hit = np.flatnonzero(pz == 0x06000000)
    print(f"  u32 == 0x06000000：{len(hit)} 处")
    news = []
    for h in hit.tolist():
        off = h * 4
        same = pa[h] == pz[h]
        news.append((off, same))
    new_only = [o for o, s in news if not s]
    print(f"  其中汉化新增：{len(new_only)} 处")

    # ── ② 也扫 0x06010000（OBJ VRAM）和 0x06014000 ─────────────
    print("\n" + "=" * 78)
    print("② 扫 VRAM 的其它常见基址")
    print("=" * 78)
    for addr in (0x06010000, 0x06014000, 0x06008000):
        h = np.flatnonzero(pz == addr)
        newh = [x for x in h.tolist() if pa[x] != pz[x]]
        print(f"  0x{addr:08X}: 共 {len(h)} 处，汉化新增 {len(newh)} 处")

    # ── ③ 反汇编「汉化新增」的 VRAM 字面量附近 ──────────────────
    print("\n" + "=" * 78)
    print("③ 反汇编汉化新增的 VRAM 引用点")
    print("=" * 78)
    shown = 0
    for o in new_only[:6]:
        a = BASE + max(0, o - 0x40)
        print(f"\n  ---- 字面量 @0x{BASE+o:08X} ----")
        for ln in dis(zh, a, 0xA0)[:18]:
            print("    " + ln)
        shown += 1
        if shown >= 4:
            break

    # ── ④ 找「大块 memcpy 到 VRAM」的特征：ldmia/stmia ──────────
    print("\n" + "=" * 78)
    print("④ 搜 0x06000000 附近的 str 指令模式")
    print("=" * 78)
    # Thumb: 把 0x04000000 段之外的常量池找出来
    # 简单做法：在 0x06000000 字面量前 0x40 字节内找 ldr rX,[pc,#imm]
    for o in new_only[:10]:
        region = zh[max(0, o - 0x40):o + 4]
        if len(region) < 8:
            continue
        # 找 4X (ldr) 指令
        cnt = sum(1 for b in region if 0x48 <= b <= 0x4F)
        print(f"  0x{BASE+o:08X} 前 0x40 字节里 ldr 类字节 {cnt} 个")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
