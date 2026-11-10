#!/usr/bin/env python3
"""调研㊳ 渲染协议：火红的中文/日文 12px 字模到底怎么存、怎么画。

═══════════════════════════════════════════════════════════════════════════
【要回答的问题（用户原话）】
═══════════════════════════════════════════════════════════════════════════
「由于日版 ruby 没有变宽汉化，因此 12px 是通过 8+4 / 4+8 显示出来的，
  因此 charBase 区大量占用。有些界面移动光标或者弹窗（比如背包里使用
  学习装置，会出现提示），会出现大量撞 UI、文字互相替换 BUG。
  要研究一下有没有更优雅的 12px 渲染方案？以及火红那边是怎么显示的」

═══════════════════════════════════════════════════════════════════════════
【必须先解决的前提：找字模区】
═══════════════════════════════════════════════════════════════════════════
火红的字模在哪？两个方向：
  A) 原版日文 1 字节字模（8×12 或 8×16），原版就有，汉化没动
  B) 汉化新增的中文字模（F7 码位 2,299 个），必须在新增区

判据：字模区 = 「位图特征强」的区。文本区墨量变异系数 0.10–0.14，
字模应该更低（< 0.05），因为每个字都是满格位图。

方法：
 ① 对全 ROM 按 16 字节步长切片，算每片的「墨量」（1 的个数）
 ② 找墨量稳定、且值分布集中（不是 0 也不是满）的连续区
 ③ 对候选区用 8×12 / 8×16 / 16×16 三种方式切 tile，算各自的墨量变异系数
    变异系数最小的那种尺寸 = 真实字模尺寸

用法：python scripts/research/firered/38_font_bitmaps.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def bit_count(a: np.ndarray) -> np.ndarray:
    return np.unpackbits(a).reshape(-1, 8).sum(axis=1) if a.dtype == np.uint8 else None


def main() -> int:
    zh = np.frombuffer(FR_ZH.read_bytes(), dtype=np.uint8)
    ja = np.frombuffer(FR_JA.read_bytes(), dtype=np.uint8)
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("① 全 ROM 位图特征扫描：找「墨量稳定」的区")
    print("=" * 78)
    # 8KB 一块，算 popcount 的均值和变异系数
    SEG = 0x2000
    nseg = n // SEG
    pop = np.unpackbits(ja[:nseg * SEG]).reshape(nseg, SEG, 8).sum(axis=(1, 2))
    # 每块的「字节级墨量」= 该块平均每个字节的 1 的个数
    dens = pop / (SEG * 8)

    # 字模区特征：非 0 非 255，密度中等且块间稳定
    cand = []
    for i in range(nseg):
        d = dens[i]
        if 0.25 <= d <= 0.60 and (ja[i * SEG] != 0xFF):
            cand.append((i, d))
    print(f"  候选 8KB 块：{len(cand)}（密度 0.25–0.60 且非全 FF）")

    # 看这些块是否连成片
    runs = []
    if cand:
        idxs = [c[0] for c in cand]
        s = p = idxs[0]
        for x in idxs[1:]:
            if x == p + 1:
                p = x
            else:
                runs.append((s, p))
                s = p = x
        runs.append((s, p))
    runs = [(a, b) for a, b in runs if b - a >= 1]
    runs.sort(key=lambda r: -(r[1] - r[0]))
    print(f"  连续成片的候选区（≥16KB）：{len(runs)} 个")
    print(f"  {'起始':>14} {'大小':>10} {'平均密度':>9}")
    for a, b in runs[:15]:
        d = dens[a:b + 1].mean()
        print(f"  0x{BASE+a*SEG:08X} {(b-a+1)*SEG//1024:>9}KB {d:>8.1%}")

    # ── ② 对最大候选区试三种 tile 尺寸 ────────────────────────────
    print("\n" + "=" * 78)
    print("② 对候选区试 tile 尺寸：变异系数最小者 = 真实字模尺寸")
    print("=" * 78)

    def tile_cv(rom: np.ndarray, off: int, size: int, tw: int, th: int,
                count: int = 512) -> tuple[float, float]:
        """按 tw×th 切 tile，返回 (墨量变异系数, 平均填充率)。
        只支持 8 或 16 宽的 4bpp/1bpp 常见格式，这里假设 1bpp 行对齐。"""
        row_bytes = tw // 8
        tb = row_bytes * th
        if off + tb * count > len(rom):
            count = (len(rom) - off) // tb
        if count < 16:
            return (9.9, 0)
        tiles = rom[off:off + tb * count].reshape(count, tb)
        # 每 tile 的墨量
        ink = np.unpackbits(tiles).reshape(count, tb * 8).sum(axis=1)
        cap = tb * 8
        fill = ink / cap
        cv = float(fill.std() / max(1e-9, fill.mean()))
        return (cv, float(fill.mean()))

    best_regions = runs[:6]
    for a, b in best_regions:
        off = a * SEG
        print(f"\n  区 0x{BASE+off:08X}（{(b-a+1)*SEG//1024}KB）")
        for tw, th, label in ((8, 8, "8×8  (1bpp tile)"),
                              (8, 12, "8×12"),
                              (8, 16, "8×16"),
                              (16, 16, "16×16"),
                              (8, 24, "8×24"),
                              (8, 32, "8×32")):
            cv, fill = tile_cv(ja, off, SEG, tw, th)
            mark = " ★最低" if cv < 0.25 else ""
            print(f"    {label:<18} 变异系数 {cv:>6.3f}  "
                  f"平均填充 {fill:>6.1%}{mark}")

    # ── ③ 已知的「日文字模区」对照 ───────────────────────────────
    print("\n" + "=" * 78)
    print("③ 对照：代码区（应无位图特征）")
    print("=" * 78)
    for off in (0x10000, 0x80000, 0x3DD000):
        for tw, th, label in ((8, 8, "8×8"), (8, 16, "8×16")):
            cv, fill = tile_cv(ja, off, SEG, tw, th)
            print(f"  0x{BASE+off:08X} {label:<6} 变异系数 {cv:>6.3f} "
                  f"填充 {fill:>6.1%}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
