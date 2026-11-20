#!/usr/bin/env python3
"""harvest_obj_assets.py — 抓 OBJ（精灵）层里的预渲染日文

BG 扫描器（harvest_all_scene_assets.py）只能看到 BG 层。
图鉴左半的「みつけたかず / つかまえたかず / START メニュー」、
领航员的「メインメニュー / ポケモンずかん / コンディション …」
都是 **OBJ 精灵**，tile 来自 OAM + VRAM 的 OBJ 区（0x10000），
BG 扫描器永远不会看到它们，所以单独做一套。

每帧：解析 OAM → 每个 sprite 的 8×8 子 tile 号 →
用和 BG 同一套「逐 tile 投票」在 ROM 的 LZ77 块里找图块集 →
对上的 sprite 记成 cells（格子坐标 + 块内 tile 号 + palbank）。

用法：
    C:/Python314/python.exe scripts/misc/harvest_obj_assets.py \
        --scenes dex_area,navigator --frames 0 -o work/obj_assets
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np                                   # noqa: E402
from PIL import Image                                # noqa: E402

from util.gba_ppu import Snapshot, _obj_dim, parse_oam, render  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts" / "misc"))
import harvest_all_scene_assets as H                  # noqa: E402

OBJ_CHAR_BASE = 0x10000
VIS_W, VIS_H = 240, 160


def obj_layer_img(snap) -> np.ndarray:
    """把所有可见 OBJ 合成到一张 256×160 RGBA，作为对照图。

    比屏幕宽 16px：精灵图块集常按 32/64 宽切块，最右一列会跨出屏幕，
    但那部分内容仍属于这张图，所以对照图也留出来。
    """
    arr = np.zeros((VIS_H, VIS_W + 16, 4), np.uint8)
    for ob in parse_oam(snap):
        spr, mask = ob.rgb, ob.mask
        h, w = spr.shape[:2]
        y, x = ob.y, ob.x
        ys, xs = max(0, y), max(0, x)
        ye, xe = min(VIS_H, y + h), min(VIS_W + 16, x + w)
        if ye <= ys or xe <= xs:
            continue
        arr[ys:ye, xs:xe, :3] = spr[ys - y:ye - y, xs - x:xe - x]
        arr[ys:ye, xs:xe, 3] = np.where(mask[ys - y:ye - y, xs - x:xe - x], 0, 255)
    return arr


def sprite_tiles(snap, ob):
    """列出一个 sprite 用到的 (tx, ty, tile_no)。1D 映射，步长恒为 1。"""
    wt, ht = ob.w // 8, ob.h // 8
    out = []
    t = ob.tile_no
    for ty in range(ht):
        for tx in range(wt):
            out.append((tx, ty, t))
            t += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="all")
    ap.add_argument("--frames", type=int, default=0, help="0=全部帧")
    ap.add_argument("--min-cells", type=int, default=6)
    ap.add_argument("-o", default=str(ROOT / "work" / "obj_assets"))
    args = ap.parse_args()

    rom = H.ROM_PATH.read_bytes()
    print(f"ROM {len(rom)}B；建块缓存…", flush=True)
    blocks = H.build_blocks(rom)
    print(f"  {len(blocks)} 块；建 tile 索引…", flush=True)
    index = H.build_tile_index(blocks)
    # 块地址 → (压缩方式, 解压数据, 第一个全空槽位)：定源时直接按字节在块里
    # 核对/定位，不依赖 index（index 每种 tile 只留 6 个候选、且跳过全空
    # tile，空白格会被漏掉，条带就会缺一块）
    ZERO32 = b"\x00" * 32
    bdata = {}
    for addr, comp, data in blocks:
        z = next((i for i in range(len(data) // 32)
                  if data[i * 32:(i + 1) * 32] == ZERO32), -1)
        bdata[addr] = (comp, data, z)

    if args.scenes == "all":
        names = sorted(d.name for d in H.BOT_ROOT.iterdir()
                       if d.is_dir() and not d.name.startswith("_")
                       and d.name != "images_dump")
    else:
        names = [s.strip() for s in args.scenes.split(",") if s.strip()]

    out_root = Path(args.o).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    catalog = []
    seen: dict[str, set] = defaultdict(set)
    per_scene = defaultdict(int)

    for name in names:
        scene_dir = H.BOT_ROOT / name
        if not scene_dir.is_dir():
            continue
        # 同一场景可能有好几轮回放，不同轮的界面状态（读数/滚动位置）不一样，
        # 混在一起会拼出对不上的条带；只扫「帧最多」的那一轮。
        runs = []
        for run in sorted([d for d in scene_dir.iterdir() if d.is_dir()]):
            side = run / "origin"
            if not side.is_dir():
                continue
            n_frames = len([p for p in side.glob("*.vram.bin")
                            if p.name.split(".")[0].isdigit()])
            if n_frames:
                runs.append((n_frames, run))
        if not runs:
            continue
        for run in [r for _c, r in sorted(runs, reverse=True)]:
            side = run / "origin"
            frames = sorted({p.name.split(".")[0] for p in side.glob("*.vram.bin")
                             if p.name.split(".")[0].isdigit()})
            if args.frames and len(frames) > args.frames:
                step = max(1, len(frames) // args.frames)
                frames = frames[::step][:args.frames]
            for n in frames:
                try:
                    snap = Snapshot.load(side, n)
                except Exception:
                    continue
                if snap.mode != 0 or not snap.obj_on:
                    continue
                sprites = parse_oam(snap)
                if not sprites:
                    continue
                fp = hashlib.md5(bytes(snap.vram) + bytes(snap.oam)).hexdigest()
                if fp in seen[name]:
                    continue
                seen[name].add(fp)

                img = obj_layer_img(snap)
                # 每个 sprite 先粗筛：至少一半 8×8 在 ROM 图块里出现过。
                # 真正定源放到「逐格」阶段 —— 一个精灵的 8 个 tile 可能横跨
                # 两张图块集（领航员菜单行最右那格就是这样），所以不能整
                # 只精灵只认一个块。
                cand_sprites = []
                for ob in sprites:
                    if ob.bpp8:
                        continue                      # 8bpp sprite 先不处理
                    if ob.x < -8 or ob.y < -8 or ob.x >= VIS_W or ob.y >= VIS_H:
                        continue
                    tiles = [t for _tx, _ty, t in sprite_tiles(snap, ob)]
                    if len(tiles) < 2:
                        continue
                    hit = sum(1 for t in tiles
                              if H.tile_bytes(snap.vram, OBJ_CHAR_BASE, t, 32)
                              in index)
                    if hit * 2 < len(tiles):
                        continue
                    # 整只精灵的主块：一条菜单行由几只精灵拼成时，靠它判断
                    # 哪些精灵属于同一条（不同块的不许并到一起）
                    m = H.match_tileset(snap.vram, OBJ_CHAR_BASE, 4, tiles,
                                        blocks, index, rom)
                    cand_sprites.append((ob, m["addr"] if m else 0))
                if not cand_sprites:
                    continue

                # ── 按「一条」切：同一 y 带、x 相邻、同一主块的精灵归成一条 ──
                # 领航员每行菜单是 4 个 32×16 精灵拼的，用户要的是
                # 「文字条单独一张图」，所以按行拆，而不是整块面板一张
                ordered = sorted(cand_sprites, key=lambda p: (p[0].y, p[0].x))
                strips, cur = [], []
                for ob, pa in ordered:
                    if not cur:
                        cur = [(ob, pa)]
                        continue
                    py = cur[0][0].y
                    xmax = max(o.x + o.w for o, _a in cur)
                    if (abs(ob.y - py) <= 8 and ob.x <= xmax + 40
                            and pa == cur[0][1]):
                        cur.append((ob, pa))
                    else:
                        strips.append(cur)
                        cur = [(ob, pa)]
                if cur:
                    strips.append(cur)

                for strip in strips:
                    # 先给每只精灵算一个「主块」（整只精灵一致的那个图块集），
                    # 再逐格定源：主块优先，主块字节对不上的格才退回次块。
                    # 这样不会因为某格 tile 在好几块里字节相同就跑偏到
                    # 共享面板块上（那样翻译会改到别的界面）。
                    prim: dict[int, tuple[int, str, int]] = {}
                    for ob, _pa in strip:
                        tiles = [t for _tx, _ty, t in sprite_tiles(snap, ob)]
                        m = H.match_tileset(snap.vram, OBJ_CHAR_BASE, 4, tiles,
                                            blocks, index, rom)
                        if m:
                            prim[id(ob)] = (m["addr"], m["comp"], m["offset"])

                    raw_cells = []
                    for ob, _pa in strip:
                        for tx, ty, t in sprite_tiles(snap, ob):
                            sx, sy = ob.x + tx * 8, ob.y + ty * 8
                            # 只记在屏幕附近的 8×8；右侧允许略微越界（精灵
                            # 图块集常按 32/64 宽切块，最右一格会跨出屏幕，
                            # 但那部分内容仍属于这张图，翻译时不能丢）
                            if (sx < 0 or sy < 0
                                    or sx >= VIS_W + 16 or sy >= VIS_H):
                                continue
                            b = H.tile_bytes(snap.vram, OBJ_CHAR_BASE, t, 32)
                            cand = sorted(index.get(b, []),
                                          key=lambda c: (c[2], c[0]))
                            raw_cells.append((sx, sy, t, ob.palbank,
                                              cand, prim.get(id(ob))))

                    votes: dict[tuple, int] = defaultdict(int)
                    for *_f, cand, p in raw_cells:
                        for addr, comp, slot in cand:
                            votes[(addr, comp)] += 1
                        if p:
                            votes[(p[0], p[1])] += 100

                    srcs: list[tuple[int, str]] = []
                    cells, seen_tiles, metas = [], [], []
                    for sx, sy, t, palbank, cand, p in raw_cells:
                        b = H.tile_bytes(snap.vram, OBJ_CHAR_BASE, t, 32)
                        if p:
                            # 主块定源：先按 base 推出的槽位核对字节，对不上就
                            # 在块里找同字节的其他槽位（块内重复 tile、全空
                            # 占位格都很常见），再不行才考虑「全 ROM 唯一」
                            # 的跨块回落
                            addr_p, comp_p, base_p = p
                            data_p, zslot = bdata[addr_p][1], bdata[addr_p][2]
                            if b == ZERO32 and zslot >= 0:
                                pick = (addr_p, comp_p, zslot)
                            else:
                                np_tiles = len(data_p) // 32
                                want = (t + base_p // 32
                                        if base_p % 32 == 0 else -1)
                                if 0 <= want < np_tiles and \
                                        data_p[want * 32:(want + 1) * 32] == b:
                                    pick = (addr_p, comp_p, want)
                                else:
                                    slots = ([s for s in range(np_tiles)
                                              if data_p[s * 32:(s + 1) * 32] == b]
                                             if np_tiles <= 256 else [])
                                    if slots:
                                        pick = (addr_p, comp_p,
                                                min(slots,
                                                    key=lambda s: abs(s - want)))
                                    elif len(cand) == 1:
                                        # 多块同字节 = 共享面板块，写进去会改
                                        # 到别的界面，只有全 ROM 唯一才允许跨块
                                        pick = cand[0]
                                    else:
                                        continue
                        elif cand:
                            pick = max(cand, key=lambda c: (votes[(c[0], c[1])],
                                                            -abs(c[2] - t)))
                        else:
                            continue
                        addr, comp, slot = pick
                        si = next((i for i, s in enumerate(srcs)
                                   if s[0] == addr), None)
                        if si is None:
                            srcs.append((addr, comp))
                            si = len(srcs) - 1
                        entry = slot | (palbank << 12)
                        cells.append([sx // 8, sy // 8, entry, si])
                        seen_tiles.append((sx, sy, t))

                    if len(cells) < args.min_cells:
                        continue
                    for ob, _pa in strip:
                        metas.append({"x": ob.x, "y": ob.y, "w": ob.w,
                                      "h": ob.h, "tile_no": ob.tile_no,
                                      "palbank": ob.palbank})
                    palbanks = sorted({m["palbank"] for m in metas})
                    pal = H.find_palette(snap, palbanks, blocks, rom, bank_base=512)
                    if not pal:
                        continue
                    cols = [c[0] for c in cells]
                    rows = [c[1] for c in cells]
                    phx = min(t[0] % 8 for t in seen_tiles)
                    phy = min(t[1] % 8 for t in seen_tiles)
                    box = [min(cols) * 8 + phx, min(rows) * 8 + phy,
                           (max(cols) - min(cols) + 1) * 8,
                           (max(rows) - min(rows) + 1) * 8]
                    crop = img[box[1]:box[1] + box[3], box[0]:box[0] + box[2]]
                    if crop.size == 0:
                        continue
                    addr0, comp0 = srcs[0]
                    hit = sum(votes[(a, c)] for a, c in srcs)
                    entry = {
                        "scene": name, "frame": f"{run.name}/{n}", "layer": "obj",
                        "bpp": 4,
                        "tileset": {"address": f"0x{addr0:08X}",
                                    "compression": comp0, "offset": 0,
                                    "coverage": round(min(1.0, hit / len(cells)), 3)},
                        "sources": [{"address": f"0x{a:08X}", "compression": c}
                                    for a, c in srcs],
                        "palette": pal, "crop": box, "phase": [phx, phy],
                        "cell_count": len(cells), "cells": cells,
                        "sprites": metas,
                    }
                    # 同一条在不同帧上会被切得长短不一，按「首块 + 行 + 调色板」
                    # 去重，留格数最多的那次
                    key = (name, addr0, box[1], box[3],
                           pal["address"], pal["offset"], len(srcs))
                    old = next((c for c in catalog if c.get("_key") == key), None)
                    if old is not None:
                        if len(cells) > old["cell_count"]:
                            Image.fromarray(crop).save(ROOT / old["png"])
                            keep = old["png"]
                            old.update(entry)
                            old["png"] = keep
                        old["frames"] = old.get("frames", 1) + 1
                        continue
                    d = out_root / name
                    d.mkdir(parents=True, exist_ok=True)
                    png = d / f"obj_{addr0:08X}_{box[1]:03d}.png"
                    Image.fromarray(crop).save(png)
                    entry["png"] = str(png.relative_to(ROOT))
                    entry["_key"] = key
                    catalog.append(entry)
                    per_scene[name] += 1
            # 这一轮已经抓出东西就别再混下一轮（不同轮回放状态不一致，
            # 混起来会拼出对不上的条带）
            if per_scene[name]:
                break

        if per_scene[name]:
            print(f"  {name}: {per_scene[name]} 个 OBJ 图块集", flush=True)

    for e in catalog:
        e.pop("_key", None)
    (out_root / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    by_ts = defaultdict(list)
    for e in catalog:
        by_ts[(e["tileset"]["address"], e["tileset"]["offset"])].append(e)
    lines = ["# OBJ 层图块集汇总", "",
             f"- 扫描场景：{len(names)}", f"- 条目：{len(catalog)}",
             f"- 唯一图块集：{len(by_ts)}", ""]
    for (addr, off), items in sorted(by_ts.items(), key=lambda kv: -len(kv[1])):
        scenes = sorted({i["scene"] for i in items})
        lines.append(f"## {addr} +{off:X} — {len(scenes)} 场景 / "
                     f"{sum(i['cell_count'] for i in items)} 格")
        lines.append("")
        lines.append("场景：" + ", ".join(scenes[:14]) +
                     (f" …+{len(scenes)-14}" if len(scenes) > 14 else ""))
        lines.append("")
    (out_root / "report.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"\n完成：{len(catalog)} 条目 / {len(by_ts)} 个唯一 OBJ 图块集")
    print(f"输出 → {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
