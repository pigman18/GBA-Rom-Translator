#!/usr/bin/env python3
"""harvest_all_scene_assets.py — 把「背包抓图」那套逻辑铺到全部 bot 场景

## 思路（每一步都基于真实运行时状态，不猜）

1. 只收 **能精确重放** 的帧：`render(snapshot)` 与该帧 PNG 比对，
   一致率 < 阈值（默认 99%）说明该场景有卷动 / 未实现的特效，跳过并记账。
   这一条同时把「卷动≠0 的大地图场景」自然挡在外面（UI/菜单/战斗/对话卷动就是 0）。
2. 每个在用的 BG 层：取屏幕 30×20 格用到的 tile，先按「8 连续 tile」当锚点，
   在 ROM 全部 LZ77 解压块里做子串搜索 → 得到块地址 + 块内偏移；
   再验证该层其余 tile 有多少能对上（覆盖率），取最高分的块。
3. 调色板：按该层 tilemap 的 palbank 组装 32B，先找 raw，再找「同一 LZ 块里
   连续排着 bank0..bankN」的情况（背包就是这么排的）。
4. 拼图：直接用 `bg_text_layer` 渲染结果，按该图块集覆盖的格子算 bbox 裁剪。
5. 按 (场景, 层, 图块集地址, 偏移, 调色板) 去重，保留覆盖率最高的一帧。

## 输出

    work/scene_assets/
      catalog.json                  全部条目（含地址/调色板/裁剪框/来源帧）
      <scene>/<bg>_<addr>_<off>.png 每个场景每个图块集的裁剪图
      report.md                     按图块集汇总，方便看哪些是日文 UI

用法：
    C:/Python314/python.exe scripts/misc/harvest_all_scene_assets.py
    ... --scenes bag,dex --frames 12
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "util"))

import numpy as np                                   # noqa: E402
from PIL import Image                                # noqa: E402

from util.gba_ppu import Snapshot, bg_text_layer, compare, render  # noqa: E402
from util.tiles_patcher import lz77_decompress                # noqa: E402

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BOT_ROOT = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"

VIS_W, VIS_H = 30, 20          # 240×160 的格数
SCREEN = (240, 160)


def build_blocks(rom: bytes):
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
                out.append((0x08000000 + off, "lz77_swap" if swap else "lz77", d))
                break
    return out


def tile_bytes(vram, char_base: int, t: int, stride: int) -> bytes:
    off = char_base + t * stride
    return bytes(vram[off:off + stride])


def build_tile_index(blocks):
    """tile 字节 → [(块地址, 压缩, 块内 tile 号)]。

    BG 层的 char base 经常「ROM 图块 + 运行时打印的字形」混在一起，
    所以按连续 8 tile 找锚点会失效；改成逐 tile 投票：
    每个 tile 在哪些块、什么位置出现过，再按 (块, 块内起点) 投票。
    """
    idx: dict[bytes, list] = {}
    zeros = (b"\x00" * 32, b"\x00" * 64)
    for addr, comp, data in blocks:
        n = len(data) // 32
        for i in range(n):
            b = data[i * 32:(i + 1) * 32]
            if b in zeros:
                continue
            lst = idx.get(b)
            if lst is None:
                idx[b] = [(addr, comp, i)]
            elif len(lst) < 6:
                lst.append((addr, comp, i))
    return idx


def match_tileset(vram, char_base: int, bpp: int, tiles: list[int],
                  blocks, index, rom=None):
    """逐 tile 投票 → 选出覆盖最多的 (ROM 块, 块内起点)。

    先按 LZ77 块投票；若覆盖不够，再拿最「复杂」的几个 tile 去整份 ROM 里
    未压缩搜索 —— 相当一部分地图图块集是不压缩直接躺在 ROM 里的。
    返回 {addr, comp, offset, data, cov, n}。
    """
    stride = 64 if bpp == 8 else 32
    zero = b"\x00" * stride
    # 采样：最多 48 个 tile，覆盖整个 tile 号范围
    sample = tiles if len(tiles) <= 48 else tiles[::max(1, len(tiles) // 48)][:48]
    votes: dict[tuple, int] = {}
    for t in sample:
        b = tile_bytes(vram, char_base, t, stride)
        if b == zero:
            continue
        for addr, comp, i in index.get(b, []):
            key = (addr, comp, i * stride - t * stride)
            votes[key] = votes.get(key, 0) + 1

    best = None
    block_data = {a: d for a, _c, d in blocks}
    for (addr, comp, base), v in sorted(votes.items(), key=lambda kv: -kv[1])[:6]:
        # base 可以是负数：图块集整块从 tile 0 开始、而 VRAM 里的图块从
        # 更大的 tile 号起（OBJ 精灵图集就是这样），只要用到的 tile 都落在
        # 块内就行
        if base + min(tiles) * stride < 0:
            continue
        data = block_data[addr]
        cov = 0
        for t in tiles:
            a = base + t * stride
            if a + stride > len(data):
                continue
            if data[a:a + stride] == tile_bytes(vram, char_base, t, stride):
                cov += 1
        if best is None or cov > best["cov"]:
            best = {"addr": addr, "comp": comp, "offset": base,
                    "data": data, "cov": cov, "n": len(tiles),
                    "votes": v, "sampled": len(sample)}

    # ── 兜底：未压缩图块集直接躺在 ROM 里 ──
    need = max(4, int(0.25 * len(tiles)))
    if rom is not None and (best is None or best["cov"] < need):
        cands = []
        for t in sorted(tiles, key=lambda t: len(set(tile_bytes(
                vram, char_base, t, stride))), reverse=True)[:3]:
            blob = tile_bytes(vram, char_base, t, stride)
            if blob == zero:
                continue
            size = (max(tiles) + 1) * stride
            pos = rom.find(blob)
            hit = 0
            while pos >= 0 and hit < 2:
                base = pos - t * stride
                if base >= 0:
                    data = rom[base:base + size]
                    cov = sum(1 for tt in tiles
                              if data[tt * stride:(tt + 1) * stride]
                              == tile_bytes(vram, char_base, tt, stride))
                    cands.append({"addr": 0x08000000 + base, "comp": "raw",
                                  "offset": 0, "data": data, "cov": cov,
                                  "n": len(tiles), "votes": 0,
                                  "sampled": 0})
                pos = rom.find(blob, pos + 1)
                hit += 1
        for c in cands:
            if best is None or c["cov"] > best["cov"]:
                best = c
    return best


def find_palette(snap, palbanks: list[int], blocks, rom: bytes, bank_base: int = 0):
    """返回 {address, offset, size, banks}；优先「一个块里连续多 bank」。

    bank_base：CGRAM 里的字节偏移。BG 调色板从 0 开始，
    OBJ 调色板从 512（=颜色 256）开始 —— 精灵的 palbank 4 指的是
    CGRAM 第 260 组色，不是 BG 的 bank4（这是精灵颜色对不上的根因）。
    """
    banks = {}
    for b in palbanks:
        raw = bytes(snap.pal[bank_base + b * 32:bank_base + (b + 1) * 32])
        banks[b] = raw

    # 多 bank：在同一个 LZ 块里连续找
    if len(banks) > 1:
        b0 = banks[min(banks)]
        for addr, comp, data in blocks:
            pos = data.find(b0)
            while pos >= 0:
                base = pos - min(banks) * 32
                if base >= 0 and all(
                        data[base + b * 32:base + (b + 1) * 32] == banks[b]
                        for b in banks):
                    return {"address": addr, "offset": base,
                            "size": 32 * (max(banks) + 1),
                            "banks": sorted(banks), "compression": comp}
                pos = data.find(b0, pos + 1)

    # 单 bank：raw 优先，其次 LZ 块
    b0 = banks[min(banks)]
    hits, i = [], rom.find(b0)
    while i >= 0:
        hits.append(0x08000000 + i)
        i = rom.find(b0, i + 1)
    if hits:
        addr = sorted(hits, key=lambda a: ((a - 0x08000000) % 4 != 0, a))[0]
        return {"address": addr, "offset": 0, "size": 32 * (max(banks) + 1),
                "banks": sorted(banks), "compression": "none"}
    for addr, comp, data in blocks:
        pos = data.find(b0)
        if pos >= 0:
            return {"address": addr, "offset": pos,
                    "size": 32 * (max(banks) + 1),
                    "banks": sorted(banks), "compression": comp}
    return None


def visible_cells(snap: Snapshot, bg: int):
    cnt = snap.bgcnt(bg)
    bpp = 8 if (cnt & 0x80) else 4
    char_base = ((cnt >> 2) & 3) * 0x8000 if bpp == 8 else ((cnt >> 2) & 3) * 0x4000
    screen_base = ((cnt >> 8) & 0x1F) * 0x800
    words = np.frombuffer(snap.vram, dtype="<u2", count=len(snap.vram) // 2)
    cells = []
    for row in range(VIS_H):
        for col in range(VIS_W):
            e = int(words[(screen_base + row * 64 + col * 2) // 2])
            if e == 0:
                continue
            cells.append({"col": col, "row": row, "entry": e,
                          "tile": e & 0x3FF, "palbank": (e >> 12) & 0xF})
    return bpp, char_base, cells


def bbox(cells):
    c0 = min(c["col"] for c in cells); c1 = max(c["col"] for c in cells)
    r0 = min(c["row"] for c in cells); r1 = max(c["row"] for c in cells)
    return [c0 * 8, r0 * 8, (c1 - c0 + 1) * 8, (r1 - r0 + 1) * 8]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="all")
    ap.add_argument("--frames", type=int, default=16, help="每个场景最多取多少个不同帧")
    ap.add_argument("--runs", type=int, default=1, help="每个场景取最新几个 run")
    ap.add_argument("--min-cov", type=float, default=0.25,
                    help="一组 tile 里至少多少比例能在同一 ROM 块对上"
                         "（菜单层常混着运行时字形，比例不会高）")
    ap.add_argument("--min-cells", type=int, default=8)
    ap.add_argument("--replay", type=float, default=0.99)
    ap.add_argument("-o", default=str(ROOT / "work" / "scene_assets"))
    args = ap.parse_args()

    rom = ROM_PATH.read_bytes()
    print(f"ROM {len(rom)}B；建 LZ77 块缓存…", flush=True)
    blocks = build_blocks(rom)
    total = sum(len(d) for _a, _c, d in blocks)
    print(f"  {len(blocks)} 块 / {total / 1024:.0f}KB 缓存", flush=True)
    print("  建 tile 索引…", flush=True)
    tile_index = build_tile_index(blocks)
    print(f"  {len(tile_index)} 种不同 tile", flush=True)

    if args.scenes == "all":
        names = sorted(d.name for d in BOT_ROOT.iterdir()
                       if d.is_dir() and not d.name.startswith(("_lib", "_"))
                       and d.name not in ("images_dump",))
    else:
        names = [s.strip() for s in args.scenes.split(",") if s.strip()]

    out_root = Path(args.o).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    catalog = []
    skipped_frames = defaultdict(int)
    seen_frames: dict[str, set] = defaultdict(set)

    for name in names:
        scene_dir = BOT_ROOT / name
        runs = sorted([d for d in scene_dir.iterdir() if d.is_dir()],
                      key=lambda d: d.name)[-args.runs:]
        per_scene = 0
        for run in runs:
            side = run / "origin"
            if not side.is_dir():
                continue
            frames = sorted({p.name.split(".")[0] for p in side.glob("*.vram.bin")
                             if p.name.split(".")[0].isdigit()})
            if args.frames > 0 and len(frames) > args.frames:
                # bot 的 run 里「路过的户外地图」和「目标界面」混在一起，
                # 均匀采样整段，再由「重放率更高者胜」挑出真正的界面帧
                step = max(1, len(frames) // args.frames)
                frames = frames[::step][:args.frames]
            for n in frames:
                try:
                    snap = Snapshot.load(side, n)
                except Exception:
                    continue
                if snap.mode != 0:
                    continue
                img = render(snap)
                png = side / f"{n}.png"
                ratio = -1.0
                if png.is_file():
                    ratio = compare(img, png).get("ratio", 0)
                    # 只挡「转场/黑屏」这类完全对不上的帧；调色板淡入、
                    # 窗口/混合未实现会让整帧有偏差，但不影响图层图块本身
                    if ratio < 0.15:
                        skipped_frames[name] += 1
                        continue

                # 同场景同画面去重（vram 指纹）
                fp = hashlib.md5(bytes(snap.vram)).hexdigest()
                if fp in seen_frames[name]:
                    continue
                seen_frames[name].add(fp)

                for bg in range(4):
                    if not snap.bg_on(bg):
                        continue
                    bpp, char_base, cells = visible_cells(snap, bg)
                    stride = 64 if bpp == 8 else 32
                    if not cells:
                        continue
                    layer_img = None
                    remaining = list(cells)
                    # 一层里可能混着多块图块集（面板 / 字体 / 图标），
                    # 每轮剥掉已命中的格子，最多剥 4 轮
                    for _round in range(6):
                        tiles = sorted({c["tile"] for c in remaining})
                        if len(tiles) < args.min_cells:
                            break
                        m = match_tileset(snap.vram, char_base, bpp, tiles,
                                          blocks, tile_index, rom)
                        if not m:
                            break
                        need = args.min_cells
                        if m["cov"] < need or (m.get("votes", 0) < 1
                                               and m["comp"] != "raw"):
                            break
                        data = m["data"]
                        group, other = [], []
                        for c in remaining:
                            off = m["offset"] + c["tile"] * stride
                            if data[off:off + stride] == tile_bytes(
                                    snap.vram, char_base, c["tile"], stride):
                                group.append(c)
                            else:
                                other.append(c)
                        if len(group) < args.min_cells:
                            break

                        palbanks = sorted({c["palbank"] for c in group})
                        pal = find_palette(snap, palbanks, blocks, rom)
                        if not pal:
                            remaining = other
                            continue
                        if layer_img is None:
                            layer_img, _mask = bg_text_layer(snap, bg)
                        box = bbox(group)
                        crop = layer_img[box[1]:box[1] + box[3],
                                         box[0]:box[0] + box[2]]
                        if crop.size == 0:
                            remaining = other
                            continue

                        entry = {
                            "scene": name, "frame": f"{run.name}/{n}", "bg": bg,
                            "bpp": bpp, "replay": round(ratio, 4),
                            "tileset": {
                                "address": f"0x{m['addr']:08X}",
                                "compression": m["comp"], "offset": m["offset"],
                                "coverage": round(m["cov"] / m["n"], 3),
                                "tiles": m["n"],
                            },
                            "palette": pal, "crop": box,
                            "cell_count": len(group),
                            "cells": [[c["col"], c["row"], c["entry"]]
                                      for c in group],
                            "unmatched_cells": len(other),
                        }
                        key = (name, bg, m["addr"], m["offset"], bpp,
                               pal["address"], pal["offset"])
                        old = next((c for c in catalog
                                    if c.get("_key") == key), None)
                        if old is not None:
                            # 同一图块集在不同帧上重合时，留「重放率更高」的那帧：
                            # 户外帧因卷动对不上（0.2x），室内/界面帧能到 0.9+
                            if (entry["replay"], len(group)) > (old.get("replay", -1.0),
                                                               old["cell_count"]):
                                Image.fromarray(crop).save(ROOT / old["png"])
                                keep = old["png"]
                                old.update(entry)
                                old["png"] = keep
                            old["frames"] = old.get("frames", 1) + 1
                        else:
                            d = out_root / name
                            d.mkdir(parents=True, exist_ok=True)
                            png_path = d / (f"bg{bg}_{m['addr']:08X}_"
                                            f"{m['offset']:03X}.png")
                            Image.fromarray(crop).save(png_path)
                            entry["png"] = str(png_path.relative_to(ROOT))
                            entry["_key"] = key
                            catalog.append(entry)
                            per_scene += 1
                        remaining = other
        if per_scene:
            print(f"  {name}: {per_scene} 个图块集", flush=True)

    for e in catalog:
        e.pop("_key", None)
    (out_root / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    # 按图块集汇总
    by_ts = defaultdict(list)
    for e in catalog:
        by_ts[(e["tileset"]["address"], e["tileset"]["offset"], e["bpp"])].append(e)
    lines = ["# 场景图块集汇总", "",
             f"- 场景扫描：{len(names)}", f"- 条目：{len(catalog)}",
             f"- 唯一图块集：{len(by_ts)}", ""]
    for (addr, off, bpp), items in sorted(by_ts.items(), key=lambda kv: -len(kv[1])):
        scenes = sorted({i["scene"] for i in items})
        lines.append(f"## {addr} +{off} ({bpp}bpp) — {len(scenes)} 场景 / "
                     f"{sum(i['cell_count'] for i in items)} 格")
        lines.append("")
        lines.append("场景：" + ", ".join(scenes[:12]) +
                     (f" …+{len(scenes)-12}" if len(scenes) > 12 else ""))
        lines.append("")
    # 按场景倒排，方便直接看「这个场景抓到了什么」
    lines += ["## 按场景", ""]
    by_scene = defaultdict(list)
    for e in catalog:
        by_scene[e["scene"]].append(e)
    for scene in sorted(by_scene):
        parts = [f"{e['tileset']['address']}+{e['tileset']['offset']:X}"
                 f"(BG{e['bg']},{e['cell_count']}格,rp{e['replay']:.2f})"
                 for e in sorted(by_scene[scene], key=lambda e: -e["cell_count"])]
        lines.append(f"- **{scene}**：" + " / ".join(parts))
    (out_root / "report.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"\n完成：{len(catalog)} 条目 / {len(by_ts)} 个唯一图块集")
    if skipped_frames:
        top = sorted(skipped_frames.items(), key=lambda kv: -kv[1])[:10]
        print("重放不达标而跳过的帧（前10场景）: " +
              ", ".join(f"{k}={v}" for k, v in top))
    print(f"输出 → {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
