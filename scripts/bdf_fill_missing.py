#!/usr/bin/env python3
"""Fill missing Unicode glyphs into a BDF by rasterizing system / listed fonts.

Loads **all** fonts you pass (files or directories), tries each in order until a
glyph has enough ink, then appends/replaces the BDF entry.

Typical flow after FireRed export:
  1. scripts/firered_export_bdf.py → normal_firered.bdf (+ .map.csv)
  2. python scripts/bdf_fill_missing.py \\
       --bdf configs/POKEMON_RUBY_AXVJ00/fonts/normal_firered.bdf \\
       --charmap configs/POKEMON_RUBY_AXVJ00/charmap.txt \\
       --fonts C:/Windows/Fonts/simsun.ttc C:/Windows/Fonts/msyh.ttc \\
       --out configs/POKEMON_RUBY_AXVJ00/fonts/normal.bdf

Only fills encodings required by charmap that are absent (or PUA-only) in
the input BDF. Existing real Unicode glyphs are kept.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_chinese_font import parse_bdf  # noqa: E402

SLOT = 16
INK_TARGET = 12  # FireRed-like advance cell


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


def load_charmap_chars(charmap: Path) -> list[str]:
    seen: dict[str, None] = {}
    pat = re.compile(r"^([0-9A-Fa-f]+)=(.+)$")
    for line in charmap.read_text("utf-8").splitlines():
        line = line.strip()
        m = pat.match(line)
        if not m:
            continue
        ch = m.group(2).strip()
        if len(ch) == 1 and ord(ch) > 0x7F:
            seen.setdefault(ch, None)
    return list(seen.keys())


def load_pil_fonts(files: list[Path], px: int) -> list[tuple[str, ImageFont.FreeTypeFont]]:
    loaded: list[tuple[str, ImageFont.FreeTypeFont]] = []
    for f in files:
        # TTC may have multiple faces
        for index in range(0, 8):
            try:
                font = ImageFont.truetype(str(f), px, index=index)
                loaded.append((f"{f.name}#{index}", font))
            except OSError:
                break
            except Exception:
                break
    return loaded


def rasterize(
    ch: str,
    fonts: list[tuple[str, ImageFont.FreeTypeFont]],
    *,
    slot: int = SLOT,
    ink: int = INK_TARGET,
    pad_top: int | None = None,
    thresh: int = 96,
    min_ink: int = 8,
) -> tuple[list[str], str] | None:
    """Return (BDF hex rows for slot×slot, font_tag) or None."""
    SS = 4
    big = max(ink, 8) * SS * 3
    pad = (
        pad_top
        if pad_top is not None
        else max(0, (slot - ink) // 2)
    )
    for tag, font in fonts:
        img = Image.new("L", (big, big), 0)
        draw = ImageDraw.Draw(img)
        draw.text((big // 6, big // 6), ch, fill=255, font=font)
        bbox = img.getbbox()
        if bbox is None:
            continue
        crop = img.crop(bbox)
        tw, th = crop.size
        scale = min(ink / tw, ink / th)
        nw = max(1, min(ink, int(round(tw * scale))))
        nh = max(1, min(ink, int(round(th * scale))))
        rs = crop.resize((nw, nh), Image.Resampling.LANCZOS)
        cell = Image.new("L", (slot, slot), 0)
        ox = max(0, (slot - nw) // 2)
        oy = max(0, min(slot - nh, pad + max(0, (ink - nh) // 2)))
        cell.paste(rs, (ox, oy))
        px = cell.load()
        ink_n = sum(
            1
            for y in range(slot)
            for x in range(slot)
            if px[x, y] >= thresh
        )
        if ink_n < min_ink:
            continue
        rows: list[str] = []
        for y in range(slot):
            buf = bytearray(2)  # 16 bits
            for x in range(slot):
                if px[x, y] >= thresh:
                    buf[x // 8] |= 0x80 >> (x % 8)
            rows.append(buf.hex().upper())
        return rows, tag
    return None


def bdf_has_real_unicode(glyphs: dict[int, tuple], enc: int) -> bool:
    if enc not in glyphs:
        return False
    # treat BMP PUA as "not real" so fill can replace FireRed unmatched
    if 0xE000 <= enc <= 0xF8FF:
        return False
    return True


def rewrite_bdf(
    src_path: Path,
    glyphs_keep: dict[int, tuple],
    new_chars: dict[int, tuple[list[str], str]],
    out: Path,
    *,
    ascent: int,
    descent: int,
    pixel_size: int,
) -> None:
    """Rebuild BDF: keep non-replaced glyphs from parse structure via re-emit."""
    # Re-parse source text blocks by ENCODING for comments/order is heavy;
    # emit a clean BDF from keep + new.
    all_enc = sorted(set(glyphs_keep.keys()) | set(new_chars.keys()))
    lines = [
        "STARTFONT 2.1",
        "FONT -Meowth-Normal-Medium-R-Normal--16-160-75-75-C-120-ISO10646-1",
        "SIZE 16 75 75",
        "FONTBOUNDINGBOX 16 16 0 -2",
        "STARTPROPERTIES 6",
        f"FONT_ASCENT {ascent}",
        f"FONT_DESCENT {descent}",
        "DEFAULT_CHAR 0",
        f"PIXEL_SIZE {pixel_size or 16}",
        'COMMENT "bdf_fill_missing.py: FireRed base + TTF fill for gaps"',
        "ENDPROPERTIES",
        f"CHARS {len(all_enc)}",
        "",
    ]
    for enc in all_enc:
        if enc in new_chars:
            hex_rows, tag = new_chars[enc]
            lines.append(f"STARTCHAR U+{enc:04X}")
            lines.append(f"ENCODING {enc}")
            lines.append("SWIDTH 120 0")
            lines.append("DWIDTH 12 0")
            lines.append("BBX 16 16 0 -2")
            lines.append(f'COMMENT "fill from {tag}"')
            lines.append("BITMAP")
            lines.extend(hex_rows)
            lines.append("ENDCHAR")
            lines.append("")
        else:
            bitmap, bw, bh, bx, by = glyphs_keep[enc]
            lines.append(f"STARTCHAR U+{enc:04X}")
            lines.append(f"ENCODING {enc}")
            lines.append("SWIDTH 120 0")
            lines.append("DWIDTH 12 0")
            lines.append(f"BBX {bw} {bh} {bx} {by}")
            lines.append("BITMAP")
            for row in bitmap:
                lines.append(row.hex().upper())
            lines.append("ENDCHAR")
            lines.append("")
    lines.append("ENDFONT")
    lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bdf", type=Path, required=True, help="input BDF to extend")
    ap.add_argument(
        "--charmap",
        type=Path,
        default=ROOT / "configs/POKEMON_RUBY_AXVJ00/charmap.txt",
    )
    ap.add_argument(
        "--fonts",
        type=Path,
        nargs="*",
        default=None,
        help="font files and/or directories (loads all TTF/TTC/OTF inside dirs)",
    )
    ap.add_argument(
        "--fonts-dir",
        type=Path,
        action="append",
        default=[],
        help="extra directory of fonts (repeatable); merged with --fonts",
    )
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--px", type=int, default=48, help="TTF render px before downscale")
    ap.add_argument("--thresh", type=int, default=96)
    ap.add_argument("--ink", type=int, default=INK_TARGET, help="ink cell size (normal=12, small=9)")
    ap.add_argument(
        "--pad-top",
        type=int,
        default=None,
        help="vertical pad in 16 slot (normal≈2, small=6); default (16-ink)//2",
    )
    ap.add_argument(
        "--replace-pua",
        action="store_true",
        help="also refill charmap chars that only exist as PUA in input",
    )
    a = ap.parse_args()

    default_fonts = [
        Path(r"C:\Windows\Fonts\simsun.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\Deng.ttf"),
    ]
    fonts_arg = list(a.fonts) if a.fonts else [p for p in default_fonts if p.exists()]
    fonts_arg.extend(a.fonts_dir)

    font_files = collect_font_files(fonts_arg)
    if not font_files:
        raise SystemExit("no font files found")
    print(f"fonts ({len(font_files)}):")
    for f in font_files[:20]:
        print(f"  {f}")
    if len(font_files) > 20:
        print(f"  … +{len(font_files) - 20} more")

    pil_fonts = load_pil_fonts(font_files, a.px)
    print(f"loaded faces: {len(pil_fonts)}")

    glyphs, ascent, descent, pixel_size = parse_bdf(a.bdf)
    chars = load_charmap_chars(a.charmap)
    print(f"charmap chars: {len(chars)}  bdf glyphs: {len(glyphs)}")

    missing: list[str] = []
    for ch in chars:
        enc = ord(ch)
        if not bdf_has_real_unicode(glyphs, enc):
            missing.append(ch)
    print(f"missing (need fill): {len(missing)}")

    filled: dict[int, tuple[list[str], str]] = {}
    failed: list[str] = []
    min_ink = 4 if a.ink <= 9 else 8
    for i, ch in enumerate(missing):
        got = rasterize(
            ch,
            pil_fonts,
            thresh=a.thresh,
            ink=a.ink,
            pad_top=a.pad_top,
            min_ink=min_ink,
        )
        if got is None:
            failed.append(ch)
            continue
        rows, tag = got
        filled[ord(ch)] = (rows, tag)
        if (i + 1) % 500 == 0:
            print(f"  … {i + 1}/{len(missing)}")

    # drop PUA placeholders for chars we filled
    keep = {
        enc: g
        for enc, g in glyphs.items()
        if not (0xE000 <= enc <= 0xF8FF and any(ord(c) in filled for c in missing))
    }
    # Actually keep all non-PUA; drop PUA always when writing merged set
    keep = {enc: g for enc, g in glyphs.items() if not (0xE000 <= enc <= 0xF8FF)}

    rewrite_bdf(
        a.bdf,
        keep,
        filled,
        a.out,
        ascent=ascent,
        descent=descent,
        pixel_size=pixel_size,
    )
    print(f"wrote {a.out}")
    print(f"  kept={len(keep)}  filled={len(filled)}  failed={len(failed)}")
    if failed[:20]:
        print(f"  failed sample: {''.join(failed[:40])}")
    return 0 if not failed else 0  # soft OK — report only


if __name__ == "__main__":
    raise SystemExit(main())
