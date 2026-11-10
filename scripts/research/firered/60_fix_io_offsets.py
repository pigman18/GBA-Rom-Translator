#!/usr/bin/env python3
"""调研(60) 修正 IO 偏移 + 重采「真正变化」的多帧，从 tilemap 直接看汉字。

═══════════════════════════════════════════════════════════════════════════
【(58)/(59) 错在两处，都记下来当教训】
═══════════════════════════════════════════════════════════════════════════
 错 1 **IO 偏移算错**
     GBA IO 真实布局（0x04000000 起）：
       +0x00 DISPCNT   +0x02 DISPSTAT  +0x04 VCOUNT  +0x06 BG0HOFS
       +0x08 BG0CNT    +0x0A BG1CNT    +0x0C BG2CNT  +0x0E BG3CNT
       +0x10 BG0VOFS   ...
     我写的是 `rd16(io, 8 + b*2)` —— 对 b=0 恰好是 BG0CNT（对），
     但 b=1 读到 BG1CNT（对）… 其实偏移没错。
     **真正的错是**：我把 0x04000000 的 96 字节当成「从 DISPCNT 直接排到 BG3CNT」，
     中间忘了 VCOUNT/BGxHOFS 的占位。实测：
       0x04000000 起 u16: 3140 0000 9629 00A0 1E00 0000 1C0F ...
       即 DISPCNT=0x3140 DISPSTAT=0 VCOUNT=0x9629(其实是 BG0HOFS)
       BG0CNT=0x00A0  BG1CNT=0x1E00  BG2CNT=0  BG3CNT=0x1C0F
     ⇒ BG0CNT 是 **0x00A0**，不是我以为的 0x1E00。
       charBase=(0x00A0>>2)&3=0  screenBase=0x00A0>>8=0  4bpp
       BG1CNT=0x1E00 → charBase=0 screenBase=0x1E00>>8=0x1E(×0x800=0xF000)
     我之前把 BG1 的配置当成 BG0 了。

 错 2 **s2..s6 是同一帧**
     实测 VRAM/EWRAM 的 MD5 全同 ⇒ 只有 s1 是新的，之后画面冻住。
     原因：脚本在 `proved and frame > 760` 后每 200 帧 dump 一次，
     但游戏进了「继续游戏」菜单后**画面不再变**（静态菜单），
     所以 6 帧内容当然一样 —— 不是 bug，是**采样点没覆盖到不同界面**。

═══════════════════════════════════════════════════════════════════════════
【本脚本】
═══════════════════════════════════════════════════════════════════════════
 ① 用正确偏移重新解析已有的 s1（BG0CNT=0x00A0 → screenBase=0）
 ② 按 BG0 的真实 charBase/screenBase 读 tilemap，画出屏幕内容
 ③ 若能看到汉字 tile，直接分析它们的宽度（8 还是 12）

用法：python scripts/research/firered/60_fix_io_offsets.py
"""
from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "ewram3"

# GBA IO 真实偏移（0x04000000 起）
IO_OFF_DISPCNT = 0x00
IO_OFF_DISPSTAT = 0x02
IO_OFF_VCOUNT = 0x04
IO_OFF_BG0CNT = 0x08          # 注意：BG0CNT 在 +0x08
IO_OFF_BGXHOFS = 0x10 + 0    # BG0HOFS = 0x04000010
BG_CNT_BASE = 0x08


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def decode_bgcnt(v: int) -> dict:
    return {
        "charBase": ((v >> 2) & 3) * 0x4000,
        "screenBase": ((v >> 8) & 0x1F) * 0x800,
        "bpp8": bool((v >> 7) & 1),
        "size": v >> 14,
        "prio": v & 3,
    }


