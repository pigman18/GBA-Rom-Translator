#!/usr/bin/env python3
"""调研(74) 结论性验证：文字到底在不在 VRAM —— 用「像素级反查」定案。

═══════════════════════════════════════════════════════════════════════════
【目前的全部事实（都是实测，不是推断）】
═══════════════════════════════════════════════════════════════════════════
  1. emu:readRange 对 ROM 区可信（与 ROM 文件逐字节一致）
  2. IO 区读数与 IWRAM 开头 16 字节有 14/16 相同 ⇒ IO 读的是 IWRAM 镜像，
     不是真硬件寄存器（VCOUNT=0x9629 这种不可能值就是证据）
  3. VRAM 里 tile 1..288 全是 0xAA（未初始化标记），只有 tile 433..441
     是真实图形（菜单边框）
  4. 对 VRAM 穷举 4×32×2 种 charBase/screenBase/bpp 组合，
     最佳只能还原截图 **0.7%**
  5. 截图确实显示中文菜单（肉眼确认多次）

⇒ **结论必须改：中文字形不在这一帧的 VRAM 里。**

═══════════════════════════════════════════════════════════════════════════
【最后一个可能的藏身处：OAM（OBJ/sprite）】
═══════════════════════════════════════════════════════════════════════════
GBA 的 OBJ 用 OAM 表（0x07000000）描述位置，字形仍在 VRAM 的
「OBJ charBase」（DISPCNT bit 2-4 指定 0x06010000 的 0x0000/0x4000/...）。

若文字是 OBJ：
  · OAM 里会有大量 8×8 的 sprite 条目
  · 字形在 VRAM 的 OBJ 区

但 DISPCNT 读到 OBJ=0（虽然 IO 不可信）。所以这条也不确定。

【本脚本要做的事：不再猜，直接看 OAM】
  读 OAM 1024 字节 = 128 个 OBJ 条目 × 8 字节
  每个条目：attr0(8bit) attr1(16bit) attr2(16bit) + 2 字节填充
  统计有多少个 enabled 的 OBJ、它们的坐标分布

若 OAM 里有大量条目覆盖菜单区域 ⇒ 文字是 OBJ 画的。
若 OAM 全空 ⇒ 文字既不在 BG 也不在 OBJ，只能是「采集的帧根本不是显示帧」。

用法：python scripts/research/firered/74_check_oam.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "ewram3"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def main() -> int:
    print("=" * 78)
    print("① OAM 分析（128 个 OBJ 条目）")
    print("=" * 78)

    for tag in ("s1",):
        oam_p = OUT / f"{tag}.oam.bin"
        if not oam_p.exists():
            print(f"  没有 {oam_p.name}")
            continue
        oam = oam_p.read_bytes()
        print(f"  {tag}.oam.bin  {len(oam)} 字节 = {len(oam)//8} 个条目")

        enabled = []
        for k in range(len(oam) // 8):
            e = oam[k * 8:(k + 1) * 8]
            a0 = rd16(e, 0)
            a1 = rd16(e, 2)
            a2 = rd16(e, 4)
            # bit9 of attr0 = 1 ⇒ 禁用（rot/scale 模式之外）
            mode = (a0 >> 8) & 3
            is_rs = (a0 >> 8) & 1
            disabled = (a0 & 0x0200) != 0 if not is_rs else False
            if disabled:
                continue
            y = a0 & 0xFF
            x = a1 & 0x1FF
            tile = a2 & 0x3FF
            enabled.append((k, x, y, tile, mode))

        print(f"  未禁用条目：{len(enabled)}")
        for k, x, y, tile, mode in enabled[:20]:
            print(f"    OBJ[{k:>3}] x={x:>3} y={y:>3} tile={tile:>3} mode={mode}")

        if enabled:
            xs = [e[1] for e in enabled]
            ys = [e[2] for e in enabled]
            print(f"\n  x 范围 {min(xs)}..{max(xs)}  y 范围 {min(ys)}..{max(ys)}")
        else:
            print("\n  **OAM 全部禁用 ⇒ 没有 OBJ 在显示**")

    # ── ② 再确认 VRAM 里到底有多少「像字形」的 tile ─────────────────
    print("\n" + "=" * 78)
    print("② VRAM 里「像字形」的 tile 统计（排除 00/FF/AA 填充）")
    print("=" * 78)
    vram = (OUT / "s1.vram.bin").read_bytes()

    def kind(blob: bytes) -> str:
        s = set(blob)
        if s == {0x00}:
            return "全00"
        if s == {0xFF}:
            return "全FF"
        if s == {0xAA}:
            return "全AA"
        # 墨点：4bpp 视角
        ink = 0
        for b in blob:
            if (b & 0x0F):
                ink += 1
            if (b >> 4):
                ink += 1
        if ink == 0:
            return "无墨"
        if ink >= 60:
            return "满墨"
        return "有形状"

    from collections import Counter
    c = Counter()
    shapes = []
    for k in range(len(vram) // 32):
        blob = vram[k * 32:(k + 1) * 32]
        kd = kind(blob)
        c[kd] += 1
        if kd == "有形状":
            shapes.append(k)
    print(f"  总计 {len(vram)//32} 个 tile：")
    for kd, n in c.most_common():
        print(f"    {kd:<8} {n:>5}")
    print(f"\n  「有形状」的 tile：{len(shapes)} 个")
    if shapes:
        print(f"    编号（前 40）：{shapes[:40]}")
        print(f"\n  抽样 6 个画出来：")
        for t in shapes[:6]:
            blob = vram[t * 32:(t + 1) * 32]
            print(f"\n    tile {t}:")
            for y in range(8):
                row = blob[y * 4:(y + 1) * 4]
                line = ""
                for xx in range(8):
                    b = row[xx // 2]
                    p = (b & 0x0F) if xx % 2 == 0 else (b >> 4)
                    line += "." if p == 0 else "#"
                print(f"      {line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
