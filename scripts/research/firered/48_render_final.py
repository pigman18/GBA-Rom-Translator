#!/usr/bin/env python3
"""调研㊽ 渲染协议定案：字宽从哪来、F7 展开后如何绘制。

═══════════════════════════════════════════════════════════════════════════
【目前确证的（㊺–㊼）】
═══════════════════════════════════════════════════════════════════════════
 Z1 原版编码 = 1 字节（㊶ 三判据）
 Z2 火红引入 4 个前缀：F6 / F7 / F8（+原版已有的）
 Z3 转码函数 @0x081DB660 & @0x081DB800：
      F6 h l        → 输出 F7 h l
      F7 h          → ptr = TABLE[h]; 展开 ptr 指向的原版单字节串
      F8 F7 h l     → 输出 F7 h l
      F8 F8 ??      → 原版就有（两版字节分布**完全一致**，非汉化引入）
 Z4 TABLE = 0x0203F2C0（EWRAM 缓冲区，**原版引擎本来就用**，4 处原版引用）
 Z5 F7 的第一参数字节（hi）真实分布以 0x00（42.8%）为主

⇒ 汉化的中文 = **「F7 表项索引」指向的「原版单字节串片段」**
  也就是说：它没有为每个汉字新建 8×12 字模，
  而是把常用「字/词」编译成原版字符集里的**序列**，渲染时展开。

═══════════════════════════════════════════════════════════════════════════
【本脚本：找出字宽/字模尺寸的确切来源】
═══════════════════════════════════════════════════════════════════════════
 ① 0x081DB640 那个「movs r0,#12 / bx lr」是什么函数（很可能返字宽 12）
 ② 从 0x081DB6C0 的 `cmp r1,#88 / subs r1,#88 / cmp r1,#108 / lsls r1,#2`
    反推它查的是一张 **按字节值索引的表**（0x58–0x6C 区间 = 88–108）
 ③ 反汇编 0x081DB6C0 所在函数，看它把字符转成什么
 ④ 结论：这套渲染是否真的需要 8+4/4+8 拼接

用法：python scripts/research/firered/48_render_final.py
"""
from __future__ import annotations

import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
TMP = ROOT / "work" / "_probe" / "dis"


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def dis(rom: bytes, addr: int, size: int = 0x120) -> list[str]:
    off = addr - BASE
    TMP.mkdir(parents=True, exist_ok=True)
    b, e = TMP / "r5.bin", TMP / "r5.elf"
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
    print("① 0x081DB640 附近的函数：是否返回字宽 12")
    print("=" * 78)
    for ln in dis(zh, 0x081DB620, 0x60):
        print("  " + ln)
    lit = ((0x081DB644 + 4) // 4) * 4 + 4
    print(f"\n  0x081DB644 的 ldr r1 字面量 @0x{lit:08X} = "
          f"0x{u32(zh, lit-BASE):08X}（原版 0x{u32(ja, lit-BASE):08X}）")

    print("\n" + "=" * 78)
    print("② 0x081DB6C0 的函数（cmp r1,#88 / #108 —— 按字节值查表）")
    print("=" * 78)
    for ln in dis(zh, 0x081DB5C0, 0x120):
        print("  " + ln)

    print("\n" + "=" * 78)
    print("③ 0x081DB6DC 与 0x081DB6E0 两个跳转目标")
    print("=" * 78)
    for lit in (0x081DB6DC, 0x081DB6E0, 0x081DB6E4):
        v = u32(zh, lit - BASE)
        print(f"  字面量 0x{lit:08X} = 0x{v:08X}"
              f"（原版 0x{u32(ja, lit-BASE):08X}）")
        if BASE <= v < BASE + n:
            print(f"    ---- 目标 0x{v:08X} ----")
            for ln in dis(zh, v, 0x60)[:14]:
                print("      " + ln)

    # ── ④ F7 表项内容：它展开成什么 ──────────────────────────────
    print("\n" + "=" * 78)
    print("④ 关键：F7 展开后的串有多长（决定是否需要变宽渲染）")
    print("=" * 78)
    # 已知 TABLE 在 EWRAM，ROM 里没有。改用「F7 后跟的串在文本区的形态」判断
    seg_lo, seg_hi = 0x6D0000, 0x722000
    seg = zh[seg_lo:seg_hi]
    # 统计「F7 xx」两字节后面紧跟的字节
    import collections
    c = collections.Counter()
    i = seg.find(b"\xf7")
    cnt = 0
    while i >= 0 and i + 2 < len(seg):
        nxt = seg[i + 2]
        c[nxt] += 1
        cnt += 1
        i = seg.find(b"\xf7", i + 1)
    print(f"  文本区里 F7 后第 3 字节的分布（前 12）：")
    for k, v in c.most_common(12):
        print(f"    0x{k:02X}: {v:>7,}（{v/max(1,cnt)*100:>5.1f}%）")
    print(f"\n  ⇒ 若第 3 字节几乎都是 0xF7，说明是连续的 F7 xx F7 xx（每字 2 字节）")

    # 直接统计 F7 xx 的「后一字节是不是另一个 F7」
    f7_next_f7 = 0
    tot = 0
    i = seg.find(b"\xf7")
    while i >= 0 and i + 2 < len(seg):
        tot += 1
        if seg[i + 2] == 0xF7:
            f7_next_f7 += 1
        i = seg.find(b"\xf7", i + 1)
    print(f"  F7 xx 后紧跟 F7 的比例：{f7_next_f7}/{tot} = "
          f"{f7_next_f7/max(1,tot)*100:.1f}%")
    print(f"  ⇒ 高比例 = 每个汉字 2 字节（F7 + 索引），**没有第 3 字节**")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
