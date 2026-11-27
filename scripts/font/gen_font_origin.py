#!/usr/bin/env python3
"""生成 font.origin.s —— 美版数字字形「原样 12 行」写入日版血条字库（up + lo 双槽）。

═══════════════════════════════════════════════════════════════════
一、为什么需要这张 up 表（问题本质）
═══════════════════════════════════════════════════════════════════
日版（AXVJ）血条数字的槽结构：
    up : FontType1Map[glyph*4]   —— 实测 10 个数字全是 212
         → 0x081B51AC + 212*32 = 0x081B6C2C，内容全 0（**共用，不用**）
    lo : FontType1Map[glyph*4+1] —— 118..127，各不相同
         → 0x081B606C..0x081B618C，字形塞在 lo 的 row1-7（7 行）

美版（AXVE）血条数字的槽结构（GDB 出口探针 0x08003AC4 实测）：
    up = 0x08EA5484 + (glyph-0xA1)*0x40
    lo = up + 0x20
    字形跨 up row2-7 + lo row0-5，合计 **12 行高**

把 12 行压成 7 行（第一版做法）→ 顶底横线被压没、笔画 2px→1px，
屏幕上数字瘦成残笔（用户截图反馈"效果差很多"）。

═══════════════════════════════════════════════════════════════════
二、本脚本的方案：给 up 另开独立表
═══════════════════════════════════════════════════════════════════
hook 的 grid_draw_pcs 本来就是双格渲染：
    grid_copy32(gp,      up);    // gp[0..31]  = 上半格 8 行
    grid_copy32(gp + 32, lo);    // gp[32..63] = 下半格 8 行
即渲染空间天然是 16 行。障碍只在「up 是所有数字共用的固定地址」。

FontType1Map 的 up_idx 是 u8、可寻址 idx 0..255，实测其中全零槽只有
212/220/236 三个 —— 不够 10 个数字各占一槽。所以不改 FontType1Map，
改为在 hook 里特判（见 PrintNextChar_hook.c）：

    if (fn == 4u && glyph >= 0xA1u && glyph <= 0xAAu)
        up = ADDR_FONT_DIGIT_UP + (glyph - 0xA1u) * 32u;

本脚本负责两件事：
    1. 把美版 12 行字形按原样拆分：row0-7 → 写入 ADDR_FONT_DIGIT_UP 表
                                   row8-15 → 写入日版原 lo 槽
    2. 不做任何缩放，笔画密度与原版一致

═══════════════════════════════════════════════════════════════════
三、ADDR_FONT_DIGIT_UP 选址依据
═══════════════════════════════════════════════════════════════════
0x09F00700 起 1MB 实测全是 0xFF 对齐填充（最后一个真实数据结束于
0x09F006C0，同一次实测确认）。占 10*32 = 320B。

用法
====
    python scripts/font/gen_font_origin.py
    python scripts/font/gen_font_origin.py --verify
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

US_ROM = ROOT / "roms/origin/Pokemon Ruby Version 1.1(US).gba"

# 美版 up 地址（GDB 出口探针 0x08003AC4 实测；lo = up + 0x20，up 步长 0x40）
US_BASE_ADDR = 0x08EA5484
US_BASE_GLYPH = 0xA1
US_UP_STEP = 0x40

# 本项目自建的数字「上半格」表（与 hook 里 ADDR_FONT_DIGIT_UP 必须一致）
DIGIT_UP_ADDR = 0x09F00700

# 日版原 lo 槽（FontType1Map[glyph*4+1] 反汇编 + GDB 实测）
JP_LO: dict[int, int] = {
    0xA1: 0x081B606C,
    0xA2: 0x081B608C,
    0xA3: 0x081B60AC,
    0xA4: 0x081B60CC,
    0xA5: 0x081B60EC,
    0xA6: 0x081B610C,
    0xA7: 0x081B612C,
    0xA8: 0x081B614C,
    0xA9: 0x081B616C,
    0xAA: 0x081B618C,
}

GLYPH_NAMES = {
    0xA1: "0", 0xA2: "1", 0xA3: "2", 0xA4: "3", 0xA5: "4",
    0xA6: "5", 0xA7: "6", 0xA8: "7", 0xA9: "8", 0xAA: "9",
}

BG, SHADOW, INK = 0, 14, 15


def read_us_8x16(us: bytes, gidx: int) -> list[list[int]]:
    """美版 up(32B)+lo(32B) → 8x16 nibble 网格（lo nibble 为左像素）。"""
    up = US_BASE_ADDR + (gidx - US_BASE_GLYPH) * US_UP_STEP
    lo = up + 0x20
    grid: list[list[int]] = []
    for addr in (up, lo):
        off = addr - 0x08000000
        chunk = us[off:off + 32]
        if len(chunk) != 32:
            raise SystemExit(f"error: 美版 ROM 越界 0x{addr:08X} (glyph 0x{gidx:02X})")
        for y in range(8):
            grid.append([
                ((chunk[y * 4 + x // 2] & 0x0F) if x % 2 == 0
                 else (chunk[y * 4 + x // 2] >> 4))
                for x in range(8)
            ])
    return grid


def pack_8x8(grid8: list[list[int]]) -> bytes:
    """8 行 nibble 网格 → 32B（lo nibble 为左像素）。"""
    buf = bytearray(32)
    for y in range(8):
        for x in range(8):
            v = grid8[y][x] & 0x0F
            i = y * 4 + x // 2
            if x % 2 == 0:
                buf[i] = (buf[i] & 0xF0) | v
            else:
                buf[i] = (buf[i] & 0x0F) | (v << 4)
    return bytes(buf)


def show(grid: list[list[int]]) -> list[str]:
    ch = {BG: ".", SHADOW: "+", INK: "#"}
    return ["".join(ch.get(v, "?") for v in row) for row in grid]


def emit_asm(out_path: Path, items: list[tuple[int, bytes, bytes]]) -> None:
    head = [
        "; =============================================================================",
        "; font.origin.s —— 美版数字字形（原样 12 行）写入日版血条字库 up + lo 双槽",
        ";",
        "; 由 scripts/font/gen_font_origin.py 生成，勿手改。",
        ";",
        "; 渲染路径（反汇编 + GDB 实测）：",
        ";   血条 win[0x0B]=4 → GetGlyphTilePointers @0x08003730 的 fn=4 分支",
        ";   lo = 0x081B51AC + FontType1Map[glyph*4+1]*32   (FontType1Map=0x081B34A8)",
        ";   up 原本恒为 0x081B6C2C（全 0，10 个数字共用）—— 本 patch 在 hook 里",
        ";   特判改写成 0x09F00700 + (glyph-0xA1)*32，让每个数字有独立上半格。",
        ";",
        "; 格式：每字 8x16 = up(32B 上半格) + lo(32B 下半格)，",
        ";       nibble 0=背景 14=阴影 15=主墨，lo nibble 为左像素。",
        ";       不缩放、不改笔画，与美版原样一致。",
        ";",
        "; 注意：被 main.asm include，**不要写 .open/.gba/.close**。",
        "; =============================================================================",
        "",
        "; ---- 上半格表 ADDR_FONT_DIGIT_UP = 0x09F00700（hook 里按 glyph 索引）----",
        "",
    ]
    body: list[str] = []
    for gidx, up_data, lo_data in items:
        up_addr = DIGIT_UP_ADDR + (gidx - US_BASE_GLYPH) * 32
        body.append(f"; ---- {GLYPH_NAMES[gidx]!r} (gidx 0x{gidx:02X}) ----")
        body.append(f"; up -> 0x{up_addr:08X}")
        body.append(f".org 0x{up_addr:08X}")
        for i in range(0, 32, 16):
            body.append("    .byte " + ", ".join(f"0x{b:02X}" for b in up_data[i:i + 16]))
        body.append(f"; lo -> 0x{JP_LO[gidx]:08X}")
        body.append(f".org 0x{JP_LO[gidx]:08X}")
        for i in range(0, 32, 16):
            body.append("    .byte " + ", ".join(f"0x{b:02X}" for b in lo_data[i:i + 16]))
        body.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(head + body), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="美版数字字形 → 日版 up+lo 双槽")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "configs/POKEMON_RUBY_AXVJ00/hook/patches/font.origin.s")
    ap.add_argument("--verify", action="store_true", help="打印 16 行全貌")
    args = ap.parse_args()

    if not US_ROM.is_file():
        raise SystemExit(f"error: 美版 ROM 不存在: {US_ROM}")
    us = US_ROM.read_bytes()

    items: list[tuple[int, bytes, bytes]] = []
    for gidx in sorted(JP_LO):
        g16 = read_us_8x16(us, gidx)
        up_part = pack_8x8(g16[0:8])      # row0-7  → 上半格
        lo_part = pack_8x8(g16[8:16])     # row8-15 → 下半格
        items.append((gidx, up_part, lo_part))
        if args.verify:
            print(f"\n=== {GLYPH_NAMES[gidx]!r} (0x{gidx:02X}) 原样 12 行 ===")
            for i, line in enumerate(show(g16)):
                mark = "up" if i < 8 else "lo"
                print(f"    {mark} row{i:2d} {line}")

    emit_asm(args.out, items)
    print(f"\n写入 {args.out}")
    print(f"  {len(items)} 个字形 x (up 32B + lo 32B)")
    print(f"  up 表基址 0x{DIGIT_UP_ADDR:08X}（占用 {len(items)*32} B）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())