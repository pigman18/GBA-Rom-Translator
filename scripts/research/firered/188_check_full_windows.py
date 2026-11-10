#!/usr/bin/env python3
"""调研(188) 检查「满新增但不在文本区」的窗口：0x9B3xxx / 0xAB8xxx / 0xE4Axxx。

═══════════════════════════════════════════════════════════════════════════
【(187) 之后剩下的候选】
═══════════════════════════════════════════════════════════════════════════
主文本区 0x6D0000..0x727000 已确认 **纯 F7 文本**（字模候选 0/128）。

剩余「4KB 窗口 100% 满新增」且不属于文本流的三个点：
    0x009B3000 / 0x009B4000 / 0x009B5000   （连续 12KB）
    0x00AB8000                             （4KB）
    0x00E4A000                             （4KB）

这些窗口原版全是 0xFF、汉化全填满 ⇒ 是纯新增数据块，最像字库。

【本脚本对每个候选做四件事】
 A. 字节直方图：F7/FF/00 密度（判断是否还是文本）
 B. 32B 块可视化（通用 4bpp 灰度，不做值假设）
 C. 8x16 竖拼可视化（每两个 32B 块上下拼）
 D. 与 VRAM 已知字形比对：逐字节最大重合度
    —— 若重合度 ≥28/32，直接确认

【可视化用「自适应映射」】
不假设 nibble 只有 10/11/12，而是按块内出现过的最小/最大值做线性拉伸，
这样任意编码都能看出图形。

用法：python scripts/research/firered/188_check_full_windows.py
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "cand188"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
SCREEN_BASE = 0xF000

CANDS = [0x009B3000, 0x009B4000, 0x009B5000, 0x00AB8000, 0x00E4A000,
         0x00739000, 0x00730000]


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def entry(vr: bytes, r: int, c: int) -> int:
    return struct.unpack_from("<H", vr, SCREEN_BASE + (r * 32 + c) * 2)[0]


def save_png(path: Path, arr: np.ndarray) -> None:
    import zlib
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return (struct.pack(">I", len(data)) + c
                + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9))
                     + chunk(b"IEND", b""))


def render_blocks(blocks: list[bytes], cols: int, scale: int,
                  vertical: bool = False) -> np.ndarray:
    """通用渲染：块内值线性拉伸到灰度。vertical=True 时两两上下拼。"""
    if vertical:
        pairs = []
        for i in range(0, len(blocks) - 1, 2):
            pairs.append((blocks[i], blocks[i + 1]))
        rows = (len(pairs) + cols - 1) // cols
        cw = 8 * scale + 2
        chh = 16 * scale + 2
        img = np.full((rows * chh, cols * cw, 3), 16, dtype=np.uint8)
        for i, (a, b) in enumerate(pairs):
            m = np.vstack([tile_nibs(a), tile_nibs(b)])
            lo, hi = int(m.min()), int(m.max())
            rng = max(1, hi - lo)
            ry, rx = divmod(i, cols)
            for y in range(16):
                for x in range(8):
                    g = int((int(m[y, x]) - lo) * 255 / rng)
                    img[ry * chh + y * scale:ry * chh + (y + 1) * scale,
                        rx * cw + x * scale:rx * cw + (x + 1) * scale] = (g, g, g)
        return img

    rows = (len(blocks) + cols - 1) // cols
    cw = 8 * scale + 2
    chh = 8 * scale + 2
    img = np.full((rows * chh, cols * cw, 3), 16, dtype=np.uint8)
    for i, blob in enumerate(blocks):
        m = tile_nibs(blob)
        lo, hi = int(m.min()), int(m.max())
        rng = max(1, hi - lo)
        ry, rx = divmod(i, cols)
        for y in range(8):
            for x in range(8):
                g = int((int(m[y, x]) - lo) * 255 / rng)
                img[ry * chh + y * scale:ry * chh + (y + 1) * scale,
                    rx * cw + x * scale:rx * cw + (x + 1) * scale] = (g, g, g)
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rom = ROM_ZH.read_bytes()
    rom_or = ROM_OR.read_bytes()
    vr = (SNAP / "vram.bin").read_bytes()

    # VRAM 已知字形（全部含笔画的 32B 块）
    vr_tiles = []
    for t in range(0, 800):
        blob = vr[t * 32:t * 32 + 32]
        if len(blob) < 32:
            break
        m = tile_nibs(blob)
        if int((m == 12).sum()) + int((m == 11).sum()) > 2:
            vr_tiles.append(blob)
    print(f"VRAM 字形块：{len(vr_tiles)}")

    report = {}
    for base in CANDS:
        seg = rom[base:base + 0x1000]
        if len(seg) < 0x1000:
            continue
        print("\n" + "=" * 78)
        print(f"候选 0x{base:08X}")
        print("=" * 78)

        # A 直方图
        c = Counter(seg)
        n = len(seg)
        print(f"  F7={c.get(0xF7, 0) / n:>6.1%}  FF={c.get(0xFF, 0) / n:>6.1%}  "
              f"00={c.get(0x00, 0) / n:>6.1%}  值种类={len(c)}")
        top = c.most_common(6)
        print(f"  最常见 {[(hex(v), f'{k / n:.1%}') for v, k in top]}")

        # 原版
        ors = rom_or[base:base + 0x1000]
        cor = Counter(ors)
        print(f"  原版 FF={cor.get(0xFF, 0) / n:>6.1%}  "
              f"值种类={len(cor)}")

        # B/C 渲染
        blocks = [seg[i * 32:(i + 1) * 32] for i in range(128)]
        img8 = render_blocks(blocks, cols=16, scale=2, vertical=False)
        p8 = OUT / f"C_{base:08X}_8x8.png"
        save_png(p8, img8)
        img16 = render_blocks(blocks, cols=12, scale=2, vertical=True)
        p16 = OUT / f"C_{base:08X}_8x16.png"
        save_png(p16, img16)
        print(f"  ✔ {p8.name} / {p16.name}")

        # D 与 VRAM 比对
        best = (0, None)
        for i, blob in enumerate(blocks):
            for j, vt in enumerate(vr_tiles):
                same = sum(1 for a, b in zip(blob, vt) if a == b)
                if same > best[0]:
                    best = (same, (i, j))
        print(f"  与 VRAM 字形最高重合：{best[0]}/32  "
              f"(块{best[1][0] if best[1] else '-'} vs tile"
              f"{best[1][1] if best[1] else '-'})")
        if best[0] >= 28:
            print("  ★★★ 高度吻合 —— 这就是字库块")

        # 打印前 4 块字符画（十六进制）
        print("  前 4 块：")
        for i, blob in enumerate(blocks[:4]):
            m = tile_nibs(blob)
            print(f"    块{i}:")
            for y in range(8):
                print("      " + "".join(f"{int(v):X}" for v in m[y]))

        report[f"0x{base:08X}"] = {
            "f7": c.get(0xF7, 0) / n, "ff": c.get(0xFF, 0) / n,
            "zero": c.get(0x00, 0) / n, "nvals": len(c),
            "best_match": best[0],
        }

    print("\n" + "=" * 78)
    print("汇总")
    print("=" * 78)
    for k, v in report.items():
        print(f"  {k}  F7={v['f7']:.1%}  值种类={v['nvals']:>3}  "
              f"VRAM最高重合={v['best_match']}/32")

    (OUT / "cands.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'cands.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
