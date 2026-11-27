#!/usr/bin/env python3
"""把官方汉化版字库 bin 转成「base BDF」（主墨 + 阴影各一份，双 base）。

═══════════════════════════════════════════════════════════════════════════════
为什么需要双 base BDF（而不是单 BDF + --shadow 程序化阴影）
═══════════════════════════════════════════════════════════════════════════════
官方字库每像素是 **三级 nibble**：0=背景 / 14=阴影 / 15=主墨。
BDF 标准只有 1bpp（0/1），一张 BDF 装不下两级。

实测（2026-11-27，全库 7006 槽逐槽比对）：
    官方阴影 == 「主墨右下 1px 程序化阴影」的槽数 = **0 / 6763**
    Normal 每槽差 20~41 像素，Small 每槽差 18~33 像素

⇒ 官方阴影是**手工设计**的，靠 ink_to_slot16(shadow=True) 程序化补必然不一致。
⇒ 因此拆成两张 BDF：`*.base.bdf` 存主墨、`*.base.shadow.bdf` 存阴影，
   生成 bin 时按 `15 if 主墨 else 14 if 阴影 else 0` 合并，可 **100% 无损还原**。
   （已验证：6763 槽全部可重建，零非法 nibble 值）

═══════════════════════════════════════════════════════════════════════════════
槽内字节布局（★ 踩过坑，必须按 row-major）
═══════════════════════════════════════════════════════════════════════════════
每个字 128B = 4 个 8x8 tile，**按行优先排列**（不是列优先）：

    offset  0..31   TL  (x 0-7,  y 0-7)
    offset 32..63   BL  (x 0-7,  y 8-15)
    offset 64..95   TR  (x 8-15, y 0-7)
    offset 96..127  BR  (x 8-15, y 8-15)

⚠ 曾误按「列优先」读（TL, BL, TR, BR），解出的「巨」是错切碎片。
  正确顺序解出的「巨」结构完整：顶横 / 左右竖 / 中间三横收口，
  且 y 范围 2..13 恰好等于 font.config.json 的 pad_top=2 / ink_h=12。
  这是交叉验证，不是巧合。

nibble 顺序 = **lo-first**：每个字节的低 4 位是左边那个像素。
    实测反证：官方「巨」BL 首字节 f0，lo-first 解得 [背景,墨,墨,墨...] 正常；
    若按 hi-first 解，阴影与主墨之间会隔一格。

═══════════════════════════════════════════════════════════════════════════════
槽位号公式（★ 易错点：不能直接用 charmap 的 code）
═══════════════════════════════════════════════════════════════════════════════
    slot = glyph_index(lead, trail) = lead_adjust(lead) * 256 + trail

    lead_adjust(lead):  adj = lead - 1
                        if lead >= 6:    adj -= 1
                        if lead >= 0x1B: adj -= 1

实测：「巨」charmap code = 0x078E（lead=7, trail=0x8E）
      ⇒ lead_adjust(7) = 7-1-1 = 5
      ⇒ slot = 5*256 + 0x8E = **1422**   ✅ 解出清晰的「巨」
      若直接用 0x78E = 1934 → 解出乱码。

═══════════════════════════════════════════════════════════════════════════════
产出 BDF 格式（与仓内现有 normal.bdf / small.bdf 完全一致）
═══════════════════════════════════════════════════════════════════════════════
    BBX 16 16 0 -2    每行 2 字节（16px，高字节是左 8px）
    Normal: FONT_ASCENT 15 / DESCENT 1
    Small:  FONT_ASCENT 14 / DESCENT 2

用法
====
    python scripts/font/bin_to_base_bdf.py
    python scripts/font/bin_to_base_bdf.py --verify     # 只做往返自检
    python scripts/font/bin_to_base_bdf.py --only Normal
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME = "POKEMON_RUBY_AXVJ00"

CHARMAP = ROOT / "configs" / GAME / "charmap.txt"
FONT_CFG = ROOT / "configs" / GAME / "translate" / "font.config.json"
FONTS_DIR = ROOT / "configs" / GAME / "fonts"
REF_DIR = ROOT / "work" / "_us_cn_ref"

BYTES_PER_GLYPH = 128
SLOT_W = SLOT_H = 16

BG, SHADOW, INK = 0, 14, 15

# 必须与 build_chinese_font.py 完全一致（charmap 过滤 + 槽位上限）
DEFAULT_GLYPH_COUNT = 7168
DEFAULT_LEADS = {
    1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21,
    22, 23, 24, 25, 26, 28, 29, 30,
}

# 官方两库实际槽数（尾部 162 槽是 0xFF 填充，不是字库）
US_CN_SLOTS = 7006

# 每套字库的 bin 文件名与 BDF 头部参数
SLOT_SPECS = {
    "Normal": {
        "bin": "FontChsNormal.bin",
        "base_bdf": "normal.base.bdf",
        "shadow_bdf": "normal.base.shadow.bdf",
        "ascent": 15,
        "descent": 1,
        "dwidth": 12,
        "xlfd": "Normal",
    },
    "Small": {
        "bin": "FontChsSmall.bin",
        "base_bdf": "small.base.bdf",
        "shadow_bdf": "small.base.shadow.bdf",
        "ascent": 14,
        "descent": 2,
        "dwidth": 9,
        "xlfd": "Small",
    },
}


# ─────────────────────────────────────────────────────────────── charmap / 槽位


def lead_adjust(lead: int) -> int:
    """与 scripts/font/build_chinese_font.py 完全一致，不要改。"""
    adj = lead - 1
    if lead >= 6:
        adj -= 1
    if lead >= 0x1B:
        adj -= 1
    return adj


def glyph_index(lead: int, trail: int) -> int:
    return lead_adjust(lead) * 256 + trail


def load_charmap(path: Path) -> dict[int, str]:
    """{slot: char}，key 已经是槽位号（过 lead_adjust）。

    ★ 必须与 build_chinese_font.parse_charmap() 的过滤条件**完全一致**，
      否则两边槽位表不同 → base BDF 的 ENCODING 与流水线取的槽位错开 → 整片错字。
      官方过滤：
        · hex_val <= 0xFF          单字节区跳过
        · lead not in _DEFAULT_LEADS
        · glyph_index >= DEFAULT_GLYPH_COUNT(7168) 跳过
    """
    out: dict[int, str] = {}
    pat = re.compile(r"^([0-9A-Fa-f]+)=(.+)$")
    for line in path.read_text("utf-8", errors="replace").splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        code = int(m.group(1), 16)
        ch = m.group(2)
        if code <= 0xFF or not ch:
            continue
        lead, trail = (code >> 8) & 0xFF, code & 0xFF
        if lead not in DEFAULT_LEADS:
            continue
        slot = glyph_index(lead, trail)
        if slot >= DEFAULT_GLYPH_COUNT:
            continue
        out[slot] = ch
    return out


# ─────────────────────────────────────────────────────────────── bin 解码 / 编码


def decode_slot(bin_data: bytes, slot: int) -> list[list[int]]:
    """128B → 16x16 nibble 网格。row-major 四 tile + lo-first。"""
    g = [[BG] * SLOT_W for _ in range(SLOT_H)]
    base = slot * BYTES_PER_GLYPH
    for tile in range(4):
        off = base + tile * 32
        if off + 32 > len(bin_data):
            return g
        # tile 0=TL(0,0) 1=BL(0,8) 2=TR(8,0) 3=BR(8,8)
        x0 = (tile // 2) * 8
        y0 = (tile % 2) * 8
        for y in range(8):
            for x in range(8):
                b = bin_data[off + y * 4 + x // 2]
                v = (b & 0x0F) if x % 2 == 0 else (b >> 4)
                g[y0 + y][x0 + x] = v
    return g


def encode_slot(grid: list[list[int]]) -> bytes:
    """16x16 nibble 网格 → 128B（decode_slot 的逆运算，用于往返自检）。"""
    out = bytearray(BYTES_PER_GLYPH)
    for tile in range(4):
        off = tile * 32
        x0 = (tile // 2) * 8
        y0 = (tile % 2) * 8
        for y in range(8):
            for x in range(8):
                left = grid[y0 + y][x0 + x] & 0x0F
                right = grid[y0 + y][x0 + x + 1] & 0x0F if x % 2 == 0 else None
                if x % 2 == 0:
                    out[off + y * 4 + x // 2] = left | (
                        (grid[y0 + y][x0 + x + 1] & 0x0F) << 4
                    )
    return bytes(out)


def mask_from_grid(grid: list[list[int]], value: int) -> list[list[int]]:
    return [[1 if grid[y][x] == value else 0 for x in range(SLOT_W)]
            for y in range(SLOT_H)]


def grid_from_masks(
    fg: list[list[int]], sh: list[list[int]]
) -> list[list[int]]:
    """主墨/阴影两张 mask → 官方三级 nibble 网格。"""
    return [
        [INK if fg[y][x] else (SHADOW if sh[y][x] else BG) for x in range(SLOT_W)]
        for y in range(SLOT_H)
    ]


# ─────────────────────────────────────────────────────────────────── BDF 写出


def rows_to_hex(mask: list[list[int]]) -> list[str]:
    """16px 宽的 0/1 mask → BDF 十六进制行（每行 2 字节，高字节是左 8px）。"""
    out: list[str] = []
    for y in range(SLOT_H):
        hi = lo = 0
        for x in range(8):
            if mask[y][x]:
                hi |= 0x80 >> x
        for x in range(8, 16):
            if mask[y][x]:
                lo |= 0x80 >> (x - 8)
        out.append(f"{hi:02X}{lo:02X}")
    return out


def write_bdf(
    path: Path,
    *,
    order: list[tuple[int, str]],
    masks: dict[int, list[list[int]]],
    ascent: int,
    descent: int,
    dwidth: int,
    xlfd_name: str,
    kind: str,
    source: str,
) -> int:
    """写 BDF。order 决定字符顺序（保持 charmap 顺序，便于比对）。"""
    lines = [
        "STARTFONT 2.1",
        f"FONT -Meowth-{xlfd_name}{kind}-Medium-R-Normal--16-160-75-75-"
        f"C-{dwidth * 10}-ISO10646-1",
        "SIZE 16 75 75",
        "FONTBOUNDINGBOX 16 16 0 -2",
        "STARTPROPERTIES 7",
        f"FONT_ASCENT {ascent}",
        f"FONT_DESCENT {descent}",
        "DEFAULT_CHAR 0",
        "PIXEL_SIZE 16",
        f'COMMENT "bin_to_base_bdf.py: {source}; {kind}; row-major; lo-first"',
        "ENDPROPERTIES",
    ]
    entries: list[str] = []
    n = 0
    for slot, ch in order:
        m = masks.get(slot)
        if m is None:
            continue
        enc = ord(ch)
        entries.append(f"STARTCHAR U+{enc:04X}")
        entries.append(f"ENCODING {enc}")
        entries.append(f"SWIDTH {dwidth * 10} 0")
        entries.append(f"DWIDTH {dwidth} 0")
        entries.append("BBX 16 16 0 -2")
        entries.append("BITMAP")
        entries.extend(rows_to_hex(m))
        entries.append("ENDCHAR")
        entries.append("")
        n += 1
    lines.append(f"CHARS {n}")
    lines.append("")
    lines.extend(entries)
    lines.append("ENDFONT")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return n


# ─────────────────────────────────────────────────────────────────────── 主流程


def build_one(label: str, charmap: dict[int, str], *, verify_only: bool) -> dict:
    spec = SLOT_SPECS[label]
    bin_path = REF_DIR / spec["bin"]
    if not bin_path.is_file():
        raise SystemExit(f"[ERR] 官方字库不存在: {bin_path}")
    data = bin_path.read_bytes()

    order = sorted(charmap.items(), key=lambda kv: kv[0])
    fg_masks: dict[int, list[list[int]]] = {}
    sh_masks: dict[int, list[list[int]]] = {}
    n_fg = n_sh = 0
    empty = 0
    illegal = 0

    for slot, _ch in order:
        if slot >= US_CN_SLOTS:
            continue
        g = decode_slot(data, slot)
        for y in range(SLOT_H):
            for x in range(SLOT_W):
                if g[y][x] not in (BG, SHADOW, INK):
                    illegal += 1
        fg = mask_from_grid(g, INK)
        sh = mask_from_grid(g, SHADOW)
        if not any(any(r) for r in fg) and not any(any(r) for r in sh):
            empty += 1
            continue
        fg_masks[slot] = fg
        sh_masks[slot] = sh
        n_fg += sum(sum(r) for r in fg)
        n_sh += sum(sum(r) for r in sh)

    print(f"=== {label} ===")
    print(f"  charmap 槽位 {len(charmap)}，bin 有效槽 {US_CN_SLOTS}")
    print(f"  有字形 {len(fg_masks)}，全空 {empty}，非法 nibble {illegal}")
    print(f"  主墨像素 {n_fg}，阴影像素 {n_sh}")

    # 往返自检：mask → 三级 nibble → 128B，与原 bin 逐字节比
    bad = 0
    for slot in fg_masks:
        rebuilt = encode_slot(grid_from_masks(fg_masks[slot], sh_masks[slot]))
        orig = data[slot * BYTES_PER_GLYPH:(slot + 1) * BYTES_PER_GLYPH]
        if rebuilt != orig:
            bad += 1
            if bad <= 3:
                print(f"  [MISMATCH] slot {slot}")
    print(f"  往返自检: 不一致 {bad} / {len(fg_masks)}")

    if verify_only:
        return {"label": label, "bad": bad, "glyphs": len(fg_masks)}

    base_path = FONTS_DIR / spec["base_bdf"]
    shadow_path = FONTS_DIR / spec["shadow_bdf"]
    nb = write_bdf(
        base_path,
        order=order,
        masks=fg_masks,
        ascent=spec["ascent"],
        descent=spec["descent"],
        dwidth=spec["dwidth"],
        xlfd_name=spec["xlfd"],
        kind="Base",
        source=f"{spec['bin']} 主墨(nibble 15)",
    )
    ns = write_bdf(
        shadow_path,
        order=order,
        masks=sh_masks,
        ascent=spec["ascent"],
        descent=spec["descent"],
        dwidth=spec["dwidth"],
        xlfd_name=spec["xlfd"],
        kind="BaseShadow",
        source=f"{spec['bin']} 阴影(nibble 14)",
    )
    print(f"  -> {base_path.relative_to(ROOT)}  ({nb} 字)")
    print(f"  -> {shadow_path.relative_to(ROOT)}  ({ns} 字)")
    return {"label": label, "bad": bad, "glyphs": len(fg_masks)}


def show_anchor(charmap: dict[int, str]) -> None:
    """打印「巨」的 ASCII 图，人工确认解码正确。"""
    slot = glyph_index(0x07, 0x8E)
    data = (REF_DIR / "FontChsNormal.bin").read_bytes()
    g = decode_slot(data, slot)
    ch = charmap.get(slot, "?")
    print(f"\n锚点校验：slot {slot} = 「{ch}」（charmap code 0x078E 经 lead_adjust）")
    mp = {BG: " ", SHADOW: "+", INK: "#"}
    for y in range(SLOT_H):
        print("  " + "".join(mp.get(v, "?") for v in g[y]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true", help="只做往返自检，不写 BDF")
    ap.add_argument("--only", choices=tuple(SLOT_SPECS), nargs="*", default=None)
    ap.add_argument("--anchor", action="store_true", help="打印「巨」ASCII 图")
    args = ap.parse_args()

    charmap = load_charmap(CHARMAP)
    print(f"charmap: {CHARMAP.name}  槽位 {len(charmap)}")
    print(f"官方字库: {REF_DIR}\n")

    if args.anchor:
        show_anchor(charmap)

    labels = list(args.only) if args.only else list(SLOT_SPECS)
    results = []
    for label in labels:
        results.append(build_one(label, charmap, verify_only=args.verify))

    bad_total = sum(r["bad"] for r in results)
    print()
    if bad_total:
        print(f"[FAIL] 往返自检共 {bad_total} 槽不一致 —— 不要接回流水线")
        return 1
    print("[OK] 往返自检全部一致（双 mask 可无损还原官方字库）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
