#!/usr/bin/env python3
"""调研(57) 用「屏幕像素」当锚点反查中文来源 —— 不再猜地址。

═══════════════════════════════════════════════════════════════════════════
【为什么换方法】
═══════════════════════════════════════════════════════════════════════════
前面所有失败都源于：**从反汇编猜地址，然后去那个地址找东西**。
  · 猜 0x0203F2C0 是 F7 表 → 实测全 0
  · 猜「TABLE[hi] 指向字符序列」 → EWRAM 只有 361 个 ROM 指针，无支撑

现在改成：**屏幕上确实显示了中文**，就从屏幕反推。

═══════════════════════════════════════════════════════════════════════════
【反查链】
═══════════════════════════════════════════════════════════════════════════
  PNG 像素 → 哪些 tile 在显示 → VRAM 里那些 tile 的内容
           → tile 序号 → tilemap 表项
           → 但**先说清一件事**：汉字是 8×8 tile 拼的，还是 12×12？

关键判据（不需要知道任何地址）：
  在 VRAM 里，把 tile 按 8×8 切出来，找出「墨点密度像汉字」的 tile，
  然后看它们的**相邻关系**：
    · 若是 8+4/4+8 拼，会看到「左半满、右半窄」成对出现
    · 若是 12×12 单字模，会看到 2×2 tile 组（但每格内容不同）

同时做一件更直接的事：**在 EWRAM/VRAM 里搜 F7 序列**。
  中文文本在显示前必然以 F7 形式存在于某处。
  找到 F7 出现的位置，就知道文本缓冲区在哪，进而知道它怎么被转成字形。

用法：python scripts/research/firered/57_pixel_anchor.py
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "ewram3"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def read16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def main() -> int:
    zh = ROM_ZH.read_bytes()
    n = len(zh)

    # ── ① 在 EWRAM 里搜 F7 序列（中文文本缓冲区在哪）──────────────
    print("=" * 78)
    print("① EWRAM 里的 F7 字节序列（中文文本必须存在于某处）")
    print("=" * 78)
    for tag in ("s1", "s3", "s6"):
        ew = (OUT / f"{tag}.ewram.bin").read_bytes()
        pos = []
        i = ew.find(b"\xf7")
        while i >= 0:
            pos.append(i)
            i = ew.find(b"\xf7", i + 1)
        print(f"\n  {tag}: EWRAM 里 F7 出现 {len(pos)} 次")
        if pos:
            # 聚成区间
            runs = []
            s = p = pos[0]
            for x in pos[1:]:
                if x - p <= 16:
                    p = x
                else:
                    runs.append((s, p))
                    s = p = x
            runs.append((s, p))
            print(f"    聚成 {len(runs)} 段，前 8 段：")
            for s, e in runs[:8]:
                blob = ew[max(0, s - 8):e + 16]
                print(f"      0x{0x02000000+s:08X}..0x{0x02000000+e:08X} "
                      f"({e-s+1} B)")
                print(f"        {blob.hex(' ')}")

    # ── ② VRAM 里找汉字 tile ───────────────────────────────────────
    print("\n" + "=" * 78)
    print("② VRAM 里的 tile 分析（8×8，4bpp 与 8bpp 都算）")
    print("=" * 78)
    vram = (OUT / "s1.vram.bin").read_bytes()
    io = (OUT / "s1.ioblk.bin").read_bytes()
    dispcnt = read16(io, 0)
    print(f"  DISPCNT = 0x{dispcnt:04X}")
    for b in range(4):
        v = read16(io, 8 + b * 2)
        print(f"  BG{b}CNT = 0x{v:04X}  charBase={((v>>2)&3)*0x4000:04X} "
              f"screenBase={((v>>8)&0x1F)*0x800:04X} "
              f"{'8bpp' if (v>>7)&1 else '4bpp'} "
              f"size={v>>14}")

    # 4bpp：每 tile 32 字节。统计每个 tile 的非零像素数
    print(f"\n  按 4bpp 切 8×8 tile（32 B/tile）共 {len(vram)//32} 个")
    tiles = []
    for k in range(len(vram) // 32):
        blob = vram[k * 32:(k + 1) * 32]
        # 4bpp: 每字节两个像素
        ink = 0
        for byte in blob:
            lo = byte & 0x0F
            hi = byte >> 4
            ink += (lo != 0) + (hi != 0)
        tiles.append(ink)
    t = np.array(tiles)
    print(f"  墨点数：均值 {t.mean():.1f} 中位 {np.median(t):.0f} "
          f"最大 {t.max()}")
    # 汉字 tile：墨点 8~50（太满/太空都不是字）
    cand = np.flatnonzero((t >= 8) & (t <= 50))
    print(f"  墨点 8~50 的 tile：{len(cand)} 个")

    # ── ③ 相邻 tile 的「配对」特征：8+4 拼 vs 独立字模 ────────────
    print("\n" + "=" * 78)
    print("③ 判定 8+4/4+8 拼接：看 tile 的左右半墨量分布")
    print("=" * 78)
    print("  若汉字由 8+4 拼：会同时出现「左满右空」和「左空右满」的 tile")
    print("  若是独立 12×12 字模：每个 tile 左右墨量应比较均衡")

    def half_ink(blob: bytes) -> tuple[int, int]:
        left = right = 0
        for row in range(8):
            rb = blob[row * 4:(row + 1) * 4]
            for col in range(8):
                byte = rb[col // 2]
                pix = (byte & 0x0F) if col % 2 == 0 else (byte >> 4)
                if pix:
                    if col < 4:
                        left += 1
                    else:
                        right += 1
        return left, right

    lopsided = 0
    balanced = 0
    for k in cand[:2000]:
        blob = vram[k * 32:(k + 1) * 32]
        L, R = half_ink(blob)
        tot = L + R
        if tot == 0:
            continue
        ratio = L / tot
        if ratio < 0.25 or ratio > 0.75:
            lopsided += 1
        else:
            balanced += 1
    print(f"\n  检查 {min(len(cand),2000)} 个候选 tile：")
    print(f"    左右失衡（<25% 或 >75%）：{lopsided}")
    print(f"    左右均衡：{balanced}")
    if lopsided + balanced:
        print(f"    ⇒ 失衡占比 {lopsided/(lopsided+balanced)*100:.1f}%")

    # ── ④ 直接看几个候选 tile 的像素 ───────────────────────────────
    print("\n" + "=" * 78)
    print("④ 打印候选 tile 的 8×8 像素（人眼看是不是半个汉字）")
    print("=" * 78)
    shown = 0
    for k in cand:
        blob = vram[k * 32:(k + 1) * 32]
        L, R = half_ink(blob)
        if L + R < 10:
            continue
        print(f"\n  tile#{k}  left={L} right={R}")
        for row in range(8):
            rb = blob[row * 4:(row + 1) * 4]
            line = ""
            for col in range(8):
                byte = rb[col // 2]
                pix = (byte & 0x0F) if col % 2 == 0 else (byte >> 4)
                line += "#" if pix else "."
            print(f"    {line}")
        shown += 1
        if shown >= 6:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
