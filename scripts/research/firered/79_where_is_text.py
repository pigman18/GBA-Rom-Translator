#!/usr/bin/env python3
"""调研(79) 定性：mGBA 的 readRange 在 VRAM/OAM 上是否可靠。

═══════════════════════════════════════════════════════════════════════════
【铁证累积】
═══════════════════════════════════════════════════════════════════════════
  E1 ROM 区 readRange 可信（与 ROM 文件逐字节相同）
  E2 IO 区读到 VCOUNT=0x9629（GBA 上不可能）——但修正位定义后发现
     DISPCNT 值本身是合理（0x3140/0x7F60），只是我先前位解读错了
  E3 **VRAM 在 g1..g4 四个不同时刻 MD5 完全相同 52fc9d7c53**，
     而四张 PNG 各不相同 ⇒ VRAM 读数没有跟着画面变化
  E4 OAM 128 个条目全是 x=304 y=160 tile=0（明显填充值）
  E5 VRAM 里只有 72 个中等墨量 tile，全是菜单边框，无文字字形

⇒ 强烈怀疑：**readRange 对 VRAM/OAM 返回的是启动时的快照**，
  或该构建的 readRange 只对 ROM/EWRAM 实时。

【决定性测试】
 ① 同一帧里：readRange(VRAM) 与 read16 逐点读 VRAM 对比
 ② 跨帧：按 A 让画面剧变（菜单→野外），VRAM 是否变化
 ③ 对照 EWRAM：EWRAM 是否会变（(75) 显示 EWRAM 的 T1/T2 有变化吗？）

(75) 里 T1 VRAM=D9912110，T2 VRAM=F9A4EB94 —— **VRAM 那时是变的！**
但 g1..g4 与 s1..s6 全是 52fc9d7c53。

⇒ 说明 52fc9d7c53 是「停在标题/菜单不动」时的稳定值，
  一旦画面真的切换（菜单→野外），VRAM 才变。
  所以**不是冻结，而是菜单期间 VRAM 真的没变**。

那么问题转向：**菜单画面的 VRAM 里为什么没有文字字形？**

用法：python scripts/research/firered/79_where_is_text.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"
FROZEN = ROOT / "work" / "_probe" / "frozen"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def main() -> int:
    from PIL import Image

    print("=" * 78)
    print("① 三个不同来源的 VRAM 指纹对比")
    print("=" * 78)
    import hashlib
    for p in (OUT / "g1.vram.bin", OUT / "g4.vram.bin"):
        if p.exists():
            print(f"  {p.name}: {hashlib.md5(p.read_bytes()).hexdigest()[:12]}")

    # ── ② 直接从 PNG 反推：文字区域的像素值 ──────────────────────
    print("\n" + "=" * 78)
    print("② 从 g1.png 找文字像素（黑字在白底上）")
    print("=" * 78)
    png = OUT / "g1.png"
    target = np.asarray(Image.open(png).convert("RGB"), dtype=np.uint8)
    print(f"  图像 {target.shape}")
    # 统计每行「非白非边框」的像素数
    white = (target[:, :, 0] > 240) & (target[:, :, 1] > 240) & \
            (target[:, :, 2] > 240)
    dark = (target[:, :, 0] < 100) & (target[:, :, 1] < 100) & \
           (target[:, :, 2] < 100)
    print(f"  白色像素 {white.sum():,}  深色像素 {dark.sum():,}")
    print(f"\n  每行深色像素数（找文字行）：")
    for y in range(0, 160, 4):
        n = int(dark[y:y + 4].sum())
        if n > 0:
            bar = "#" * min(60, n // 2)
            print(f"    y={y:>3}: {n:>4}  {bar}")

    # ── ③ 文字行的实际字形尺寸 ───────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 量字形尺寸：在文字行上找连通的深色列")
    print("=" * 78)
    # 找一个深色最多的行带
    rowsum = dark.sum(axis=1)
    y0 = int(np.argmax(rowsum))
    print(f"  深色最多的行 y={y0}，该行深色 {int(rowsum[y0])} 像素")
    band = dark[max(0, y0 - 2):y0 + 3].any(axis=0)
    # 找连续 True 段（= 笔画列）
    runs = []
    i = 0
    while i < len(band):
        if band[i]:
            j = i
            while j + 1 < len(band) and band[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    print(f"  该行有 {len(runs)} 段深色，前 20 段 (起,止,宽):")
    for a, b in runs[:20]:
        print(f"    ({a:>3},{b:>3}) 宽={b-a+1}")

    # ── ④ 文字整体区域：裁一块画出来 ─────────────────────────────
    print("\n" + "=" * 78)
    print("④ 裁文字区域画成 ASCII（人能看出是不是汉字）")
    print("=" * 78)
    # 取 y 在文字带附近、x 从 0 到 120
    ys = [y for y in range(160) if rowsum[y] > 3]
    if ys:
        ylo, yhi = min(ys), max(ys)
        print(f"  有深色的行范围：y={ylo}..{yhi}")
        y1 = min(yhi + 1, ylo + 16)
        sub = dark[ylo:y1, 0:100]
        for r in range(sub.shape[0]):
            line = "".join("#" if sub[r, c] else "." for c in range(sub.shape[1]))
            print(f"    {line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
