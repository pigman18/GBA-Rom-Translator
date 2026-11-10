#!/usr/bin/env python3
"""调研(120) 找「字形渲染函数」—— 从 BG 写 tilemap 的代码反向定位。

═══════════════════════════════════════════════════════════════════════════
【思路转变】
═══════════════════════════════════════════════════════════════════════════
前面一直在「找字库数据」，全部失败。改找**代码**：

要显示一个汉字，代码必须做两件事：
  ① 把字形数据写进 VRAM（或直接从 ROM 读着画）
  ② 在 tilemap 里写下 tile 编号

(107) 已确认：汉化**没有**新增任何 0x06000000 的引用
⇒ 写 VRAM 的代码是**原版**的

但原版写的是**日文假名/汉字**，而画面显示的是**简体中文**
⇒ 说明汉化必须改动「码位 → 字形」的映射，而不改「字形 → VRAM」的路径

【关键推论】
 如果字形→VRAM 走原版代码，那么**字库格式必须与原版一致**。
 原版火红的字库格式是什么？找它就知道中文在哪里。

【本脚本：找原版字库】
 原版火红（日版）的汉字/假名字库，位置可以通过「原版和汉化都不改」的区找。
 但更直接：原版 GBA 宝可梦的字库通常以「8×16 或 8×12 的 1bpp 位图」存，
 且**按码位顺序排列**（0x00, 0x01, 0x02 ...），所以相邻字形的数据高度相关。

 判据：找「连续很多个 32B 块，每块互不相同，但 nibble 分布相似」的区。

用法：python scripts/research/firered/120_find_render_code.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def main() -> int:
    ja = FR_JA.read_bytes()
    zh = FR_ZH.read_bytes()
    n = min(len(ja), len(zh))

    print("=" * 78)
    print("① 原版 ROM 里找「码位顺序排列的字库」")
    print("=" * 78)
    print("  判据：连续 512+ 个 32B 块，nibble 分布相似但内容不同")

    # 按 32B 块算 nibble 直方图，找连续的「相似但不同」区
    nblk = n // 32
    print(f"  原版共 {nblk:,} 个 32B 块")

    # 先把每块的 (唯一值数, nibble1数, nibble2数, 熵) 算出来
    feats = np.zeros((nblk, 4), dtype=np.float32)
    for k in range(nblk):
        blob = ja[k * 32:(k + 1) * 32]
        c = {}
        n1 = n2 = 0
        for b in blob:
            for v in (b & 0xF, b >> 4):
                c[v] = c.get(v, 0) + 1
                if v == 1:
                    n1 += 1
                elif v == 2:
                    n2 += 1
        feats[k] = (len(c), n1, n2, 0)

    # 找「n1 和 n2 都 > 0」的连续区
    valid = (feats[:, 1] > 0) & (feats[:, 2] > 0)
    runs = []
    i = 0
    while i < nblk:
        if valid[i]:
            j = i
            while j + 1 < nblk and valid[j + 1]:
                j += 1
            if j - i + 1 >= 128:
                runs.append((i, j - i + 1))
            i = j + 1
        else:
            i += 1
    runs.sort(key=lambda r: -r[1])
    print(f"  原版里「含 1 和 2 的连续块」≥128：{len(runs)} 个")
    for sb, cnt in runs[:12]:
        off = sb * 32
        print(f"    0x{BASE+off:08X}  {cnt} 块（{cnt*32:,} B）")

    # ── ② 这些区在汉化里改了吗 ────────────────────────────────
    print("\n" + "=" * 78)
    print("② 这些区在汉化版里的变化")
    print("=" * 78)
    for sb, cnt in runs[:12]:
        off = sb * 32
        a = ja[off:off + cnt * 32]
        b = zh[off:off + cnt * 32]
        diff = sum(1 for x, y in zip(a, b) if x != y)
        print(f"  0x{BASE+off:08X}  {cnt:>5} 块  改动 {diff:>7} 字节 "
              f"({diff/max(1,len(a))*100:>5.1f}%)")

    # ── ③ 画原版最大区的字形 ──────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 画原版最大 run 的前 6 块")
    print("=" * 78)
    if runs:
        sb, cnt = runs[0]
        off = sb * 32
        for k in range(6):
            blob = ja[off + k * 32: off + (k + 1) * 32]
            print(f"\n  块{k}: {blob[:16].hex(' ')}")
            for y in range(8):
                row = blob[y * 4:(y + 1) * 4]
                line = ""
                for x in range(8):
                    b = row[x // 2]
                    v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                    line += "." if v == 0 else ("+" if v == 1 else "#")
                print("    " + line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
