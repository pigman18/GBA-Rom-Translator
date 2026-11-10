#!/usr/bin/env python3
"""调研(124) 验证「字形由原版字模变换而来」—— 抓同一文字的两次不同 VRAM。

═══════════════════════════════════════════════════════════════════════════
【最后的假设】
═══════════════════════════════════════════════════════════════════════════
已排除：ROM 静态存字形、LZ77、RLE、LZSS 压缩、按 nibble 特征可识别的字库。
唯一剩下的可能：**字形由代码实时合成**（用原版字模放大/拼接/变换）。

【怎么验证】
 若是合成的，那么：
  · 同一个汉字，在不同画面、不同位置出现时，**VRAM 里的字形数据应该相同**
    （缓存/复用）
  · 但若每次都重新合成，可能有细微差别

 更关键：**同一汉字在 VRAM 的 tile 编号会变，但内容不变**。
 (103) 已经看到：A_menu 和 B_world 的字形交集只有 8 个。
 ⇒ 说明大部分字只在特定画面出现（画面不同，字不同），
    但这不能区分「静态表」还是「实时合成」。

【决定性的测试：同一汉字在不同时间点的字节是否完全一致】
 ① 让同一个画面（继续游戏菜单）出现两次（比如进菜单 → 退出 → 再进）
 ② 比较两次 VRAM 里「同一位置的字形」是否**逐字节相同**
 ③ 若完全相同 ⇒ 是确定性的（静态表或确定性合成，无法区分）
    若有差异 ⇒ 实时合成

 这个测试其实也无法区分静态表和确定性合成…

【换个更直接的：抓「字形写入 VRAM 的时序」】
 读档后连续 200 帧，每帧 dump 一次 VRAM 的某个字形区域。
 若是从 ROM 复制 ⇒ 某一帧突然出现完整字形。
 若是逐像素合成 ⇒ 能看到字形逐渐形成。

这也分不出来（复制也是一帧完成）。

⭐ 真正能区分的办法：**在 VRAM 里找到字形后，立刻在 ROM 搜它的来源**。
   已做过，命中率低且都在原版图形区。

【本脚本：换一个思路 —— 直接看 game 里有没有「字形缓冲」线性结构】
 若字形是合成的，通常会先算到一个 RAM 缓冲，再 memcpy 到 VRAM。
 那么 IWRAM/EWRAM 里应该有一段「当前画面所有字形的连续副本」。
 
 做法：读档后，在 EWRAM/IWRAM 里搜「能找到 VRAM 字形的地方」。

用法：python scripts/research/firered/124_ram_font_buffer.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
ACC = ROOT / "work" / "_probe" / "accum"
LOAD = ROOT / "work" / "_probe" / "glyphload"


def main() -> int:
    print("=" * 78)
    print("① 从已知快照取字形，去 RAM 里找")
    print("=" * 78)

    # 取 A_menu 的字形和它的 VRAM/EWRAM
    vram_p = LOAD / "A_menu.vram.bin"
    if not vram_p.exists():
        print("缺 A_menu.vram.bin")
        return 1
    vram = vram_p.read_bytes()

    # 收集含灰阶的 tile
    glyphs = []
    for t in range(len(vram) // 32):
        blob = vram[t * 32:(t + 1) * 32]
        nib = set()
        for b in blob:
            nib.add(b & 0xF)
            nib.add(b >> 4)
        if nib & {11, 12}:
            glyphs.append(blob)
    print(f"  A_menu 里 {len(glyphs)} 个字形")

    # 但 accum 目录里没存 EWRAM/IWRAM，只有 VRAM
    # 需要检查有没有
    have_ram = list(ACC.glob("*.ram.bin"))
    print(f"  accum 里的 ram 文件：{len(have_ram)}")

    # ── ② 换个做法：直接在 VRAM 里找「重复出现的字形」──────────
    print("\n" + "=" * 78)
    print("② VRAM 里同一字形是否重复出现在多个 tile（缓存复用）")
    print("=" * 78)
    from collections import Counter
    sig = Counter()
    for g in glyphs:
        sig[g] += 1
    dup = [(k, v) for k, v in sig.items() if v > 1]
    print(f"  重复字形组：{len(dup)}")
    for k, v in sorted(dup, key=lambda x: -x[1])[:5]:
        print(f"    ×{v}  {k[:16].hex(' ')}")

    # ── ③ 关键：算 VRAM 里字形的「复杂度」，判断是否手工绘制 ────
    print("\n" + "=" * 78)
    print("③ 分析字形复杂度（手工 11×11 vs 放大 8×8）")
    print("=" * 78)
    # 若是放大的 8×8，笔画会有明显的「阶梯」或「2 像素宽」
    # 统计每个字形里「连续 2 像素宽」的笔画占比
    def thick_ratio(blob: bytes) -> float:
        m = np.zeros((8, 8), dtype=np.uint8)
        for y in range(8):
            for x in range(8):
                b = blob[y * 4 + x // 2]
                v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                m[y, x] = 1 if v in (11, 12) else 0
        # 水平方向相邻两像素都是墨，算「粗」
        h = (m[:, :-1] & m[:, 1:]).sum()
        tot = m.sum()
        return float(h) / max(1, tot)

    ratios = [thick_ratio(g) for g in glyphs]
    if ratios:
        a = np.array(ratios)
        print(f"  「2 像素宽笔画」占比：均值 {a.mean():.2%} "
              f"中位 {np.median(a):.2%}")
        print(f"  ⇒ 若从 8×8 放大到 11×11（1.375 倍），笔画会变粗，")
        print(f"     该值应明显偏高（>30%）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
