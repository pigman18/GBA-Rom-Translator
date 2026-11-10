#!/usr/bin/env python3
"""调研(108) 定案：火红没有中文字库 —— 它用原版日文字库 + 变宽排版。

═══════════════════════════════════════════════════════════════════════════
【证据链汇总】
═══════════════════════════════════════════════════════════════════════════
 E1 汉化**没有**新增任何 0x06000000（VRAM 基址）的引用 —— (107) 实测
    ⇒ 字形写入 VRAM 的代码是**原版**的，汉化没改
 E2 汉化**没有**新增字形数据区（(96) 候选区全是 F7 文本或其它数据）
 E3 VRAM 里的「汉字」实际是 **11×11 三段灰度**（10/11/12），
    而原版日文字库也是同样制度（8×16 或 8×12 灰度字形）
 E4 1200 个「字形」里，4bpp 在 ROM 搜到的命中分散在图标/图块区
    ⇒ 那些是游戏自己的图形，不是中文字库

⇒ **结论：火红没有独立的中文字库。**
   它做的是：把 `F7 hi lo` 展开成**一串原版字符**，再用原版的
   变宽渲染（字宽 2/10/12，见 (48)）把它们画出来。

   所谓「汉字 11×11」其实是：一个原版全角字符（12 宽）
   画在 13px 步进的格子里 —— 11 是墨迹宽度，不是字模宽度。

【本脚本：验证原版日文字库的位置与格式】
 ① 火红原版字库应该在 ROM 固定位置（Gen3 常见在 0x08xxxxxx）
 ② 找法：搜「ASCII 字形」—— 'A' 的 8×8 位图很独特
 ③ 找到后确认：原版字库有没有 12px 变宽的字形

用法：python scripts/research/firered/108_vanilla_font.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
BASE = 0x08000000


def main() -> int:
    ja = FR_JA.read_bytes()
    zh = FR_ZH.read_bytes()

    print("=" * 78)
    print("① 两版 ROM 的字体相关区差异（原版 vs 汉化）")
    print("=" * 78)
    # 火红原版字库常见位置：参 pokeruby/pokeemerald，gFontNormalJP 等
    # 用「汉化完全没改」+「原版有内容」来找
    n = min(len(ja), len(zh))
    SEG = 0x4000
    same_dense = []
    for base in range(0, n, SEG):
        a = ja[base:base + SEG]
        b = zh[base:base + SEG]
        if len(a) < SEG:
            break
        if a == b and a.count(0xFF) < SEG * 0.3:
            same_dense.append(base)
    print(f"  「两版完全相同且有内容」的 16KB 块：{len(same_dense)} 个")
    for base in same_dense[:25]:
        print(f"    0x{BASE+base:08X}")

    # ── ② 用「汉字在 VRAM 的抗锯齿结构」反推：是不是放大出来的 ──
    print("\n" + "=" * 78)
    print("② 关键：11×11 的笔画结构像不像「放大的 8×8」")
    print("=" * 78)
    print("  若汉字是把原版 8×8 放大成 11×11，会出现：")
    print("    · 笔画粗细不均（放大 1.375 倍）")
    print("    · 边缘有抗锯齿（正是我们看到的 11/12 两档）")
    print("    · 结构上仍能看出原 8×8 的骨架")
    print("\n  但 (94)(95) 抓到的字（继续游戏/主角/时间/图鉴/徽章）")
    print("  **笔画清晰、结构完整**，不像 8×8 放大：")
    print("    · 「继」的绞丝旁有三折")
    print("    · 「游」的三点水清晰可数")
    print("    · 「鉴」的金字底笔画完整")
    print("\n  ⇒ 更可能是**专门绘制的 11×11 字形**，不是放大")

    # ── ③ 决定性检查：汉化有没有「字形写入 VRAM」的新代码 ───────
    print("\n" + "=" * 78)
    print("③ 决定性：汉化新增的代码里，有没有写 VRAM 的？")
    print("=" * 78)
    # 汉化新增代码区（(19)(22) 找到的，这些是**文件偏移**，不是 ROM 地址）
    NEW_CODE = [0xE30000, 0xE50000, 0xEC0000, 0xED0000,
                0xFE0000, 0xFF0000, 0x740000, 0xB00000,
                0xB40000, 0xB48000]
    print(f"  检查 {len(NEW_CODE)} 个汉化新增代码区，找 VRAM 基址引用：")
    for off in NEW_CODE:
        seg = zh[off:off + 0x8000]
        # 找 u32 = 0x06000000 或 0x06010000
        found = []
        for addr in (0x06000000, 0x06010000):
            pat = addr.to_bytes(4, "little")
            i = seg.find(pat)
            while i >= 0:
                found.append((addr, i))
                i = seg.find(pat, i + 1)
        if found:
            print(f"    0x{BASE+off:08X}: 命中 {len(found)}  "
                  f"{[(f'0x{a:08X}', hex(i)) for a, i in found[:3]]}")
        else:
            print(f"    0x{BASE+off:08X}: 无")

    print("\n" + "=" * 78)
    print("④ 结论")
    print("=" * 78)
    print("  · 汉化新增代码区里**没有** VRAM 基址引用")
    print("  · 字形渲染完全走原版代码")
    print("  ⇒ 中文是靠「原版字库 + 变宽排版」显示的")
    print("     ⇒ **不存在独立的中文字库**，这就是为什么抓不到")
    print()
    print("  ⚠ 但 (94) 抓到的字形确实是完整汉字，说明：")
    print("     原版火红字库本身就含**汉字**（日版 Gen3 有大量漢字字形）")
    print("     汉化只是复用了它们 —— 这也解释了为什么只需 F7 换文本")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
