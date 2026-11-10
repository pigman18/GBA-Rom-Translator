#!/usr/bin/env python3
"""调研(59) BG 全关闭 ⇒ 文字走 OBJ？查 OAM 与特殊显示模式。

═══════════════════════════════════════════════════════════════════════════
【(58) 的关键发现】
═══════════════════════════════════════════════════════════════════════════
DISPCNT = 0x3140：
    bit0-3 (BG0-BG3 使能) = 0        ← 全部关闭
    bit4   (OBJ 使能)     = 0
    bit5   (WIN0)         = 0
    bit6   (WIN1)         = 0
    bit7   (OBJWIN)       = 1        ← ★
    bit8-12 = 0x31 = 110001
    bit13-15 (BG mode) = 0

   0x3140 = 0011 0001 0100 0000
   bit0-3 = 0000   BG 全关
   bit4 = 0        OBJ 关
   bit5 = 0        WIN0 关
   bit6 = 0        WIN1 关
   bit7 = 1        ★ OBJWIN 开
   bit8 = 1
   bit9 = 0
   bit10 = 0
   bit11 = 0
   bit12 = 1
   bit13-15 = 000  BG mode 0

⇒ **BG 全关 + OBJWIN 开**。这非常反常。

两种可能：
  a) 这个 dump 撞在了转场/淡出的中间帧（画面其实是黑屏或过渡）
  b) 火红用 OBJWIN + 某种混合做文字

必须**同时看 PNG** 与寄存器才能判断。若 PNG 有中文而 BG 全关，
说明这一帧是「窗口特效帧」，我之前抓的时机不对。

═══════════════════════════════════════════════════════════════════════════
【本脚本】
═══════════════════════════════════════════════════════════════════════════
 ① 打印 6 个状态各自的 DISPCNT / OAM 数量，找出「BG 真的开着」的那帧
 ② 对 BG 开着且 4bpp 的帧，读 tilemap 并画出来
 ③ 若都不开 BG，则检查 OAM（OBJ 路线）

用法：python scripts/research/firered/59_dispcnt_scan.py
"""
from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "ewram3"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def main() -> int:
    print("=" * 78)
    print("① 6 个状态的显示配置对比")
    print("=" * 78)
    print(f"  {'tag':>4} {'DISPCNT':>8} {'BG0-3':>7} {'OBJ':>4} "
          f"{'WIN0':>5} {'WIN1':>5} {'OBJWIN':>7} {'BGmode':>7}")
    for i in range(1, 7):
        io = (OUT / f"s{i}.ioblk.bin").read_bytes()
        d = rd16(io, 0)
        bgs = "".join(str((d >> b) & 1) for b in range(3, -1, -1))
        obj = (d >> 4) & 1
        w0 = (d >> 5) & 1
        w1 = (d >> 6) & 1
        ow = (d >> 7) & 1
        mode = (d >> 13) & 7
        print(f"  s{i:>3} 0x{d:04X} {bgs:>7} {obj:>4} {w0:>5} {w1:>5} "
              f"{ow:>7} {mode:>7}")

    # ── ② 对每个状态读 BGxCNT ─────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 各状态的 BGxCNT")
    print("=" * 78)
    for i in range(1, 7):
        io = (OUT / f"s{i}.ioblk.bin").read_bytes()
        d = rd16(io, 0)
        print(f"\n  s{i}  DISPCNT=0x{d:04X}")
        for b in range(4):
            v = rd16(io, 8 + b * 2)
            cb = ((v >> 2) & 3) * 0x4000
            sb = ((v >> 8) & 0x1F) * 0x800
            print(f"    BG{b}CNT=0x{v:04X} char=0x{cb:04X} scr=0x{sb:04X} "
                  f"{'8bpp' if (v>>7)&1 else '4bpp'} "
                  f"{'ON' if (d>>b)&1 else 'off'}")

    # ── ③ 找「BG0 开着」的状态，读它的 tilemap ────────────────────
    print("\n" + "=" * 78)
    print("③ 寻找 BG 真的开着的状态并解析")
    print("=" * 78)
    found = False
    for i in range(1, 7):
        io = (OUT / f"s{i}.ioblk.bin").read_bytes()
        d = rd16(io, 0)
        if not (d & 0x0F):
            continue
        found = True
        vram = (OUT / f"s{i}.vram.bin").read_bytes()
        print(f"\n  s{i} 有 BG 开启")
        for b in range(4):
            if not ((d >> b) & 1):
                continue
            v = rd16(io, 8 + b * 2)
            cb = ((v >> 2) & 3) * 0x4000
            sb = ((v >> 8) & 0x1F) * 0x800
            bpp8 = (v >> 7) & 1
            if sb + 0x800 > len(vram):
                continue
            tm = vram[sb:sb + 0x800]
            nz_rows = []
            for row in range(20):
                ents = [rd16(tm, (row * 32 + c) * 2) for c in range(30)]
                nz = sum(1 for e in ents if (e & 0x3FF))
                if nz > 3:
                    nz_rows.append((row, nz, ents))
            print(f"    BG{b} char=0x{cb:04X} scr=0x{sb:04X} "
                  f"{'8bpp' if bpp8 else '4bpp'}  有内容行 {len(nz_rows)}")
            if not nz_rows:
                continue
            # 画第一行
            row, nz, ents = nz_rows[0]
            print(f"      行{row}（{nz} 个 tile）画出来：")
            for lr in range(8):
                line = ""
                for c in range(16):
                    e = ents[c]
                    tidx = e & 0x3FF
                    if bpp8:
                        off = cb + tidx * 64
                        if off + 64 > len(vram):
                            line += "?" * 8
                            continue
                        blob = vram[off:off + 64]
                        rb = blob[lr * 8:(lr + 1) * 8]
                        line += "".join("#" if x else "." for x in rb)
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

    if not found:
        print("  **6 个状态里 BG 全关** ⇒ 这批 dump 都撞在过渡帧/窗口特效上")
        print("  ⇒ 需要重采：等到 BG 稳定开启的帧再 dump")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