def main() -> int:
    io = (OUT / "s1.ioblk.bin").read_bytes()
    vram = (OUT / "s1.vram.bin").read_bytes()
    pal = (OUT / "s1.pal.bin").read_bytes()

    print("=" * 78)
    print("① 正确解析 s1 的 IO")
    print("=" * 78)
    d = rd16(io, IO_OFF_DISPCNT)
    print(f"  DISPCNT = 0x{d:04X}")
    print(f"    BG0={(d>>0)&1} BG1={(d>>1)&1} BG2={(d>>2)&1} BG3={(d>>3)&1} "
          f"OBJ={(d>>4)&1} WIN0={(d>>5)&1} WIN1={(d>>6)&1} "
          f"OBJWIN={(d>>7)&1} mode={(d>>13)&7}")
    print(f"\n  DISPSTAT = 0x{rd16(io, IO_OFF_DISPSTAT):04X}")
    print(f"  BG0HOFS  = {rd16(io, 0x10)}")
    print(f"  BG0VOFS  = {rd16(io, 0x12)}")
    print(f"  BG1HOFS  = {rd16(io, 0x14)}")
    print(f"  BG1VOFS  = {rd16(io, 0x16)}")

    print(f"\n  BG 寄存器：")
    for b in range(4):
        v = rd16(io, BG_CNT_BASE + b * 2)
        info = decode_bgcnt(v)
        on = (d >> b) & 1
        print(f"    BG{b}CNT=0x{v:04X} char=0x{info['charBase']:04X} "
              f"scr=0x{info['screenBase']:04X} "
              f"{'8bpp' if info['bpp8'] else '4bpp'} "
              f"size={info['size']} prio={info['prio']} "
              f"{'ON' if on else 'off'}")

    # ── ② 按正确的层配置读 tilemap ────────────────────────────────
    print("\n" + "=" * 78)
    print("② 按正确配置读 tilemap，找出有文字的行")
    print("=" * 78)
    for b in range(4):
        if not ((d >> b) & 1):
            continue
        v = rd16(io, BG_CNT_BASE + b * 2)
        info = decode_bgcnt(v)
        cb, sb = info["charBase"], info["screenBase"]
        bpp8 = info["bpp8"]
        if sb + 0x800 > len(vram):
            print(f"  BG{b}: screenBase 0x{sb:04X} 越界")
            continue
        tm = vram[sb:sb + 0x800]
        print(f"\n  ---- BG{b} char=0x{cb:04X} scr=0x{sb:04X} "
              f"{'8bpp' if bpp8 else '4bpp'} ----")
        rows = []
        for row in range(20):
            ents = [rd16(tm, (row * 32 + c) * 2) for c in range(30)]
            nz = sum(1 for e in ents if (e & 0x3FF))
            if nz > 2:
                rows.append((row, nz, ents))
        print(f"    有内容的行：{len(rows)}")
        for row, nz, ents in rows[:10]:
            print(f"      行{row:>2}: {nz:>2} tile, 序号 "
                  f"{[e & 0x3FF for e in ents[:12]]}")

        # 画前 3 行
        for row, nz, ents in rows[:3]:
            print(f"\n      行{row} 像素：")
            for lr in range(8):
                line = ""
                for c in range(20):
                    e = ents[c]
                    tidx = e & 0x3FF
                    if bpp8:
                        off = cb + tidx * 64
                        if off + 64 > len(vram):
                            line += "?" * 8
                            continue
                        blob = vram[off:off + 64]
                        rb = blob[lr * 8:(lr + 1) * 8]
                        s = "".join("#" if x else "." for x in rb)
                    else:
                        off = cb + tidx * 32
                        if off + 32 > len(vram):
                            line += "?" * 8
                            continue
                        blob = vram[off:off + 32]
                        rb = blob[lr * 4:(lr + 1) * 4]
                        s = ""
                        for col in range(8):
                            byte = rb[col // 2]
                            pix = (byte & 0x0F) if col % 2 == 0 else (byte >> 4)
                            s += "#" if pix else "."
                    if (e >> 10) & 1:
                        s = s[::-1]
                    line += s
                print(f"        |{line}|")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
