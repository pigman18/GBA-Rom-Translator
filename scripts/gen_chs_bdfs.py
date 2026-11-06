#!/usr/bin/env python3
"""Generate AXVJ normal/middle/small BDF from texts_translated.json.

Raster path (2026-11-06 修正 — 禁止再走「大号抗锯齿 + LANCZOS + 阈值」):
  FreeType ``FT_LOAD_TARGET_MONO`` 在 **ink 高度附近** 直接出 1bpp，
  裁 bbox → 过大才 NEAREST 压进 ink WxH → 放入 16×16（pad_top）。

底字优先级（无衬线、小字 hint 更好；宋体/衬线会在 12px 断笔糊成渣）:
  Noto Sans SC → 微软雅黑 → 黑体 → 等线 → （最后）宋体兜底缺字

尺寸仍只取 FireRed metrics（font.config.json），不导出 FR 字形。

Usage:
  python scripts/gen_chs_bdfs.py
  python scripts/gen_chs_bdfs.py --fonts "C:/Windows/Fonts/Noto Sans SC (TrueType).otf"
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import freetype
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
GAME = "POKEMON_RUBY_AXVJ00"
DEFAULT_TRANSLATED = ROOT / "configs" / GAME / "translate" / "texts_translated.json"
DEFAULT_FONT_CFG = ROOT / "configs" / GAME / "translate" / "font.config.json"
DEFAULT_CHARMAP = ROOT / "configs" / GAME / "charmap.txt"
DEFAULT_OUT_DIR = ROOT / "configs" / GAME / "fonts"

# 无衬线优先；宋体仅兜底（缺字时）
DEFAULT_FONTS = [
    Path(r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf"),
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path(r"C:\Windows\Fonts\Deng.ttf"),
    Path(r"C:\Windows\Fonts\simsun.ttc"),
]

SLOT = 16

DEFAULT_SLOTS = {
    "normal": {"ink_w": 12, "ink_h": 13, "pad_top": 2, "dwidth": 12, "file": "normal.bdf"},
    "middle": {"ink_w": 9, "ink_h": 11, "pad_top": 2, "dwidth": 9, "file": "middle.bdf"},
    "small": {"ink_w": 9, "ink_h": 9, "pad_top": 6, "dwidth": 8, "file": "small.bdf"},
}


def parse_ink(s: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d+)x(\d+)", s.strip(), re.I)
    if not m:
        raise argparse.ArgumentTypeError(f"ink must be WxH, got {s!r}")
    return int(m.group(1)), int(m.group(2))


def load_slots_from_font_config(path: Path) -> dict[str, dict]:
    slots = {k: dict(v) for k, v in DEFAULT_SLOTS.items()}
    if not path.is_file():
        return slots
    cfg = json.loads(path.read_text(encoding="utf-8"))
    for fs in cfg.get("font_slots") or []:
        label = (fs.get("label") or "").lower()
        if label not in slots:
            continue
        ink = fs.get("ink")
        if isinstance(ink, str) and "x" in ink:
            w, h = parse_ink(ink)
            slots[label]["ink_w"] = w
            slots[label]["ink_h"] = h
        if "pad_top" in fs:
            slots[label]["pad_top"] = int(fs["pad_top"])
        if fs.get("bdf"):
            slots[label]["file"] = Path(fs["bdf"]).name
    return slots


def collect_charset(translated: Path, charmap: Path | None) -> list[str]:
    seen: dict[str, None] = {}

    def add(ch: str) -> None:
        if len(ch) != 1:
            return
        o = ord(ch)
        if o < 0x20 or ch in ("\n", "\r", "\t"):
            return
        seen.setdefault(ch, None)

    for o in range(0x20, 0x7F):
        add(chr(o))

    data = json.loads(translated.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"expected list in {translated}")
    for e in data:
        if not isinstance(e, dict):
            continue
        for key in ("translated", "original"):
            t = e.get(key) or ""
            if isinstance(t, str):
                for ch in t:
                    add(ch)

    if charmap and charmap.is_file():
        pat = re.compile(r"^([0-9A-Fa-f]+)=(.+)$")
        for line in charmap.read_text(encoding="utf-8").splitlines():
            m = pat.match(line.strip())
            if not m:
                continue
            ch = m.group(2).strip()
            if len(ch) == 1:
                add(ch)

    return list(seen.keys())


def collect_font_files(paths: list[Path]) -> list[Path]:
    exts = {".ttf", ".ttc", ".otf", ".otc"}
    out: list[Path] = []
    seen: set[Path] = set()
    for p in paths:
        p = p.resolve()
        if p.is_dir():
            for f in sorted(p.iterdir()):
                if f.suffix.lower() in exts and f not in seen:
                    out.append(f)
                    seen.add(f)
        elif p.is_file() and p.suffix.lower() in exts and p not in seen:
            out.append(p)
            seen.add(p)
    return out


def open_faces(files: list[Path]) -> list[tuple[str, freetype.Face]]:
    """Open outline faces (TTC: try several indices)."""
    faces: list[tuple[str, freetype.Face]] = []
    for f in files:
        for index in range(0, 8):
            try:
                face = freetype.Face(str(f), index=index)
            except Exception:
                break
            # Skip faces that clearly have no charmaps
            try:
                face.set_pixel_sizes(0, 16)
            except Exception:
                continue
            faces.append((f"{f.name}#{index}", face))
            # OTF usually single face
            if f.suffix.lower() in {".otf", ".ttf"} and index == 0:
                # still try index 1 for some TTF collections misnamed
                pass
    return faces


def ft_mono_glyph(face: freetype.Face, ch: str, px: int) -> Image.Image | None:
    """Render one char with FreeType mono target → L image (0=ink, 255=bg)."""
    try:
        face.set_pixel_sizes(0, px)
        flags = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO
        face.load_char(ch, flags)
    except Exception:
        return None
    bitmap = face.glyph.bitmap
    if bitmap.width <= 0 or bitmap.rows <= 0:
        return None
    img = Image.new("L", (bitmap.width, bitmap.rows), 255)
    px_ = img.load()
    buf = bytes(bitmap.buffer)
    for y in range(bitmap.rows):
        row = buf[y * bitmap.pitch : (y + 1) * bitmap.pitch]
        for x in range(bitmap.width):
            if row[x >> 3] & (0x80 >> (x & 7)):
                px_[x, y] = 0
    return img


def place_ink(
    bw: Image.Image,
    *,
    ink_w: int,
    ink_h: int,
    pad_top: int,
) -> Image.Image | None:
    """Crop ink, NEAREST-downscale only if larger than ink, place in 16×16."""
    # 0=ink / 255=bg：PIL getbbox 看「非 0」，全墨字（「一」）会是整幅 0 → None。
    # 必须先反成墨=255 再取 bbox。
    mask = bw.point(lambda v: 255 if v < 128 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return None
    crop = bw.crop(bbox)
    tw, th = crop.size
    if tw > ink_w or th > ink_h:
        scale = min(ink_w / tw, ink_h / th)
        nw = max(1, int(round(tw * scale)))
        nh = max(1, int(round(th * scale)))
        # NEAREST keeps 1bpp edges; never LANCZOS here
        crop = crop.resize((nw, nh), Image.Resampling.NEAREST)
        # re-threshold after nearest (should stay 0/255)
        crop = crop.point(lambda v: 0 if v < 128 else 255)
        tw, th = crop.size
    if tw < 1 or th < 1:
        return None
    cell = Image.new("L", (SLOT, SLOT), 255)
    ox = max(0, (ink_w - tw) // 2)
    oy = pad_top + max(0, (ink_h - th) // 2)
    if oy + th > SLOT:
        oy = max(0, SLOT - th)
    if ox + tw > SLOT:
        ox = max(0, SLOT - tw)
    cell.paste(crop, (ox, oy))
    return cell


def score_cell(
    cell: Image.Image, ink_w: int, ink_h: int, pad_top: int, *, px_size: int
) -> float:
    """Higher = better. Prefer ink_h-sized mono; penalize solid full-width bars."""
    px = cell.load()
    ink = 0
    in_box = 0
    full_rows = 0
    for y in range(SLOT):
        row_ink = 0
        for x in range(SLOT):
            if px[x, y] >= 128:
                continue
            ink += 1
            if 0 <= x < ink_w and pad_top <= y < pad_top + ink_h:
                in_box += 1
                row_ink += 1
        if row_ink >= max(ink_w - 1, 8):
            full_rows += 1
    if ink < 4:
        return -1.0
    area = ink_w * ink_h
    fill = in_box / max(area, 1)
    if fill > 0.72:
        return in_box * 0.2
    sc = float(in_box) + (1.0 - abs(fill - 0.35)) * 10.0
    # 多数汉字不会有 ≥3 条几乎满宽横；FT 过大字号常造出底边伪横
    if full_rows >= 3:
        sc -= 25.0
    elif full_rows >= 2:
        sc -= 8.0
    # Prefer exact ink height
    sc -= abs(px_size - ink_h) * 3.0
    return sc


def rasterize_glyph(
    ch: str,
    faces: list[tuple[str, freetype.Face]],
    *,
    ink_w: int,
    ink_h: int,
    pad_top: int,
    min_ink: int,
) -> tuple[list[str], str] | None:
    """FT_MONO near ink_h — first priority face with OK score wins."""
    # 绝不试 ink_h+1：Noto 在 +1 时常挤出底边满宽伪横（「宝」@mono14）
    sizes = sorted({ink_h, max(8, ink_h - 1)})
    best: tuple[float, Image.Image, str] | None = None
    for tag, face in faces:
        local: tuple[float, Image.Image, str] | None = None
        for px_size in sizes:
            raw = ft_mono_glyph(face, ch, px_size)
            if raw is None:
                continue
            cell = place_ink(raw, ink_w=ink_w, ink_h=ink_h, pad_top=pad_top)
            if cell is None:
                continue
            ink_n = sum(
                1
                for y in range(SLOT)
                for x in range(SLOT)
                if cell.getpixel((x, y)) < 128
            )
            if ink_n < min_ink:
                continue
            sc = score_cell(cell, ink_w, ink_h, pad_top, px_size=px_size)
            label = f"{tag}@mono{px_size}"
            if local is None or sc > local[0]:
                local = (sc, cell, label)
        # Face order = priority (Noto → … → 宋体). First OK face wins.
        if local is not None:
            best = local
            if local[0] >= 18.0:
                break

    if best is None:
        return None
    _, cell, label = best
    px = cell.load()
    rows: list[str] = []
    for y in range(SLOT):
        buf = bytearray(2)
        for x in range(SLOT):
            if px[x, y] < 128:
                buf[x // 8] |= 0x80 >> (x % 8)
        rows.append(buf.hex().upper())
    return rows, label


def backup_bdf(path: Path) -> Path | None:
    if not path.is_file():
        return None
    bak_dir = path.parent / "bak"
    bak_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d%H%M")
    dest = bak_dir / f"{path.stem}.{ts}{path.suffix}"
    if dest.exists():
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        dest = bak_dir / f"{path.stem}.{ts}{path.suffix}"
    shutil.copy2(path, dest)
    return dest


def write_bdf(
    out: Path,
    chars: list[str],
    glyphs: dict[int, tuple[list[str], str]],
    *,
    name: str,
    ink_w: int,
    ink_h: int,
    dwidth: int,
    pad_top: int,
) -> None:
    lines = [
        "STARTFONT 2.1",
        f"FONT -Meowth-{name}-Medium-R-Normal--16-160-75-75-C-{dwidth * 10}-ISO10646-1",
        "SIZE 16 75 75",
        "FONTBOUNDINGBOX 16 16 0 -2",
        "STARTPROPERTIES 7",
        f"FONT_ASCENT {pad_top + ink_h}",
        f"FONT_DESCENT {max(0, SLOT - pad_top - ink_h)}",
        "DEFAULT_CHAR 0",
        "PIXEL_SIZE 16",
        f'COMMENT "gen_chs_bdfs.py: FT_LOAD_TARGET_MONO → {ink_w}x{ink_h} ink, '
        f'pad_top={pad_top}; base=NotoSansSC>YaHei>SimHei; no FR export"',
        "ENDPROPERTIES",
        f"CHARS {len(glyphs)}",
        "",
    ]
    for ch in chars:
        enc = ord(ch)
        if enc not in glyphs:
            continue
        hex_rows, tag = glyphs[enc]
        lines.append(f"STARTCHAR U+{enc:04X}")
        lines.append(f"ENCODING {enc}")
        lines.append(f"SWIDTH {dwidth * 10} 0")
        lines.append(f"DWIDTH {dwidth} 0")
        lines.append("BBX 16 16 0 -2")
        lines.append(f'COMMENT "from {tag}"')
        lines.append("BITMAP")
        lines.extend(hex_rows)
        lines.append("ENDCHAR")
        lines.append("")
    lines.append("ENDFONT")
    lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def gen_one(
    name: str,
    spec: dict,
    chars: list[str],
    font_files: list[Path],
    out_dir: Path,
) -> tuple[Path, int, int]:
    ink_w = int(spec["ink_w"])
    ink_h = int(spec["ink_h"])
    pad_top = int(spec["pad_top"])
    dwidth = int(spec["dwidth"])
    out = out_dir / spec["file"]
    bak = backup_bdf(out)
    if bak:
        print(f"  bak → {bak.relative_to(ROOT)}")

    faces = open_faces(font_files)
    if not faces:
        raise SystemExit(f"no FreeType faces loaded for {name}")
    print(f"  faces: {', '.join(t for t, _ in faces[:8])}{'…' if len(faces) > 8 else ''}")

    min_ink_default = 4 if max(ink_w, ink_h) <= 9 else 8
    filled: dict[int, tuple[list[str], str]] = {}
    failed: list[str] = []
    for i, ch in enumerate(chars):
        # 标点/符号墨迹少，阈值放宽
        o = ord(ch)
        min_ink = 2 if o < 0x80 or not (0x4E00 <= o <= 0x9FFF) else min_ink_default
        got = rasterize_glyph(
            ch,
            faces,
            ink_w=ink_w,
            ink_h=ink_h,
            pad_top=pad_top,
            min_ink=min_ink,
        )
        if got is None:
            failed.append(ch)
            continue
        filled[ord(ch)] = got
        if (i + 1) % 500 == 0:
            print(f"  … {name} {i + 1}/{len(chars)}")

    write_bdf(
        out,
        chars,
        filled,
        name=name.capitalize(),
        ink_w=ink_w,
        ink_h=ink_h,
        dwidth=dwidth,
        pad_top=pad_top,
    )
    print(
        f"  wrote {out.relative_to(ROOT)}  glyphs={len(filled)}  "
        f"failed={len(failed)}  ink={ink_w}x{ink_h} pad_top={pad_top}"
    )
    if failed[:30]:
        print(f"  failed sample: {''.join(failed[:40])}")
    return out, len(filled), len(failed)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--translated", type=Path, default=DEFAULT_TRANSLATED)
    ap.add_argument("--font-config", type=Path, default=DEFAULT_FONT_CFG)
    ap.add_argument("--charmap", type=Path, default=DEFAULT_CHARMAP)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--fonts", type=Path, nargs="*", default=None)
    ap.add_argument(
        "--only",
        choices=("normal", "middle", "small"),
        nargs="*",
        default=None,
    )
    a = ap.parse_args()

    if not a.translated.is_file():
        raise SystemExit(f"missing {a.translated}")

    slots = load_slots_from_font_config(a.font_config)
    fonts_arg = list(a.fonts) if a.fonts else [p for p in DEFAULT_FONTS if p.exists()]
    font_files = collect_font_files(fonts_arg)
    if not font_files:
        raise SystemExit("no outline fonts found")

    chars = collect_charset(a.translated, a.charmap)
    cjk = sum(1 for c in chars if 0x4E00 <= ord(c) <= 0x9FFF)
    print(f"charset: {len(chars)} (CJK {cjk}) from {a.translated.name}")
    print(f"outline fonts ({len(font_files)}):")
    for f in font_files:
        print(f"  {f}")

    names = list(a.only) if a.only else ["normal", "middle", "small"]
    for name in names:
        print(f"=== {name} ===")
        gen_one(name, slots[name], chars, font_files, a.out_dir)
    print("done (FT_MONO + NotoSansSC-first; metrics-only sizes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
