#!/usr/bin/env python3
"""scripts/misc/harvest_bg_tilesets.py — 从 bot 快照反查 BG 图块集（tileset）

## 为什么需要这个

`gdb_patcher` 的 `TilesHarvester` 只盯 **OBJ（精灵）**：
`LoadSpriteSheet` / `LoadCompressedObjectPic` / `CreateSprite`。
所以 yaml 的 `tiles.presets` 里全是 OBJ 图，**没有一个 BG 图块集**。

但真正含日文 UI 图的内容主要在 **BG 层**：
  · 背包页的 `たいせつなもの / モンスターボール / どうぐ / わざマシン`
  · 各种菜单横幅、按钮、面板
实测背包帧 003：BG 区非空 tile 708 个，其中 164 个能反查回 ROM，
来源集中在 `0x087F2134`（119 tiles）和 `0x087F27E0`（37 tiles）。

## 做法

对每个 bot 快照帧：
  1. 读 BGxCNT 得到每层的 charBase / screenBase / bpp
  2. 取该层 tileData 区的每个 8x8 tile 原始字节
  3. 逐个在 **ROM 全部 LZ77 解压块**里搜 → 命中即得 ROM 地址
  4. 用 BGxCNT 对应层 + tilemap 的 palbank 去 CGRAM 取真实调色板
  5. 同一 ROM 块的命中 tile 数 ≥ 阈值 ⇒ 认定为「一个 tileset」，输出配置

## 输出

每条配置形如：

    - id: bg_087F2134
      label: BG tileset @0x087F2134（来自 bag 场景）
      address: '0x087F2134'
      palette: '0x080xxxxx'
      format: 4bpp
      compression: lz77_swap
      sprite_size: 8x8
      count: 126

## 用法

    C:/Python314/python.exe scripts/misc/harvest_bg_tilesets.py
    C:/Python314/python.exe scripts/misc/harvest_bg_tilesets.py --write
"""
from __future__ import annotations

import argparse
import struct
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "util"))

from tiles_patcher import lz77_decompress             # noqa: E402
from util.gba_ppu import Snapshot                     # noqa: E402

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BOT_ROOT = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"


def build_rom_index(rom: bytes):
    """LZ77 解压块 → [(addr, data)]。"""
    out = []
    for off in range(0, len(rom) - 4, 4):
        if rom[off] != 0x10:
            continue
        dst = rom[off + 1] | (rom[off + 2] << 8) | (rom[off + 3] << 16)
        if dst < 32 or dst > 0x40000:
            continue
        for swap in (True, False):
            try:
                d = lz77_decompress(rom[off:], swap=swap)
            except Exception:
                continue
            if d and len(d) == dst:
                out.append((0x08000000 + off, d, "lz77_swap" if swap else "lz77"))
                break
    return out


def cgram_bank(pal: bytes, bank: int) -> bytes:
    off = bank * 16 * 2
    return pal[off:off + 32]


def find_palette(rom: bytes, bank_bytes: bytes):
    out, i = [], rom.find(bank_bytes)
    while i >= 0:
        out.append(0x08000000 + i)
        i = rom.find(bank_bytes, i + 1)
    out.sort(key=lambda a: ((a - 0x08000000) % 4 != 0, a))
    return out


def scan_frame(snap: Snapshot, index):
    """扫一帧所有 BG 层的 tile，返回 {rom_addr: [tile 数, palbank, bpp8, 层号]}。"""
    hits = defaultdict(lambda: {"n": 0, "palbank": set(), "bpp8": False,
                                "bg": set()})
    for bg in range(4):
        if not snap.bg_on(bg):
            continue
        cnt = snap.bgcnt(bg)
        cb = (cnt >> 2) & 3
        bpp8 = bool(cnt & 0x80)
        char_base = cb * (0x8000 if bpp8 else 0x4000)
        stride = 64 if bpp8 else 32
        n_tiles = (0x8000 if bpp8 else 0x4000) // stride

        # 该层 tilemap 里出现的 palbank（4bpp）
        sb = (cnt >> 8) & 0x1F
        tm = sb * 0x800
        palbanks = {0}
        for i in range(0, 0x800, 2):
            if tm + i + 2 > len(snap.vram):
                break
            e = struct.unpack_from("<H", snap.vram, tm + i)[0]
            if not bpp8:
                palbanks.add((e >> 12) & 0xF)

        for t in range(n_tiles):
            off = char_base + t * stride
            if off + stride > min(len(snap.vram), 0x10000):
                continue
            blk = snap.vram[off:off + stride]
            if blk == b"\x00" * stride:
                continue
            for addr, data, comp in index:
                if blk in data:
                    h = hits[addr]
                    h["n"] += 1
                    h["bpp8"] = bpp8
                    h["bg"].add(bg)
                    h["palbank"] |= palbanks
                    break
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--limit-runs", type=int, default=400)
    ap.add_argument("--min-tiles", type=int, default=8,
                    help="一个 ROM 块至少被多少个 tile 命中才认定为 tileset")
    ap.add_argument("--scenes", default="bag,dex,pokemon_menu,start_menu,"
                                      "options,trainer_card,navigator,save")
    args = ap.parse_args()

    rom = ROM_PATH.read_bytes()
    print(f"ROM {len(rom)} bytes")
    print("建 ROM LZ77 索引...")
    index = build_rom_index(rom)
    print(f"  {len(index)} 块\n")

    scenes = args.scenes.split(",")
    agg = defaultdict(lambda: {"n": 0, "bpp8": False, "palbank": set(),
                               "scenes": set(), "comp": "", "maxn": 0})

    for sc in scenes:
        runs = sorted((BOT_ROOT / sc).glob("*/origin"))[-3:]
        for d in runs:
            for p in [x for x in d.glob("*.png") if x.stem.isdigit()][:2]:
                if not (d / f"{p.stem}.vram.bin").is_file():
                    continue
                try:
                    snap = Snapshot.load(d, p.stem)
                except Exception:
                    continue
                h = scan_frame(snap, index)
                for addr, v in h.items():
                    a = agg[addr]
                    a["n"] += v["n"]
                    a["maxn"] = max(a["maxn"], v["n"])
                    a["bpp8"] = v["bpp8"]
                    a["palbank"] |= v["palbank"]
                    a["scenes"].add(sc)
    print(f"扫 {len(scenes)} 个场景，命中 {len(agg)} 个 ROM 块\n")

    rows = []
    for addr, a in agg.items():
        if a["n"] < args.min_tiles:
            continue
        data = next((d for ad, d, c in index if ad == addr), None)
        comp = next((c for ad, d, c in index if ad == addr), "lz77_swap")
        if data is None:
            continue
        stride = 64 if a["bpp8"] else 32
        total_tiles = len(data) // stride
        rows.append({
            "addr": addr, "tiles": total_tiles,
            "hits": a["n"], "bpp8": a["bpp8"],
            "palbank": sorted(a["palbank"]),
            "scenes": sorted(a["scenes"]),
            "comp": comp, "bytes": len(data),
        })
    rows.sort(key=lambda r: -r["hits"])

    print(f"{'地址':12s} {'tiles':>6s} {'命中':>5s} {'bpp':>4s} "
          f"{'palbank':10s} 场景")
    for r in rows[:30]:
        print(f"0x{r['addr']:08X} {r['tiles']:6d} {r['hits']:5d} "
              f"{'8' if r['bpp8'] else '4':>4s} "
              f"{str(r['palbank']):10s} {','.join(r['scenes'][:4])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
