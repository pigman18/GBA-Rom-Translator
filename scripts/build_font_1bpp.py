#!/usr/bin/env python3
"""BDF → 1bpp 位流字库导出（charmap 序）。

**权威源 = `fonts/default/*.bdf`**（2026-09-10 用户拍板：「以 fonts/default/*.bdf
为权威入口，改字即生效」）。本脚本是 BDF 通往 ROM 1bpp 字库的唯一通道 —— 汉字
实际渲染读的就是这两个 1bpp 库（`text_translater.c` 的 `ADDR_FONT_1BPP_BIG /
ADDR_FONT_1BPP_SMALL`），所以改完 BDF 跑一遍流水线，游戏里的字就变了。

几何必须与渲染端/提取端**严格互逆**（否则字形平移或镜像）：
  text_translater.c  `CHS_1BPP_ROW_OFF_BIG=2` / `CHS_1BPP_ROW_OFF_SMALL=5`
  chinese_glyph.c    位流 `bits[r*width + x]`（MSB-first，行间无填充）
                     → 落 cell 行 `row_off+r`、列 `x`
  ⇒ 本脚本反向：cell 行 `row_off+r`、列 `[x0, x0+width)` → 位流第 `r*width+c` 位

位流步进 = `ceil(W*H/8)`（11×11→16 B、9×9→11 B）；末字节**填充位恒置 0**
（渲染端不读它们；归零后 bin 是 BDF 的确定性函数，往返可逐字节比对）。

槽位来自 `translate/font.config.json` 的 `extra_bins[]`，每项需带
`"bdf"` 与 `"ink_fixed": "WxH+X+Y"`（X/Y = 在 16×16 cell 内的列/行偏移）。

历史：本脚本原从 `tools/Pokemon_GBA_Font_Patch/pokeE/graphics/fonts/gba_chs_font_
{11x11,9x9}.bin` 搬位流、非 GB2312 符号再从 4bpp 库阈值派生（两条源互不相干）。
2026-09-10 改为纯 BDF 源 —— 现有 BDF 即从这两个 bin 提取，实测有效位 6807/6807
逐位一致，所以切换零风险，同时消掉了「改 BDF 不生效」的断链。

用法：
  python scripts/build_font_1bpp.py                  # 写 work/<GAME>/graphic/fonts（流水线唯一消费位置）
  python scripts/build_font_1bpp.py --out-dir <dir>  # 指定输出目录（可多个）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_chinese_font import parse_charmap  # noqa: E402

DEFAULT_GAME = "POKEMON_RUBY_AXVJ00"
DEFAULT_SLOT_N = 7168


def parse_bdf_cells(path: Path) -> dict[int, list[int]]:
    """BDF → {encoding: [每行 int，bit15 = 最左列]}（含全 16 行）。"""
    text = path.read_text(encoding="ascii", errors="replace")
    cells: dict[int, list[int]] = {}
    for m in re.finditer(
        r"^STARTCHAR.*?^ENCODING\s+(\d+).*?^BITMAP\s*$(.*?)^ENDCHAR",
        text,
        re.M | re.S,
    ):
        rows = [int(ln, 16) for ln in m.group(2).split() if ln]
        cells[int(m.group(1))] = rows
    return cells


def parse_ink_fixed(spec: str) -> tuple[int, int, int, int]:
    """`WxH+X+Y` → (w, h, x0, y0)，语义与 build_chinese_font.py 的 --ink-fixed 一致。"""
    m = re.fullmatch(r"(\d+)x(\d+)\+(\d+)\+(\d+)", str(spec).strip())
    if not m:
        raise ValueError(f"ink_fixed 格式应为 WxH+X+Y（如 11x11+0+2），收到 {spec!r}")
    w, h, x0, y0 = (int(v) for v in m.groups())
    return w, h, x0, y0


def pack_1bpp(rows: list[int], x0: int, y0: int, width: int, height: int) -> bytes:
    """16×16 cell → 1bpp 位流（每行 width 位 MSB-first，行间无填充）。"""
    stride = (width * height + 7) // 8
    out = bytearray(stride)
    bit = 0
    for r in range(height):
        y = y0 + r
        row = rows[y] if 0 <= y < len(rows) else 0
        for c in range(width):
            if (row >> (15 - (x0 + c))) & 1:
                out[bit >> 3] |= 0x80 >> (bit & 7)
            bit += 1
    return bytes(out)


def build_slot(label: str, spec: dict, charmap: dict[int, str], bdf_base: Path,
               slot_n: int) -> tuple[bytes, dict]:
    rel = spec.get("bdf")
    if not rel:
        raise ValueError(f"extra_bins[{label}]: 缺少 \"bdf\"（权威源必须是 BDF）")
    if not spec.get("ink_fixed"):
        raise ValueError(f"extra_bins[{label}]: 缺少 \"ink_fixed\"（WxH+X+Y）")

    bdf_path = Path(rel)
    if not bdf_path.is_absolute():
        bdf_path = bdf_base / bdf_path
    if not bdf_path.is_file():
        raise FileNotFoundError(f"extra_bins[{label}]: BDF 不存在: {bdf_path}")

    width, height, x0, y0 = parse_ink_fixed(spec["ink_fixed"])
    stride = (width * height + 7) // 8
    declared = int(spec.get("bytes_per_glyph", stride))
    if declared != stride:
        raise ValueError(
            f"extra_bins[{label}]: bytes_per_glyph={declared} 与 ink_fixed "
            f"{width}x{height} 的步进 {stride} 不符"
        )

    cells = parse_bdf_cells(bdf_path)
    buf = bytearray(slot_n * stride)
    stat = {"filled": 0, "blank": 0, "no_glyph": 0, "no_mapping": 0}

    for slot in range(slot_n):
        ch = charmap.get(slot)
        if not ch or len(ch) != 1:
            stat["no_mapping"] += 1
            continue
        rows = cells.get(ord(ch))
        if rows is None:
            stat["no_glyph"] += 1
            continue
        packed = pack_1bpp(rows, x0, y0, width, height)
        buf[slot * stride:(slot + 1) * stride] = packed
        if any(packed):
            stat["filled"] += 1
        else:
            stat["blank"] += 1

    stat.update({
        "label": label, "bdf": bdf_path.name, "geometry": f"{width}x{height}+{x0}+{y0}",
        "stride": stride, "size": len(buf), "slot_n": slot_n,
    })
    return bytes(buf), stat


def main() -> None:
    ap = argparse.ArgumentParser(
        description="BDF (fonts/default/*.bdf) -> 1bpp glyph bins (charmap order)"
    )
    ap.add_argument("--game", default=DEFAULT_GAME)
    ap.add_argument("--config", type=Path, default=None,
                    help="font.config.json（默认 configs/<GAME>/translate/font.config.json）")
    ap.add_argument("--charmap", type=Path, default=None,
                    help="charmap（默认 work/<GAME>/charmap.txt，回退 configs/<GAME>/charmap.txt）")
    ap.add_argument("--bdf-base", type=Path, default=None,
                    help="解析 config 内相对 bdf 路径的基准目录（默认仓库根）")
    ap.add_argument("--out-dir", type=Path, nargs="+", default=None,
                    help="输出目录，可多个（默认 work/<GAME>/graphic/fonts）")
    args = ap.parse_args()

    game = args.game
    cfg_path = args.config or (ROOT / "configs" / game / "translate" / "font.config.json")
    if not cfg_path.is_file():
        print(f"error: 找不到 {cfg_path}", file=sys.stderr)
        sys.exit(1)
    fp_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    charmap_path = args.charmap
    if charmap_path is None:
        for cand in (ROOT / "work" / game / "charmap.txt",
                     ROOT / "configs" / game / "charmap.txt"):
            if cand.is_file():
                charmap_path = cand
                break
    if charmap_path is None or not Path(charmap_path).is_file():
        print(f"error: 找不到 charmap（试过 work/ 与 configs/）", file=sys.stderr)
        sys.exit(1)

    bdf_base = args.bdf_base or ROOT
    # 唯一消费位置：fonts.s 的 .incbin 绝对指向这儿。
    # （仓库根 graphic/fonts 拍照镜像已于 2026-09-11 删除，不再双写。）
    out_dirs = [Path(p) for p in (args.out_dir or [
        ROOT / "work" / game / "graphic" / "fonts",
    ])]

    charmap = parse_charmap(Path(charmap_path))
    prefix = fp_cfg.get("font_bin_prefix", "PokeRSFontChs")
    extra_bins = [s for s in (fp_cfg.get("extra_bins") or []) if s.get("bdf")]
    if not extra_bins:
        print("warning: font.config.json 的 extra_bins 里没有任何带 \"bdf\" 的槽，无事可做")
        return
    print(f"config   : {cfg_path}")
    print(f"charmap  : {charmap_path} ({len(charmap)} slots)")

    for spec in extra_bins:
        label = spec.get("label", "Extra")
        slot_n = int(spec.get("glyph_count", DEFAULT_SLOT_N))
        data, stat = build_slot(label, spec, charmap, bdf_base, slot_n)
        name = f"{prefix}{label}_unshadow(0x{stat['size']:X}).bin"
        for d in out_dirs:
            d.mkdir(parents=True, exist_ok=True)
            (d / name).write_bytes(data)
        print(
            f"{label:<10} <- {stat['bdf']} [{stat['geometry']}] "
            f"filled={stat['filled']} blank={stat['blank']} "
            f"no_glyph={stat['no_glyph']} no_mapping={stat['no_mapping']} "
            f"-> {name} ({stat['size']} B)"
        )
    print("out dirs : " + ", ".join(str(d) for d in out_dirs))


if __name__ == "__main__":
    sys.exit(main())
