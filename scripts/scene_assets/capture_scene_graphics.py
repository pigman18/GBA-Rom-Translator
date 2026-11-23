#!/usr/bin/env python3
"""scene_capture.py — 从 bot 运行时快照里「抓」出某个场景的图形资产

定位逻辑（每一步都用真实硬件状态，不靠猜）：
  1. bot 快照 = 该帧的 VRAM(96K)/CGRAM(1K)/OAM/IO
  2. 给定屏幕矩形 → 逐 BG 层算覆盖率，挑出承载该区域的层
  3. 该层 tilemap → 取区域内的 tile 号 → 从 VRAM 切 tile 字节
  4. tile 字节在 ROM 的 LZ77 解压块里做子串搜索 ⇒ 得到 ROM 地址 + 压缩方式
  5. CGRAM 里该层用到的 palbank → 在 ROM 里搜 32B 原色 ⇒ 调色板地址
  6. tilemap 窗口本身也在 ROM 里搜（raw / LZ77）⇒ 拼合用的 map 地址

输出：
  <name>_frame.png    整帧（重放，对照用）
  <name>_layer.png    该 BG 层（透明底）
  <name>_crop.png     目标矩形
  <name>.json         资源定位报告 + 可直接落 yaml 的 preset 建议

用法：
  python src/util/scene_capture.py --run <run>/origin --frame 003 \
      --rect 8,76,112,100 --name bag_pocket_label -o work/scene_capture
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np                                          # noqa: E402
from PIL import Image                                       # noqa: E402

from util.gba_ppu import (Snapshot, bg_text_layer, parse_oam,  # noqa: E402
                          render, compare, cgram_to_rgb)
from util.tiles_patcher import lz77_decompress                # noqa: E402

DEFAULT_ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BPP = 4


def tile_bytes(snap: Snapshot, base: int, tile_no: int, bpp: int) -> bytes:
    stride = 64 if bpp == 8 else 32
    off = base + tile_no * stride
    return bytes(snap.vram[off:off + stride])


def map_entries(snap: Snapshot, bg: int, x0: int, y0: int, x1: int, y1: int):
    cnt = snap.bgcnt(bg)
    char_base = ((cnt >> 2) & 3) * 0x4000
    screen_base = ((cnt >> 8) & 0x1F) * 0x800
    words = np.frombuffer(snap.vram, dtype="<u2", count=len(snap.vram) // 2)
    out = []
    for my in range(y0 // 8, (y1 + 7) // 8):
        for mx in range(x0 // 8, (x1 + 7) // 8):
            e = int(words[(screen_base + my * 64 + mx * 2) // 2])
            out.append({"mx": mx, "my": my, "entry": e,
                        "tile": e & 0x3FF, "palbank": (e >> 12) & 0xF})
    return char_base, screen_base, out


def rom_lz_index(rom: bytes):
    """ROM 里所有能成功解压的 LZ77 块 → [(gba_addr, comp)]。"""
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
                out.append((0x08000000 + off, "lz77_swap" if swap else "lz77"))
                break
    return out


def find_in_rom(rom: bytes, index, blob: bytes):
    """raw + 所有 LZ 块里搜 blob，返回 [(addr, offset, comp, block_len)]。"""
    hits = []
    i = rom.find(blob)
    while i >= 0:
        hits.append((0x08000000 + i, 0, "none", len(blob)))
        i = rom.find(blob, i + 1)
    for addr, comp in index:
        off = addr - 0x08000000
        try:
            d = lz77_decompress(rom[off:], swap=(comp == "lz77_swap"))
        except Exception:
            continue
        j = d.find(blob)
        if j >= 0:
            hits.append((addr, j, comp, len(d)))
    return hits


def layer_for_rect(snap: Snapshot, rect):
    x0, y0, x1, y1 = rect
    best = None
    for bg in range(4):
        if not snap.bg_on(bg):
            continue
        _img, mask = bg_text_layer(snap, bg)
        cover = int((~mask[y0:y1, x0:x1]).sum())
        total = (x1 - x0) * (y1 - y0)
        ratio = cover / total
        if best is None or ratio > best[0]:
            best = (ratio, bg)
    return None if best is None else best[1]


def find_map_block(rom: bytes, index, mblob: bytes, msize: int):
    """在 ROM 里找 BG tilemap 的来源块。

    精确命中优先；但**运行时 map 会被游戏改写**（口袋名等字形格），
    整段必然搜不到 —— 于是退化为「长度匹配 + ≥90% 格子相同」的模糊命中。
    返回 (addr, comp, rom_map_bytes) 或 None。
    """
    for cut in (msize, msize // 2, 0x400, 0x200):
        hits = [h for h in find_in_rom(rom, index, mblob[:cut]) if h[2] != "none"]
        if hits:
            a, off, comp, _n = hits[0]
            try:
                d = lz77_decompress(rom[a - 0x08000000:], swap=(comp == "lz77_swap"))
            except Exception:
                continue
            return a, comp, d[off:off + msize]

    import struct as _struct
    n = msize // 2
    ents = _struct.unpack(f"<{n}H", mblob)
    best = None
    for a, comp in index:
        try:
            d = lz77_decompress(rom[a - 0x08000000:], swap=(comp == "lz77_swap"))
        except Exception:
            continue
        if len(d) < msize:
            continue
        de = _struct.unpack(f"<{n}H", d[:msize])
        same = sum(1 for i in range(n) if ents[i] == de[i])
        if same >= n * 0.9 and (best is None or same > best[3]):
            best = (a, comp, d[:msize], same)
    return None if best is None else best[:3]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="bot 侧的 origin/translated 目录")
    ap.add_argument("--frame", default="003")
    ap.add_argument("--rect", required=True, help="x0,y0,x1,y1")
    ap.add_argument("--name", default="crop")
    ap.add_argument("--bg", type=int, default=None, help="强制指定层")
    ap.add_argument("--rom", default=str(DEFAULT_ROM))
    ap.add_argument("-o", default=str(ROOT / "work" / "scene_capture"))
    args = ap.parse_args()

    run = Path(args.run)
    out = Path(args.o) / args.name
    out.mkdir(parents=True, exist_ok=True)
    rect = tuple(int(v) for v in args.rect.split(","))
    x0, y0, x1, y1 = rect

    snap = Snapshot.load(run, args.frame)
    rom = Path(args.rom).read_bytes()

    frame_img = render(snap)
    Image.fromarray(frame_img).save(out / f"{args.name}_frame.png")

    bg = args.bg if args.bg is not None else layer_for_rect(snap, rect)
    report: dict = {"frame": args.frame, "rect": list(rect), "bg": bg}

    if bg is not None:
        img, mask = bg_text_layer(snap, bg)
        rgba = np.dstack([img, np.where(mask, 0, 255).astype(np.uint8)])
        Image.fromarray(rgba, "RGBA").save(out / f"{args.name}_layer.png")
        Image.fromarray(rgba[y0:y1, x0:x1], "RGBA").save(out / f"{args.name}_crop.png")

        cnt = snap.bgcnt(bg)
        bpp = 8 if (cnt & 0x80) else 4
        char_base, screen_base, entries = map_entries(snap, bg, x0, y0, x1, y1)
        tiles = sorted({e["tile"] for e in entries})
        palbanks = sorted({e["palbank"] for e in entries})
        report.update({
            "bpp": bpp, "char_base": f"0x{char_base:04X}",
            "screen_base": f"0x{screen_base:04X}",
            "tiles": tiles, "palbanks": palbanks,
        })
        print(f"BG{bg} 承载该区域：{bpp}bpp char=0x{char_base:04X} "
              f"screen=0x{screen_base:04X} tiles={tiles[0]}..{tiles[-1]} "
              f"({len(tiles)}个) palbanks={palbanks}")

        # ── tile 块反查 ──
        stride = 64 if bpp == 8 else 32
        lo, hi = tiles[0], tiles[-1]
        probe = bytes(snap.vram[char_base + lo * stride:
                                char_base + (hi + 1) * stride])
        print("建 ROM LZ 索引…")
        index = rom_lz_index(rom)
        print(f"  {len(index)} 个解压块")
        hits = find_in_rom(rom, index, probe)
        print(f"  tile 切片命中 {len(hits)}:")
        for a, o, c, n in hits[:6]:
            tile_addr = a + o - lo * stride
            print(f"    块 0x{a:08X} comp={c} len={n} → tile{lo}@0x{tile_addr:08X}")
        if hits:
            a, o, c, n = hits[0]
            block_addr = a + o - lo * stride
            report.update({"rom_address": f"0x{block_addr:08X}",
                           "compression": c, "raw_size": n})
            # 整块是否与 VRAM 完全一致（block 起点 = char_base + 0）
            blkw = min(n, len(snap.vram) - char_base)
            report["vram_matches_block"] = bool(
                bytes(snap.vram[char_base:char_base + blkw]) ==
                lz77_decompress(rom[a - 0x08000000:], swap=(c == "lz77_swap"))[:blkw]
            )

        # ── 调色板反查（区域用到的每个 palbank）──
        pals = {}
        pal_hits: dict[int, list] = {}
        for b in palbanks:
            pb = bytes(snap.pal[b * 32:(b + 1) * 32])
            ph = find_in_rom(rom, index, pb)
            raw = [h for h in ph if h[2] == "none"]
            pal_hits[b] = ph          # 保留 LZ 命中，供「多 bank 同块」判定
            pals[b] = [f"0x{h[0]:08X}" for h in (raw or ph)][:4]
            print(f"  palbank {b}: ROM 候选 {pals[b]}")
        report["palettes"] = pals
        if 0 in pals and pals[0]:
            report["palette"] = pals[0][0]

        # 同一 LZ 块里连续排着多个 bank 的情况（如 0x087F2770 解压 64B = bank0+bank1）
        if len(pal_hits) > 1:
            def key(h):
                return (h[0], h[2])
            cand = {key(h): [] for h in sum(pal_hits.values(), [])}
            for b, hs in pal_hits.items():
                for h in hs:
                    if key(h) in cand:
                        cand[key(h)].append((b, h[1]))
            for (addr, comp), items in cand.items():
                items.sort(key=lambda t: t[1])
                banks = [b for b, _o in items]
                offs = [o for _b, o in items]
                if banks == sorted(palbanks) and all(
                        offs[i + 1] - offs[i] == 32 for i in range(len(offs) - 1)):
                    report["palette"] = f"0x{addr:08X}"
                    report["palette_compression"] = comp
                    report["palette_size"] = 32 * (max(banks) + 1)
                    print(f"  多 bank 同块: 0x{addr:08X} ({comp}, "
                          f"{report['palette_size']}B = bank{min(banks)}..{max(banks)})")
                    break

        # ── tilemap 反查 ──
        # BG 文本层地图大小：256x256=2KB / 512x256 或 256x512=4KB / 512x512=8KB
        size_code = (cnt >> 14) & 3
        msize = {0: 0x800, 1: 0x1000, 2: 0x1000, 3: 0x2000}[size_code]
        mblob = bytes(snap.vram[screen_base:screen_base + msize])
        mb = find_map_block(rom, index, mblob, msize)
        if mb:
            a, comp_, rom_map = mb
            report["tilemap_address"] = f"0x{a:08X}"
            report["tilemap_compression"] = comp_
            report["tilemap_size"] = msize
            print(f"  tilemap({msize}B) ← 0x{a:08X} ({comp_})")

            # 运行时 vs ROM 的 map 差异 —— 游戏常把「口袋名」等字形格运行时写上
            import struct as _struct
            rt_es = list(_struct.unpack(f"<{msize // 2}H", mblob))
            rom_es = list(_struct.unpack(
                f"<{min(len(rom_map), msize) // 2}H", rom_map[:msize]))
            overrides = []
            for i in range(min(len(rt_es), len(rom_es))):
                if rt_es[i] != rom_es[i]:
                    overrides.append([i % 32, i // 32, rt_es[i]])
            report["tilemap_overrides"] = overrides
            print(f"  map 运行时改写 {len(overrides)} 格")
        else:
            print(f"  tilemap({msize}B) 未在 ROM 找到")

    # OAM 精灵（区域内的）
    objs = []
    for o in parse_oam(snap):
        if o.x < x1 and o.x + o.w > x0 and o.y < y1 and o.y + o.h > y0:
            objs.append({"index": o.index, "x": o.x, "y": o.y,
                         "w": o.w, "h": o.h, "bpp8": o.bpp8,
                         "tile": o.tile_no, "palbank": o.palbank})
    report["objs"] = objs
    if objs:
        print(f"区域内的 OBJ: {json.dumps(objs, ensure_ascii=False)}")

    png = run / f"{args.frame}.png"
    if png.is_file():
        cmp = compare(frame_img, png)
        report["replay_match"] = round(cmp.get("ratio", 0), 4)
        print(f"重放 vs 截图: {cmp.get('ratio', 0):.2%}")

    # preset 建议
    if report.get("rom_address"):
        preset = {
            "id": args.name,
            "label": args.name,
            "default": False,
            "address": report["rom_address"],
            "format": f"{report.get('bpp', 4)}bpp",
            "compression": report.get("compression", "lz77_swap"),
            "palette": report.get("palette"),
        }
        if report.get("tilemap_address"):
            preset["compose"] = {
                "type": "bgmap",
                "tilemap_address": report["tilemap_address"],
                "tilemap_compression": report.get("tilemap_compression", "lz77_swap"),
                "tilemap_size": report.get("tilemap_size", 0x800),
                "width": 32, "height": 32,
                "crop": [x0, y0, x1 - x0, y1 - y0],
            }
            if report.get("tilemap_overrides"):
                preset["compose"]["tilemap_overrides"] = report["tilemap_overrides"]
        if report.get("palette_size"):
            preset["palette_size"] = report["palette_size"]
        elif report.get("palettes"):
            preset["palette_banks"] = {str(b): addrs[0]
                                       for b, addrs in report["palettes"].items()
                                       if addrs}
        report["preset"] = preset
        print("\npreset 建议:")
        print(json.dumps(preset, ensure_ascii=False, indent=2))

    (out / f"{args.name}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n输出 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
