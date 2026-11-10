#!/usr/bin/env python3
"""调研(76) 用**正确的 GBA 位定义**重做 —— 我之前读错了 DISPCNT。

═══════════════════════════════════════════════════════════════════════════
【我犯的错（根因，必须记下来）】
═══════════════════════════════════════════════════════════════════════════
我一直以为 DISPCNT 的 BG 使能是 bit0-3。**错。**

GBA DISPCNT (0x04000000) 真实位定义：
    bit0-2   BG Mode (0-5)
    bit3     CGB mode
    bit4     Frame select
    bit5     HBlank interval free
    bit6     OBJ character VRAM mapping (0=0x06010000, 1=0x06014000)
    bit7     Forced blank
    **bit8     Enable BG0**
    **bit9     Enable BG1**
    **bit10    Enable BG2**
    **bit11    Enable BG3**
    **bit12    Enable OBJ**
    bit13    Enable Window 0
    bit14    Enable Window 1
    bit15    Enable OBJ Window

验证：
    0x7F60 = 0111 1111 0110 0000
      bit0-2 = 000 → mode 0
      bit5,6 = 1,1
      bit7   = 0 （未强制空白）
      bit8-11 = 1111 → **BG0-3 全开** ✓
      bit12  = 1 → OBJ 开 ✓
      bit13,14 = 1,1 → 窗口开
    ⇒ 这是标准的**野外画面**配置，完全正常！

    0x3140 = 0011 0001 0100 0000
      bit0-2 = 000 → mode 0
      bit6   = 1
      bit8   = 1 → **BG0 开** ✓
      bit9-11 = 000
      bit12  = 1 → OBJ 开 ✓
      bit13  = 1 → WIN0 开
    ⇒ 标准菜单画面，也正常！

【同理 BGxCNT 的寄存器地址】
    0x04000006 BG0CNT
    0x04000008 BG1CNT
    0x0400000A BG2CNT
    0x0400000C BG3CNT
    0x0400000E BG0HOFS
    （BGAFF 之前我按 0x04000008 当 BG0CNT，实际那是 BG1CNT）

⚠ bot.lua 里 `emu:read16(0x04000008 + b*2)` 取 b=0 得到 0x04000008，
   按硬件手册那是 **BG1CNT**。但 bot 的注释说「BG0CNT=1F08 ⇒ charBase=2 screenBase=31」，
   1F08 的 screenBase = 0x1F*0x800 = 0xF800 —— 这条注释的换算与硬件手册一致
   （screenBase 用 (v>>8)&0x1F），所以 bot 只是把「寄存器索引」挪了一位，
   数值含义仍自洽。不影响本脚本。

═══════════════════════════════════════════════════════════════════════════
【本脚本】
═══════════════════════════════════════════════════════════════════════════
 ① 正确解析 t2（野外，dc=0x7F60）的四层 BG
 ② 按正确 charBase/screenBase 渲染，与 t2.png 比对
 ③ 若还原成功 ⇒ 证明了正确读法，可继续定位字形

用法：python scripts/research/firered/76_correct_bits.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FROZEN = ROOT / "work" / "_probe" / "frozen"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def decode_dispcnt(v: int) -> dict:
    return {
        "mode": v & 7,
        "forced_blank": (v >> 7) & 1,
        "bg": [(v >> (8 + i)) & 1 for i in range(4)],
        "obj": (v >> 12) & 1,
        "win0": (v >> 13) & 1,
        "win1": (v >> 14) & 1,
        "objwin": (v >> 15) & 1,
    }


def decode_bgcnt(v: int) -> dict:
    return {
        "prio": v & 3,
        "charBase": ((v >> 2) & 3) * 0x4000,
        "bpp8": bool((v >> 7) & 1),
        "screenBase": ((v >> 8) & 0x1F) * 0x800,
        "size": v >> 14,
    }


def render_bg(vram: bytes, cb: int, sb: int, bpp8: bool,
              hoff: int = 0, voff: int = 0) -> np.ndarray:
    out = np.zeros((160, 240), dtype=np.uint8)
    tb = 64 if bpp8 else 32
    for py in range(160):
        row = (py + voff) // 8
        for px in range(240):
            col = (px + hoff) // 8
            if row >= 32 or col >= 32:
                continue
            eo = sb + (row * 32 + col) * 2
            if eo + 2 > len(vram):
                continue
            ent = rd16(vram, eo)
            tidx = ent & 0x3FF
            hf, vf = (ent >> 10) & 1, (ent >> 11) & 1
            pil = (ent >> 12) & 0xF
            ly, lx = (py + voff) % 8, (px + hoff) % 8
            if vf:
                ly = 7 - ly
            if hf:
                lx = 7 - lx
            to = cb + tidx * tb
            if bpp8:
                if to + ly * 8 + lx < len(vram):
                    out[py, px] = vram[to + ly * 8 + lx]
            else:
                by = to + ly * 4 + lx // 2
                if by < len(vram):
                    b = vram[by]
                    p = (b & 0x0F) if lx % 2 == 0 else (b >> 4)
                    if p:
                        out[py, px] = pil * 16 + p
    return out


def to_rgb(pal: bytes, idx: np.ndarray) -> np.ndarray:
    cols = []
    for i in range(256):
        v = rd16(pal, i * 2) if (i * 2 + 2) <= len(pal) else 0
        cols.append(((v & 0x1F) * 255 // 31,
                     ((v >> 5) & 0x1F) * 255 // 31,
                     ((v >> 10) & 0x1F) * 255 // 31))
    return np.array(cols, dtype=np.uint8)[idx]


def main() -> int:
    from PIL import Image

    png = FROZEN / "t2.png"
    if not png.exists():
        print("缺 t2.png，先跑 75")
        return 1
    target = np.asarray(Image.open(png).convert("RGB"), dtype=np.uint8)

    # t2 那批的内存没存下来，只能用 75 日志里的 IO 值
    # 但 75 只存了 png。改从 ewram3 的 s1（菜单）继续，先验证位定义
    print("=" * 78)
    print("① 先验证位定义（用 75 记下的 DISPCNT）")
    print("=" * 78)
    for name, v in (("野外 t2", 0x7F60), ("菜单 s1", 0x3140)):
        d = decode_dispcnt(v)
        print(f"  {name}: 0x{v:04X}")
        print(f"    mode={d['mode']} forced_blank={d['forced_blank']} "
              f"BG={d['bg']} OBJ={d['obj']} "
              f"WIN0={d['win0']} WIN1={d['win1']}")

    print("\n" + "=" * 78)
    print("② 用 ewram3/s1（菜单）正确解析四层 BG")
    print("=" * 78)
    E = ROOT / "work" / "_probe" / "ewram3"
    vram = (E / "s1.vram.bin").read_bytes()
    pal = (E / "s1.pal.bin").read_bytes()
    io = (E / "s1.ioblk.bin").read_bytes()

    dc = rd16(io, 0)
    d = decode_dispcnt(dc)
    print(f"  DISPCNT = 0x{dc:04X}  mode={d['mode']} "
          f"BG={d['bg']} OBJ={d['obj']}")

    # 正确的寄存器地址
    BGCNT_ADDR = [0x06, 0x08, 0x0A, 0x0C]
    print(f"\n  {'层':>3} {'BGxCNT':>8} {'使能':>5} {'charBase':>9} "
          f"{'screenBase':>11} {'色深':>6} {'prio':>5}")
    layers = []
    for b in range(4):
        v = rd16(io, BGCNT_ADDR[b])
        info = decode_bgcnt(v)
        on = d["bg"][b]
        layers.append((b, v, info, on))
        print(f"  BG{b}  0x{v:04X}  {on:>5}  0x{info['charBase']:04X}   "
              f"   0x{info['screenBase']:04X} "
              f"{'8bpp' if info['bpp8'] else '4bpp':>6} {info['prio']:>5}")

    print("\n" + "=" * 78)
    print("③ 对每个「使能」的层渲染，与 s1.png 比对")
    print("=" * 78)
    for b, v, info, on in layers:
        if not on:
            print(f"  BG{b}: 未使能，跳过")
            continue
        idx = render_bg(vram, info["charBase"], info["screenBase"],
                        info["bpp8"])
        rgb = to_rgb(pal, idx)
        same = int((rgb == target).all(axis=2).sum())
        print(f"  BG{b}: 还原度 {same/(240*160):>6.1%}  "
              f"(char=0x{info['charBase']:04X} scr=0x{info['screenBase']:04X} "
              f"{'8bpp' if info['bpp8'] else '4bpp'})")

    print("\n" + "=" * 78)
    print("④ 找 BG0 的真实 tilemap 内容（BG0 使能了）")
    print("=" * 78)
    b0 = decode_bgcnt(rd16(io, 0x06))
    sb = b0["screenBase"]
    cb = b0["charBase"]
    print(f"  BG0: charBase=0x{cb:04X} screenBase=0x{sb:04X} "
          f"{'8bpp' if b0['bpp8'] else '4bpp'}")
    print(f"  tilemap 前 40 个表项：")
    for r in range(2):
        ents = [rd16(vram, sb + (r * 32 + c) * 2) for c in range(20)]
        print(f"    row{r}: {[e & 0x3FF for e in ents]}")

    # 画前两行
    tb = 64 if b0["bpp8"] else 32
    print(f"\n  画出前两行（charBase=0x{cb:04X}, {'8bpp' if b0['bpp8'] else '4bpp'}）：")
    for r in range(2):
        for ly in range(8):
            line = ""
            for c in range(20):
                ent = rd16(vram, sb + (r * 32 + c) * 2)
                tidx = ent & 0x3FF
                to = cb + tidx * tb
                if b0["bpp8"]:
                    if to + ly * 8 + 4 < len(vram):
                        v = vram[to + ly * 8 + 4]
                        line += "." if v == 0 else "#"
                    else:
                        line += "?"
                else:
                    if to + ly * 4 + 2 < len(vram):
                        bb = vram[to + ly * 4 + 2]
                        line += "." if bb == 0 else "#"
                    else:
                        line += "?"
            print(f"    |{line}|")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
