#!/usr/bin/env python3
"""Build Chinese GBA font bins for Gen3 (AXVJ).

Hardware container (fixed):
  Two stacked 8x8 tiles = 8x16 per column; glyph slot = 16x16 (TL,BL,TR,BR).
  128 bytes/glyph, 4bpp. This is NOT optional — same as mature RS CN patches.

12px product metrics (ink / advance / line), NOT a different tile size:
  - Ink ~12x12 inside the 16-tall slot (2px pad top + bottom)
  - CHS_GLYPH_ADVANCE_PX = 12, CHS_CHAR_HEIGHT_PX = 12, CHS_LINE_FEED_PX = 14

Nibble order matches Meowth engine / Font_Patch bins: left pixel = high nibble.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SLOT_W = 16
SLOT_H = 16
INK_W = 12
INK_H = 12
PAD_TOP = 2  # (16-12)/2 — top+bottom pad
BYTES_PER_GLYPH = 128
DEFAULT_GLYPH_COUNT = 7168

_DEFAULT_LEADS = {
    1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 28, 29, 30
}


def lead_adjust(lead: int) -> int:
    adj = lead - 1
    if lead >= 6:
        adj -= 1
    if lead >= 0x1B:
        adj -= 1
    return adj


def glyph_index(lead: int, trail: int) -> int:
    return lead_adjust(lead) * 256 + trail


def parse_charmap(path: Path) -> dict[int, str]:
    mapping: dict[int, str] = {}
    pat = re.compile(r"^([0-9A-Fa-f]+)=(.+)$")
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        m = pat.match(line)
        if not m:
            continue
        hex_val = int(m.group(1), 16)
        char = m.group(2)
        if hex_val <= 0xFF or not char:
            continue
        lead = (hex_val >> 8) & 0xFF
        trail = hex_val & 0xFF
        if lead not in _DEFAULT_LEADS:
            continue
        idx = glyph_index(lead, trail)
        if idx >= DEFAULT_GLYPH_COUNT:
            continue
        mapping[idx] = char
    return mapping


def parse_bdf(path: Path) -> tuple[dict[int, tuple], int, int, int]:
    glyphs: dict[int, tuple] = {}
    font_ascent = 13
    font_descent = 3
    pixel_size = 0
    text = path.read_text("utf-8", errors="replace")
    m = re.search(r"^FONT_ASCENT\s+(\d+)", text, re.MULTILINE)
    if m:
        font_ascent = int(m.group(1))
    m = re.search(r"^FONT_DESCENT\s+(\d+)", text, re.MULTILINE)
    if m:
        font_descent = int(m.group(1))
    m = re.search(r"^PIXEL_SIZE\s+(\d+)", text, re.MULTILINE)
    if m:
        pixel_size = int(m.group(1))

    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        if lines[i].startswith("STARTCHAR"):
            encoding = 0
            bbx_w = bbx_h = bbx_x = bbx_y = 0
            bitmap: list[bytearray] = []
            i += 1
            while i < n and not lines[i].startswith("BITMAP"):
                l = lines[i]
                if l.startswith("ENCODING"):
                    encoding = int(l.split()[1])
                elif l.startswith("BBX"):
                    parts = l.split()
                    bbx_w, bbx_h, bbx_x, bbx_y = map(int, parts[1:5])
                i += 1
            if i < n:
                i += 1
            while i < n and not lines[i].startswith("ENDCHAR"):
                hex_str = lines[i].strip()
                if hex_str:
                    row_bytes = bytearray()
                    for j in range(0, len(hex_str), 2):
                        row_bytes.append(int(hex_str[j : j + 2], 16))
                    bitmap.append(row_bytes)
                i += 1
            if encoding > 0 and bitmap:
                glyphs[encoding] = (bitmap, bbx_w, bbx_h, bbx_x, bbx_y)
        i += 1
    return glyphs, font_ascent, font_descent, pixel_size


def bdf_to_ink(
    bitmap_rows: list[bytearray],
    bbx_w: int,
    bbx_h: int,
    bbx_x: int,
    bbx_y: int,
    font_ascent: int,
    ink_w: int = INK_W,
    ink_h: int = INK_H,
    *,
    pad_top: int = 0,
    center_x: bool = False,
) -> bytearray:
    """Rasterize BDF into ``ink_w`` x ``ink_h`` ink (1=ink).

    **基线对齐**（2026-11-11 修）：之前把墨迹 bbox 的左上角贴到 ink(0,0)，
    ``font_ascent`` / ``bbx_y`` 全被忽略 —— 等于所有字「按墨迹顶对齐」。
    单横线字「一」（BDF 里墨迹在第 8 行）因此被抬到第 3 行，看起来没居中；
    「二」「三」两横还会挤到一起。

    正确做法：把 BDF 的行号先换成字身框行号，再减掉 ink 区在槽内的起始行
    （``pad_top``）::

        em_top = font_ascent - (bbx_y + bbx_h)   # bbox 顶在字身框里的行号
        shift  = em_top - pad_top                # ink 第 0 行对应的字身框行

    只有墨迹超出 ink 框（小字 9x9 → 8x8）时才把 shift 钳到 0 再裁右下，
    否则会连顶部笔画一起丢掉。
    """
    src_w = max(bbx_w, 1)
    src_h = len(bitmap_rows) if bitmap_rows else bbx_h
    raw = bytearray(src_w * src_h)
    for y, row in enumerate(bitmap_rows):
        if y >= src_h:
            break
        for x in range(src_w):
            bi, bit = divmod(x, 8)
            if bi < len(row) and (row[bi] & (0x80 >> bit)):
                raw[y * src_w + x] = 1

    min_x, min_y, max_x, max_y = src_w, src_h, -1, -1
    for y in range(src_h):
        for x in range(src_w):
            if raw[y * src_w + x]:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    out = bytearray(ink_w * ink_h)
    if max_x < 0:
        return out
    bw = max_x - min_x + 1
    bh = max_y - min_y + 1

    em_top = font_ascent - (bbx_y + bbx_h) if font_ascent else 0
    shift = em_top - pad_top
    if bw > ink_w or bh > ink_h:
        shift = max(0, shift)

    ox = 0
    if center_x and bw < ink_w:
        ox = (ink_w - bw) // 2

    # 墨迹比目标框大时的收缩策略（2026-11-03 定稿）
    #
    # 背景：Small 槽是 GBA 标准 8x8，步进必须 8px 才能与 tile 网格对齐
    # （非 8 会让字距 8/16 交替，实测）。而 small.bdf 是 9x9。
    #
    # 试过并否决的做法（都实测过）：
    #   · 直接裁右下角  -> 丢第 9 行，得丢底横（「宝」的王字底、「菇」的底）
    #   · 面积平均      -> 末格吞掉整条源行，每字底边糊成实心横杠
    #   · 最近邻按比例  -> 断笔画、丢孤点
    #   · 丢最空的边线  -> 切碎字形（「香」的横画错位）
    #   · 从 TTF 重新栅格化 8x8 -> SimHei/宋体在 8px 下笔画互相粘连，认不出
    #
    # 采用：**行全保留，只把列从 bw 压到 ink_w——合并最相似的两列（OR）**。
    # 9 行完整保留，字形结构不塌；少 1 列只是整体略窄，视觉可接受。
    # 墨迹比目标框大时的收缩（2026-11-03 定稿）
    #
    # Small 槽是 GBA 标准 8x8，步进必须 8px 才能与 tile 网格对齐
    # （非 8 会让字距 8/16 交替，实测）。而 small.bdf 是 9x9。
    #
    # 试过并否决：
    #   · 面积平均      -> 末格吞整条源行，底边糊成实心横杠
    #   · 最近邻按比例  -> 断笔画、丢孤点
    #   · 丢最空的边线  -> 切碎字形
    #   · 合并最相似两列(OR) -> 相邻笔画并在一起，字糊成一团
    #   · 从 TTF 重栅格化 8x8 -> SimHei/宋体在 8px 下笔画互相粘连
    #
    # 采用：**左上角直接裁切**（保留左 ink_w 列、上 ink_h 行）。
    # 丢的是最右 1 列和最下 1 行，字仍能辨认（实测「宝」宀+王、
    # 「菇」草头轮廓都在）；这是 8x8 槽下最保结构的做法。
    if bw > ink_w or bh > ink_h:
        for ny in range(min(ink_h, bh)):
            for nx in range(min(ink_w, bw)):
                if raw[(min_y + ny) * src_w + (min_x + nx)]:
                    out[ny * ink_w + nx] = 1
        return out

    for y in range(min_y, max_y + 1):
        ny = y + shift
        if not (0 <= ny < ink_h):
            continue
        for x in range(min_x, max_x + 1):
            if not raw[y * src_w + x]:
                continue
            nx = x - min_x + ox
            if 0 <= nx < ink_w:
                out[ny * ink_w + nx] = 1
    return out


# 向后兼容旧名（原签名 = 12x12）
bdf_to_ink12 = bdf_to_ink


def ink_to_slot16(
    ink: bytearray,
    *,
    shadow: bool,
    ink_w: int = INK_W,
    ink_h: int = INK_H,
    pad_top: int = PAD_TOP,
) -> bytearray:
    """Place ``ink_w`` x ``ink_h`` ink into the 16x16 slot. Values 0/14/15."""
    slot = bytearray(SLOT_W * SLOT_H)
    for y in range(ink_h):
        for x in range(ink_w):
            if not ink[y * ink_w + x]:
                continue
            sx, sy = x, y + pad_top
            if not (0 <= sx < SLOT_W and 0 <= sy < SLOT_H):
                continue
            slot[sy * SLOT_W + sx] = 15
            if shadow:
                for dx, dy in ((1, 0), (0, 1), (1, 1)):
                    tx, ty = sx + dx, sy + dy
                    if 0 <= tx < SLOT_W and 0 <= ty < SLOT_H:
                        if slot[ty * SLOT_W + tx] == 0:
                            slot[ty * SLOT_W + tx] = 14
    return slot


# 向后兼容旧名
ink12_to_slot16 = ink_to_slot16


def pack_slot16_4bpp(pixels: bytearray, *, lo_first: bool = False) -> bytes:
    """16x16 pixels → 128B TL,BL,TR,BR.

    ``lo_first=False``（默认，= primary 布局）：左像素占**高** 4 位。
    ``lo_first=True``（= ``*_unshadow`` 布局）：左像素占**低** 4 位。

    ⚠️ 两套布局是**镜像**的，混用会让墨迹整体左右偏移半像素，
    在 CHS 双趟绘制里表现为重影。hook 的 `DrawGlyphTile_refpr` /
    `CopyGlyph2bppTo4bpp_Origin` 按 unshadow 布局读，所以
    **嵌入 ROM 的字库必须 lo_first=True**。
    """
    if len(pixels) != SLOT_W * SLOT_H:
        raise ValueError("slot must be 16x16")
    glyph = bytearray(BYTES_PER_GLYPH)
    for tile_col in range(2):
        for tile_row in range(2):
            tile_idx = tile_col * 2 + tile_row  # TL=0, BL=1, TR=2, BR=3
            off = tile_idx * 32
            for ty in range(8):
                py = tile_row * 8 + ty
                for tx in range(4):
                    px = tile_col * 8 + tx * 2
                    left = pixels[py * SLOT_W + px] & 0x0F
                    right = pixels[py * SLOT_W + px + 1] & 0x0F
                    glyph[off + ty * 4 + tx] = (
                        (left | (right << 4)) if lo_first else ((left << 4) | right)
                    )
    if len(glyph) != BYTES_PER_GLYPH:
        raise AssertionError(f"pack produced {len(glyph)}, need {BYTES_PER_GLYPH}")
    return bytes(glyph)


def build_font_bin(
    bdf_glyphs: dict,
    charmap: dict[int, str],
    font_ascent: int,
    glyph_count: int = DEFAULT_GLYPH_COUNT,
    bytes_per_glyph: int = BYTES_PER_GLYPH,
    *,
    shadow: bool = True,
    ink_w: int = INK_W,
    ink_h: int = INK_H,
    pad_top: int | None = None,
    lo_first: bool = False,
) -> bytearray:
    if bytes_per_glyph != BYTES_PER_GLYPH:
        raise ValueError(
            f"bytes_per_glyph must be {BYTES_PER_GLYPH} (16x16 4bpp slot); got {bytes_per_glyph}"
        )
    # 默认把墨迹垂直居中在 16 高槽里
    if pad_top is None:
        pad_top = max(0, (SLOT_H - ink_h) // 2)
    buf = bytearray(bytes_per_glyph * glyph_count)
    for idx, char in charmap.items():
        encoding = ord(char)
        if encoding in bdf_glyphs:
            bitmap_rows, bbx_w, bbx_h, bbx_x, bbx_y = bdf_glyphs[encoding]
            ink = bdf_to_ink(
                bitmap_rows, bbx_w, bbx_h, bbx_x, bbx_y, font_ascent,
                ink_w=ink_w, ink_h=ink_h, pad_top=pad_top,
            )
        else:
            ink = bytearray(ink_w * ink_h)
        slot = ink_to_slot16(
            ink, shadow=shadow, ink_w=ink_w, ink_h=ink_h, pad_top=pad_top,
        )
        packed = pack_slot16_4bpp(slot, lo_first=lo_first)
        off = idx * bytes_per_glyph
        buf[off : off + bytes_per_glyph] = packed
    return buf


SYM_BYTES_PER_GLYPH = 64  # 8x8 上 + 8x8 下，4bpp


def pack_8x16_4bpp(px: bytearray) -> bytes:
    """8x16 像素（0..15）→ 64B：上半 8x8 4bpp + 下半 8x8 4bpp，左像素占低半字节。"""
    out = bytearray(64)
    for ty in range(16):
        for tx4 in range(4):
            left = px[ty * 8 + tx4 * 2]
            right = px[ty * 8 + tx4 * 2 + 1]
            out[ty * 4 + tx4] = (left & 0x0F) | ((right & 0x0F) << 4)
    return bytes(out)


def build_sym_bank(
    bdf_glyphs: dict,
    font_ascent: int,
    chars: list[str],
    *,
    ink_w: int = 8,
    ink_h: int = 12,
    pad_top: int = 2,
) -> bytearray:
    """句读标点小库：8x16 4bpp，64B/字。

    hook 侧 ``text_translter.c:37-49`` 对 ``0x36..0x3E`` 按 **64B/字** 取址、
    只画 8px 宽。之前这个槽复用「整张 charmap 从第 0 字起」的 16x16 缓冲、
    再硬截 576B，里面其实是「啊/阿/埃/挨」的前半 —— 所有句读标点于是都变成
    汉字残片（`！` 画成「挨」左半，看着像 `]`）。
    """
    buf = bytearray(SYM_BYTES_PER_GLYPH * len(chars))
    top = max(0, (16 - ink_h) // 2)
    for i, ch in enumerate(chars):
        enc = ord(ch)
        if enc not in bdf_glyphs:
            print(f"  [sym] 缺字 {ch!r}，留空槽")
            continue
        bitmap_rows, bbx_w, bbx_h, bbx_x, bbx_y = bdf_glyphs[enc]
        ink = bdf_to_ink(
            bitmap_rows, bbx_w, bbx_h, bbx_x, bbx_y, font_ascent,
            ink_w=ink_w, ink_h=ink_h, pad_top=pad_top, center_x=True,
        )
        px = bytearray(ink_w * 16)
        for y in range(ink_h):
            for x in range(ink_w):
                if ink[y * ink_w + x]:
                    px[(y + top) * ink_w + x] = 15
        buf[i * SYM_BYTES_PER_GLYPH:(i + 1) * SYM_BYTES_PER_GLYPH] = pack_8x16_4bpp(px)
    return buf


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build Gen3 Chinese font bins (128B / 16x16 slot, 12px ink)"
    )
    ap.add_argument("--slot-chars", nargs="*", default=None, metavar="LABEL=c1,c2,...",
                    help="该 slot 按显式字符列表生成 8x16 小库（64B/字），"
                         "用于 Sym 句读标点槽")
    ap.add_argument("--bdf", required=True, type=Path,
                    help="默认 BDF（各 slot 未单独指定时用它）")
    ap.add_argument("--bdf-map", nargs="*", default=None, metavar="LABEL=PATH",
                    help="逐 slot 指定 BDF，如 Normal=fonts/normal.bdf Sym=fonts/sym.bdf")
    ap.add_argument("--ink-map", nargs="*", default=None, metavar="LABEL=WxH",
                    help="逐 slot 指定墨迹尺寸，如 Normal=11x11 Small=9x9")
    ap.add_argument("--pad-map", nargs="*", default=None, metavar="LABEL=N",
                    help="逐 slot 指定墨迹在 16 高槽里的起始行，如 Small=6 "
                         "（必须与旧字库对齐，否则多行互相压盖）")
    ap.add_argument("--charmap", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--glyph-count", type=int, default=DEFAULT_GLYPH_COUNT)
    ap.add_argument("--bytes-per-glyph", type=int, default=BYTES_PER_GLYPH)
    ap.add_argument("--slot-labels", nargs="+", default=["Normal", "Small"])
    ap.add_argument("--slot-sizes", nargs="+", type=int, default=None)
    ap.add_argument("--prefix", type=str, default="PokeRSFontChs")
    ap.add_argument("--dilate", action="store_true")
    ap.add_argument("--shadow", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument(
        "--nibble-order",
        choices=("lo-first", "hi-first"),
        default="lo-first",
        help=(
            "像素半字节布局。hook 的 CHS 绘制按 unshadow 布局读 → lo-first（默认）；"
            "hi-first 仅用于生成与旧 primary 兼容的 bin（离线比对用）。"
        ),
    )
    ap.add_argument("--phrase-map", type=Path, default=None)
    args = ap.parse_args()

    if args.bytes_per_glyph != BYTES_PER_GLYPH:
        print(
            f"error: bytes_per_glyph must be {BYTES_PER_GLYPH}, got {args.bytes_per_glyph}",
            file=sys.stderr,
        )
        sys.exit(1)

    def _kv_map(items) -> dict[str, str]:
        out: dict[str, str] = {}
        for it in items or []:
            if "=" not in it:
                raise SystemExit(f"error: 需要 LABEL=VALUE 形式，收到 {it!r}")
            k, _, v = it.partition("=")
            out[k.strip()] = v.strip()
        return out

    bdf_map = _kv_map(args.bdf_map)
    ink_map = _kv_map(args.ink_map)
    pad_map = _kv_map(args.pad_map)
    slot_chars: dict[str, list[str]] = {}
    for item in args.slot_chars or []:
        if "=" not in item:
            raise SystemExit(f"error: --slot-chars 需要 LABEL=c1,c2 形式，收到 {item!r}")
        lbl, raw = item.split("=", 1)
        slot_chars[lbl.strip()] = [c for c in raw.split(",") if c]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Parsing BDF (default): {args.bdf}")
    default_glyphs, default_ascent, font_descent, pixel_size = parse_bdf(args.bdf)
    print(
        f"  Loaded {len(default_glyphs)} glyphs "
        f"(ascent={default_ascent}, descent={font_descent}, pixel_size={pixel_size})"
    )

    print(f"Parsing charmap: {args.charmap}")
    charmap = parse_charmap(args.charmap)
    print(f"  Found {len(charmap)} Chinese character mappings")

    # 逐 slot 解析 BDF 与 ink 尺寸，同一 BDF 只解析一次
    bdf_cache: dict[Path, tuple[dict, int]] = {args.bdf.resolve(): (default_glyphs, default_ascent)}
    plan: list[tuple[str, Path, dict, int, int, int]] = []
    for label in args.slot_labels:
        bp = Path(bdf_map[label]) if label in bdf_map else args.bdf
        key = bp.resolve()
        if key not in bdf_cache:
            if not bp.is_file():
                raise SystemExit(f"error: slot {label} 的 BDF 不存在: {bp}")
            print(f"Parsing BDF for {label}: {bp}")
            g, asc, _d, _ps = parse_bdf(bp)
            bdf_cache[key] = (g, asc)
            print(f"  Loaded {len(g)} glyphs (ascent={asc})")
        glyphs, ascent = bdf_cache[key]

        iw, ih = INK_W, INK_H
        if label in ink_map:
            try:
                iw, ih = (int(x) for x in ink_map[label].lower().split("x"))
            except ValueError:
                raise SystemExit(f"error: ink 尺寸需 WxH 形式，收到 {ink_map[label]!r}")
        # pad_top：显式指定优先；否则垂直居中。
        # ⚠️ 必须与旧字库逐字对齐，否则同屏多行上下互相压盖。
        if label in pad_map:
            try:
                pad = int(pad_map[label])
            except ValueError:
                raise SystemExit(f"error: pad_top 需整数，收到 {pad_map[label]!r}")
        else:
            pad = max(0, (SLOT_H - ih) // 2)
        plan.append((label, bp, glyphs, ascent, iw, ih, pad))
        print(f"  [{label}] bdf={bp.name} ink={iw}x{ih} pad_top={pad}")

    for i, (label, bp, glyphs, ascent, iw, ih, pad) in enumerate(plan):
        print(f"Building {label} font...")
        if label in slot_chars:
            buf = build_sym_bank(glyphs, ascent, slot_chars[label])
            size = (
                args.slot_sizes[i]
                if args.slot_sizes and i < len(args.slot_sizes)
                else len(buf)
            )
            fn = f"{args.prefix}{label}(0x{size:X}).bin"
            out_path = args.output_dir / fn
            out_path.write_bytes(buf)
            print(
                f"  Written {len(buf)} bytes -> {out_path}  "
                f"(8x16 sym bank, chars={' '.join(slot_chars[label])})"
            )
            continue
        buf = build_font_bin(
            glyphs,
            charmap,
            ascent,
            glyph_count=args.glyph_count,
            bytes_per_glyph=args.bytes_per_glyph,
            shadow=args.shadow,
            ink_w=iw,
            ink_h=ih,
            pad_top=pad,
            lo_first=(args.nibble_order == "lo-first"),
        )
        if args.slot_sizes and i < len(args.slot_sizes):
            buf = buf[: args.slot_sizes[i]]
        slot_size = (
            args.slot_sizes[i]
            if args.slot_sizes and i < len(args.slot_sizes)
            else len(buf)
        )
        fn = f"{args.prefix}{label}(0x{slot_size:X}).bin"
        out_path = args.output_dir / fn
        out_path.write_bytes(buf)
        print(f"  Written {len(buf)} bytes -> {out_path}  (ink {iw}x{ih}, from {bp.name})")
        assert len(buf[0:BYTES_PER_GLYPH]) == 128

    print("Done.")


if __name__ == "__main__":
    main()
