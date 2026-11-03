#!/usr/bin/env python3
"""调研⑤ 找火红的**中文码位表/字库索引结构**，弄清 F7 的真实语义。

═══════════════════════════════════════════════════════════════════════════
【为什么换个方向】
═══════════════════════════════════════════════════════════════════════════
统计法得到的「8,255 个码位」不可信：
  · hi 字节前 9 页几乎全满（255/256），而真实文本的字频分布不该这么均匀
  · 火红汉化版译文不重复汉字数不可能有 8000+

⇒ 说明 F7 的 (hi,lo) 不是「页 + 偏移」，可能是**别的结构**，
  或者 ROM 里混入了大量「看起来像文本」的非文本 F7。

**更可靠的办法：找字库表本身。**

汉化版必然有一张「码位 → 字形数据」的映射表。它的特征：
  · 表项数 = 汉字数（几千）
  · 表项内容指向 ROM 某处的字模数据
  · 表项本身可能是 u32 指针数组，或 u16 索引数组

方法：在 ROM 里找**密集的指针数组**（连续多个 u32 都落在 ROM 数据区），
     且数组长度在 3000-10000 之间 —— 那就是字库索引表。

用法：python scripts/research/firered/05_find_font_table.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
BASE = 0x08000000


def u32(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "little")


def is_rom_ptr(v: int) -> bool:
    return 0x08000000 <= v < 0x0A000000


def main() -> int:
    rom = FR_ZH.read_bytes()
    print(f"{FR_ZH.name}  {len(rom):,} B")

    # 找最长的一段「连续指针数组」
    best = []
    cur_start = None
    cur_len = 0
    for o in range(0, len(rom) - 4, 4):
        v = u32(rom, o)
        if is_rom_ptr(v):
            if cur_start is None:
                cur_start, cur_len = o, 1
            else:
                cur_len += 1
        else:
            if cur_len >= 500:
                best.append((cur_len, cur_start))
            cur_start, cur_len = None, 0
    if cur_len >= 500:
        best.append((cur_len, cur_start))

    best.sort(reverse=True)
    print(f"\n找到 {len(best)} 段长度 ≥500 的连续指针数组")
    print(f"{'长度':>8} {'ROM 地址':>12} {'指向范围'}")
    for n, o in best[:15]:
        lo = u32(rom, o) - BASE
        hi = u32(rom, o + (n - 1) * 4) - BASE
        print(f"{n:>8} 0x{BASE + o:08X}  0x{min(lo,hi):08X}..0x{max(lo,hi):08X}")

    print("\n=== 候选字库索引表（长度 3000–12000 最像）===")
    cand = [(n, o) for n, o in best if 3000 <= n <= 12000]
    if not cand:
        print("  没有符合长度的指针数组")
    for n, o in cand[:8]:
        print(f"\n  长度 {n}  @ROM 0x{BASE + o:08X}")
        # 看前 8 个指针指向的数据是否相似（字模应该同尺寸）
        ptrs = [u32(rom, o + k * 4) - BASE for k in range(8)]
        print(f"    前 8 个指针: {[hex(BASE + p) for p in ptrs]}")
        # 看指针间距（字模大小）
        gaps = [ptrs[k + 1] - ptrs[k] for k in range(7)]
        print(f"    指针间距: {gaps}")
        print(f"    ⇒ 若间距恒定，那个值就是**每个字模的字节数**")

    print("\n=== 也可能是 u16 索引数组 ===")
    # 找密集的 u16，值都在 0..8000 之间且递增
    runs = 0
    for o in range(0, min(len(rom) - 2, 0x80000), 2):
        v = rom[o] | (rom[o + 1] << 8)
        if v < 9000:
            runs += 1
    print(f"  前 512KB 里 u16 < 9000 的数量: {runs:,}（仅作参考）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
