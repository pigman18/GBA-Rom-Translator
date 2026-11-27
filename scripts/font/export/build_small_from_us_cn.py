#!/usr/bin/env python3
"""把「美版汉化版」的 small 字形，按**本项目 charmap 槽位**重排成可直接接入的 BDF。

═══════════════════════════════════════════════════════════════════
为什么需要这一步（踩过的坑）
═══════════════════════════════════════════════════════════════════
本项目构建管线取字模的索引**不是 Unicode，也不是汉化版的 idx**，而是

    slot_idx = glyph_index(lead, trail) = lead_adjust(lead)*256 + trail

其中 (lead, trail) 来自 `configs/<game>/charmap.txt`。实测同一批字的两种编号：

    字   本项目 slot_idx    汉化版 idx
    巨        1422             ?
    火        1149           1405
    宝          99            355

两者毫无对应关系。所以直接把「按汉化版 idx 顺序」导出的 BDF 扔进
`fonts/small.bdf` 槽位，会**整片错字**（实测：队伍界面「巨沼怪」渲染成
「发件阖」）。

正确做法（本脚本）：
    1. 读本项目 charmap → {slot_idx: 汉字}
    2. 读汉化版 TBL 码表 → {汉字: 汉化版 idx}
    3. 对每个 slot_idx，取对应汉字在汉化版的字形，写进 BDF（ENCODING=slot_idx）

═══════════════════════════════════════════════════════════════════
字库布局（实测）
═══════════════════════════════════════════════════════════════════
汉化版：基址 0x090AF220，每字 128B，有效字形只在前 64B（tile0+tile1 = 8x16）。
两段：idx 0..1404 大字（11 行高）/ idx 1405.. 小字（9 行高），**字符无重叠**。
nibble：0=背景 14=阴影 15=主墨，lo nibble 是左像素。

用法
====
    python scripts/font/export/build_small_from_us_cn.py
    python scripts/font/export/build_small_from_us_cn.py --out <path>
    python scripts/font/export/build_small_from_us_cn.py --stats
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/font"))
sys.path.insert(0, str(ROOT / "scripts/font/export"))

from build_chinese_font import parse_charmap        # noqa: E402
from map_us_cn_to_unicode import load_tbl           # noqa: E402

US_CN_ROM = ROOT / "work/_us_cn.gba"
CHARMAP = ROOT / "configs/POKEMON_RUBY_AXVJ00/charmap.txt"
OUT_BDF = ROOT / "configs/POKEMON_RUBY_AXVJ00/fonts/small_us_cn_slot.bdf"

# ★ 正确基址（2026-11-25 用官方 bin 定死）：
#   下载 Wokann 补丁的 graphic/fonts/PokeRSFontChsSmall(0xE0000).bin
#   （917504B = 7168 字 x 128B），在汉化版 ROM 里 find 其前 64B，
#   命中 0x090DB0A0 —— 这才是 small 字库真正起点。
#
# 此前的 0x090AF220 是「用 index 反推」猜出来的，偏了 0xBE80
# = 正好 200 个字，导致所有字形整体错位（"巨" 在槽 1422 解出来
# 是糊块，"火焰鸡" 能对上纯属巧合）。**别再改回去。**
FONT_BASE = 0x090DB0A0
BYTES_PER_GLYPH = 128
SLOT_W, SLOT_H = 8, 16

BG, SHADOW, INK = 0, 14, 15


def us_cn_glyph(rom: bytes, slot: int) -> list[list[int]] | None:
    """汉化版槽位 slot 的字形 → 8x16 nibble 网格；全空返回 None。

    ★ nibble 顺序 = **lo-first**：左像素在**低** 4 位（b&0xF 是 x 起点）。

    依据（三方一致，2026-11-25 定死）：
      1. 汉化版官方绘制源码 `DrawGlyphTilesChinese.s`：
             lsl r1, r1, 7      ; slot * 128  ← 每字 128B
             mov r0, 8          ; 宽度 8px
             add r0, 0x20       ; 下半格 +32B
      2. hook 的 `grid_glyph_px`：`(x & 1) ? (b >> 4) : (b & 0xF)`
         —— 偶数 x 取低半字节 = **lo-first**。
      3. 管线 `pack_slot16_4bpp(lo_first=True)`：`left | (right << 4)`。

    实测反证：官方 bin 的「巨」BL 首字节是 `f0`，
    按 lo-first 解得 `[背景, 墨, 墨, 墨, ...]`（墨从第 2 列起、阴影紧贴其右），
    是正确的「巨」；若按 hi-first 解得 `[墨, 背景, ...]`，
    阴影与墨之间会隔一格 —— 错。

    ⚠ 我曾误改成 hi-first，导致写出的字节变成 `0f`（两半字节对调），
    ROM 里字形整体左移 1px，屏幕上「巨沼怪」看着就成了「巨作馆」。
    **不要改回 hi-first。**
    """
    a = FONT_BASE - 0x08000000 + slot * BYTES_PER_GLYPH
    if a < 0 or a + 64 > len(rom):
        return None
    grid: list[list[int]] = []
    for tile in range(2):
        off = a + tile * 32
        for y in range(8):
            grid.append([
                ((rom[off + y * 4 + x // 2] & 0x0F) if x % 2 == 0
                 else (rom[off + y * 4 + x // 2] >> 4))
                for x in range(SLOT_W)
            ])
    if all(v == BG for row in grid for v in row):
        return None
    return grid


def to_bdf_rows(grid: list[list[int]], with_shadow: bool = False) -> list[str]:
    """8x16 nibble → BDF 16 行十六进制（每行 8px，MSB 最左）。

    with_shadow=False（默认）只把主墨 nibble=15 记为 1。
    ★ 必须 false：本项目渲染层 grid_draw_chs 会程序化补右下阴影，
      字库再带一层会双重阴影糊成一团（2026-11-24 已实测过）。
    """
    out = []
    for y in range(SLOT_H):
        bits = 0
        for x in range(SLOT_W):
            v = grid[y][x]
            hit = (v == INK) if not with_shadow else (v != BG)
            if hit:
                bits |= 0x80 >> x
        out.append(f"{bits:02X}")
    return out


def emit(out_path: Path, glyphs: dict[int, list[list[int]]], ascent: int, descent: int) -> None:
    """写 BDF。

    ★ BBX / ascent 必须和仓内原 small.bdf **完全一致**（BBX 16 16 0 -2，
      ascent 14 / descent 2）。管线 bdf_to_ink 用
          em_top = font_ascent - (bbx_y + bbx_h)
          shift  = em_top - pad_top
      来定位墨迹在字身框里的行号。若照抄汉化版的「8 宽 / y=0 / ascent 15」，
      em_top 会算错、字形整体被推出可视区（实测：队伍界面名字整个消失，
      只剩 Lv 和血量）。
    ★ FONTBOUNDINGBOX 也必须写 16 16 0 -2，与 BBX 一致。
    """
    lines = [
        "STARTFONT 2.1",
        # XLFD 严格 15 字段，字段名内不能含 '-'（否则 BdfEditor 打不开）
        "FONT -Meowth-USCNSlot-Medium-R-Normal--16-160-75-75-C-80-ISO10646-1",
        "SIZE 16 75 75",
        "FONTBOUNDINGBOX 16 16 0 -2",
        "STARTPROPERTIES 3",
        f"FONT_ASCENT {ascent}",
        f"FONT_DESCENT {descent}",
        "DEFAULT_CHAR 0",
        "ENDPROPERTIES",
        f"CHARS {len(glyphs)}",
        "",
    ]
    for ch in sorted(glyphs, key=ord):
        lines.append(f"STARTCHAR u{ord(ch):04X}")
        lines.append(f"ENCODING {ord(ch)}")
        lines.append("SWIDTH 500 0")
        lines.append("DWIDTH 9 0")
        lines.append("BBX 16 16 0 -2")
        lines.append("BITMAP")
        # 每行 16px → 2 字节（高字节是左 8px）
        for row in to_bdf_rows(glyphs[ch]):
            lines.append(f"{row}00")
        lines.append("ENDCHAR")
        lines.append("")
    lines.append("ENDFONT")
    lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="按本项目槽位重排汉化版 small 字形")
    ap.add_argument("--rom", type=Path, default=US_CN_ROM)
    ap.add_argument("--charmap", type=Path, default=CHARMAP)
    ap.add_argument("--out", type=Path, default=OUT_BDF)
    ap.add_argument("--with-shadow", action="store_true",
                    help="把阴影也算进字形（默认不算，见 to_bdf_rows 注释）")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    rom = args.rom.read_bytes()
    slot2char = parse_charmap(args.charmap)

    print(f"本项目 charmap 槽位 {len(slot2char)} 个")

    # ★★★ 核心简化（2026-11-25 定案）★★★
    # 官方字库 bin（PokeRSFontChsSmall(0xE0000).bin）本身就是**按本项目
    # 同一套槽位号**排的：charmap 里 `078E=巨` 经 glyph_index 得槽 1422，
    # 而 bin 的第 1422 个 128B 块解出来正是「巨」字（已手工验证
    # 巨/火/宝 三字全对）。所以**直接用槽位号取字，不需要任何码表转换**。
    #
    # 之前绕道 TBL 码表把所有字错位，是因为把 TBL 的 key（字符编码）
    # 误当成「汉化版自己的 idx」，再拿它当槽位地址 —— 纯属多余且有害。
    glyphs: dict[str, list[list[int]]] = {}
    no_glyph = 0
    miss_samples: list[str] = []

    for slot, ch in sorted(slot2char.items()):
        g = us_cn_glyph(rom, slot)
        if g is None:
            no_glyph += 1
            if len(miss_samples) < 12:
                miss_samples.append(f"{ch}(槽{slot}空)")
            continue
        glyphs[ch] = g

    print(f"  成功导出 {len(glyphs)} 个槽位")
    print(f"  字库缺字形 {no_glyph}")
    if miss_samples:
        print("  缺失示例:", "; ".join(miss_samples))

    if args.stats:
        for ch in list(sorted(glyphs, key=ord))[:5]:
            print(f"\n{ch}:")
            for i, line in enumerate(to_bdf_rows(glyphs[ch])):
                bits = int(line, 16)
                print(f"   {i:2d} " + "".join("#" if bits & (0x80 >> x) else "." for x in range(8)))
        return 0

    # 小字段字形落在 row6..14 ⇒ ascent 15 / descent 1
    emit(args.out, glyphs, ascent=14, descent=2)
    print(f"写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())