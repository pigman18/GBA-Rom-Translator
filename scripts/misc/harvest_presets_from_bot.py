#!/usr/bin/env python3
"""scripts/misc/harvest_presets_from_bot.py — 用 bot 快照「抓内存 + 匹配」出 yaml 配置

## 背景

`src/util/configs/POKEMON_RUBY_AXVJ00.yaml` 的 `tiles.presets` 原本是人工
用模拟器抓内存、比对出来的。本脚本把那个过程自动化：bot 每帧已经存了
`{vram,pal,oam,io}.bin`，等价于「抓到的那块内存」。

## 三条取证链（每条都必须通过像素验证才写进 yaml）

### A. OBJ 精灵（OAM 直给，最可靠）

    OAM → tile 号 / palbank / 尺寸
        → VRAM OBJ 区取 tile 原始字节
        → 在 ROM 全部 LZ77 解压块里搜 ⇒ address
        → palbank 取 CGRAM 那 16 色 ⇒ 在 ROM 里搜 ⇒ palette
        → 按 OAM 拼 sprite，与截图同位置逐像素比对

  实测（title_menu 001）：7 个 OBJ 中 6 个 100% 像素一致。
  这条链能确定 sprite_size（OAM 权威尺寸）和 bank_list（每个 sprite 的 palbank）。

### B. BG 图块集（含日文 UI 图的主力）

    BGxCNT → charBase / bpp
        → 该 charBlock 里每个 8x8 tile 的原始字节
        → 逐个在 ROM 解压块里搜 ⇒ address
        → 同一 ROM 块被 ≥N 个 tile 命中 ⇒ 认定为一个 tileset
        → 调色板：16 个 BG bank 逐个试，用「该 tile 能否在截图里
          逐像素找到」打分 ⇒ 命中最多的 bank 为准

  ⚠ BG 层的 BGxHOFS/VOFS（卷动）是**只写寄存器**，读回来是 open bus。
    所以**不能**整层渲染比对；这里用「单 tile 全屏搜索」，
    与卷动无关，是可靠的。（实测整层渲染一致率 0.14% 正是卷动未知导致，
    不是数据错。）

### C. 输出

    只输出同时满足「address 定位成功」+「调色板在 ROM 里定位成功」+
    「至少一个 sprite/tile 在截图上像素级命中」的配置。
    任何一条不满足就跳过并在报告里写明原因 —— 不猜、不编。

## 用法

    # 只诊断（打印候选，不改文件）
    C:/Python314/python.exe scripts/misc/harvest_presets_from_bot.py

    # 通过了验证的配置追加进 yaml（先备份）
    C:/Python314/python.exe scripts/misc/harvest_presets_from_bot.py --write
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "util"))

import numpy as np                                    # noqa: E402
from PIL import Image                                 # noqa: E402

from tiles_patcher import lz77_decompress             # noqa: E402
from util.gba_ppu import Snapshot, parse_oam          # noqa: E402

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
YAML_PATH = ROOT / "src" / "util" / "configs" / "POKEMON_RUBY_AXVJ00.yaml"
BOT_ROOT = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"
OBJ_VRAM = 0x10000


# ─────────────────────────────────────────────────────────────
# ROM 索引
# ─────────────────────────────────────────────────────────────

def build_rom_index(rom: bytes):
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


_BLOCK_CACHE: dict[bytes, tuple | None] = {}


def rom_block_of(index, tile_bytes: bytes):
    """返回第一个包含该 tile 的 (addr, offset, comp)。

    带缓存：同一 tile 内容在一帧里会被反复查（不同 BG 层 / 不同 sprite），
    而每次都要遍历 ~3000 个解压块 —— 实测这是主要瓶颈（1 帧 2 分钟）。
    """
    key = tile_bytes
    if key in _BLOCK_CACHE:
        return _BLOCK_CACHE[key]
    hit = None
    for addr, data, comp in index:
        i = data.find(tile_bytes)
        if i >= 0:
            hit = (addr, i, comp)
            break
    _BLOCK_CACHE[key] = hit
    return hit


# ─────────────────────────────────────────────────────────────
# CGRAM
# ─────────────────────────────────────────────────────────────

def cgram_colors(pal: bytes, first: int, n: int = 16) -> np.ndarray:
    """CGRAM → RGB888（mGBA 的 5→8 扩展是 (v<<3)|(v>>2)）。"""
    out = np.zeros((n, 3), dtype=np.uint8)
    for i in range(n):
        v = struct.unpack_from("<H", pal, (first + i) * 2)[0]
        r, g, b = v & 0x1F, (v >> 5) & 0x1F, (v >> 10) & 0x1F
        out[i] = ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))
    return out


def cgram_raw(pal: bytes, first: int, n: int = 16) -> bytes:
    return pal[first * 2:(first + n) * 2]


def find_palette_in_rom(rom: bytes, raw: bytes):
    """在 ROM 里搜这段调色板字节，返回 GBA 地址列表（4 字节对齐优先）。"""
    out, i = [], rom.find(raw)
    while i >= 0:
        out.append(0x08000000 + i)
        i = rom.find(raw, i + 1)
    out.sort(key=lambda a: ((a - 0x08000000) % 4 != 0, a))
    return out


# ─────────────────────────────────────────────────────────────
# 渲染 / 验证
# ─────────────────────────────────────────────────────────────

def decode_4bpp(t: bytes) -> np.ndarray:
    a = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = t[y * 4 + x // 2]
            a[y, x] = (b & 0xF) if x % 2 == 0 else (b >> 4) & 0xF
    return a


def decode_8bpp(t: bytes) -> np.ndarray:
    return np.frombuffer(t, dtype=np.uint8, count=64).reshape(8, 8).copy()


def tile_in_shot(shot: np.ndarray, tile_rgb: np.ndarray, tol: int = 0) -> bool:
    """这个 8x8 图像是否**逐像素**出现在截图里（全屏搜索，与卷动无关）。

    性能：朴素的 8x8 滑窗 + 全像素比对在 240x160 上是百万级比较，太慢
    （实测 1 帧要 2 分钟）。先挑一个"有辨识度"的像素做候选预筛：
    取 tile 里出现次数最少的非零颜色所在位置，只在截图中该色出现处开窗。
    """
    th, tw = tile_rgb.shape[:2]
    sh, sw = shot.shape[:2]
    if th > sh or tw > sw:
        return False
    t = tile_rgb.astype(np.int16)

    # 预筛：找到一个"少见色 + 其坐标"
    flat = tile_rgb.reshape(-1, 3)
    uniq, counts = np.unique(flat, axis=0, return_counts=True)
    probe_i = int(np.argmin(counts))
    probe = uniq[probe_i]
    ys, xs = np.nonzero((tile_rgb == probe).all(axis=2))
    if len(ys) == 0:
        return False
    py, px = int(ys[0]), int(xs[0])

    # 在截图里找该色所有位置，按偏移推窗口
    cands = np.nonzero((shot == probe).all(axis=2))
    for cy, cx in zip(*cands):
        y0, x0 = cy - py, cx - px
        if y0 < 0 or x0 < 0 or y0 + th > sh or x0 + tw > sw:
            continue
        if np.abs(shot[y0:y0 + th, x0:x0 + tw].astype(np.int16) - t).max() <= tol:
            return True
    return False


# ─────────────────────────────────────────────────────────────
# A. OBJ 路径
# ─────────────────────────────────────────────────────────────

def harvest_obj(snap: Snapshot, shot: np.ndarray, index, rom: bytes):
    """返回该帧里通过验证的 OBJ 配置列表。"""
    if not snap.obj_on:
        return []
    out = []
    for o in parse_oam(snap):
        if o.affine:
            continue
        stride = 64 if o.bpp8 else 32
        wt, ht = o.w // 8, o.h // 8
        tiles = []
        for ty in range(ht):
            for tx in range(wt):
                off = OBJ_VRAM + (o.tile_no + ty * wt + tx) * stride
                if off + stride > len(snap.vram):
                    tiles = []
                    break
                tiles.append(snap.vram[off:off + stride])
            if not tiles:
                break
        if not tiles:
            continue

        # 定位 ROM 块（逐 tile 投票）
        votes = defaultdict(int)
        offs = []
        for t in tiles:
            h = rom_block_of(index, t)
            if h is None:
                offs = []
                break
            votes[h[0]] += 1
            offs.append(h[1])
        if not offs:
            continue
        addr = max(votes, key=votes.get)
        base = min(offs)
        block = next((d for a, d, c in index if a == addr), None)
        comp = next((c for a, d, c in index if a == addr), "lz77_swap")
        if block is None:
            continue
        per = wt * ht * stride
        count = len(block) // per

        # 调色板：4bpp 用 OBJ bank；8bpp 用整块 256 色（bank 无效）
        first = 0x100 + (o.palbank * 16 if not o.bpp8 else 0)
        raw = cgram_raw(snap.pal, first, 256 if o.bpp8 else 16)
        pals = find_palette_in_rom(rom, raw)
        if not pals:
            continue

        # 像素验证：sprite 与截图同位置逐像素
        x0, y0 = max(0, o.x), max(0, o.y)
        sx, sy = x0 - o.x, y0 - o.y
        w = min(o.w - sx, shot.shape[1] - x0)
        h = min(o.h - sy, shot.shape[0] - y0)
        if w <= 0 or h <= 0:
            continue
        sub = o.rgb[sy:sy + h, sx:sx + w]
        m = o.mask[sy:sy + h, sx:sx + w]
        op = ~m
        if op.sum() < 16:
            continue
        ok = (np.abs(sub.astype(np.int16)
                     - shot[y0:y0 + h, x0:x0 + w].astype(np.int16)).max(axis=2) == 0)
        if (ok & op).sum() != op.sum():
            continue

        out.append({
            "address": addr, "palette": pals[0], "bpp": 8 if o.bpp8 else 4,
            "comp": comp, "w": o.w, "h": o.h, "count": count,
            "palbank": o.palbank, "raw_size": len(block),
            "scene": "", "via": "obj", "pixels": int(op.sum()),
            "tiles": len(tiles),
        })
    return out


# ─────────────────────────────────────────────────────────────
# B. BG 路径
# ─────────────────────────────────────────────────────────────

def harvest_bg(snap: Snapshot, shot: np.ndarray, index, rom: bytes,
               min_tiles: int = 6):
    """扫每层 BG 的 charBlock，按 ROM 块聚合出 tileset；调色板用「单 tile
    能否在截图里精确找到」打分（与卷动无关）。"""
    out = []
    for bg in range(4):
        if not snap.bg_on(bg):
            continue
        cnt = snap.bgcnt(bg)
        cb = (cnt >> 2) & 3
        bpp8 = bool(cnt & 0x80)
        char_base = cb * (0x8000 if bpp8 else 0x4000)
        stride = 64 if bpp8 else 32

        by_block = defaultdict(list)
        for t in range((0x8000 if bpp8 else 0x4000) // stride):
            off = char_base + t * stride
            if off + stride > min(len(snap.vram), 0x10000):
                break
            blk = snap.vram[off:off + stride]
            if blk == b"\x00" * stride:
                continue
            h = rom_block_of(index, blk)
            if h is None:
                continue
            by_block[h[0]].append((t, off, blk))

        for addr, members in by_block.items():
            if len(members) < min_tiles:
                continue
            block = next((d for a, d, c in index if a == addr), None)
            comp = next((c for a, d, c in index if a == addr), "lz77_swap")
            if block is None:
                continue

            # 用该块里的前几个 tile 做调色板打分
            sample = [blk for _t, _o, blk in members[:8]]
            best = None
            # ⚠ 8bpp 的索引是 0-255，不能用 16 色 bank 查表
            #   （实测标题 BG2 是 8bpp，索引最大 19，按 16 色会 IndexError）
            if bpp8:
                banks = [(None, cgram_colors(snap.pal, 0, 256))]
            else:
                banks = [(b, cgram_colors(snap.pal, b * 16, 16))
                         for b in range(16)]
            for bank, colors in banks:
                hit = 0
                for blk in sample:
                    idx = decode_8bpp(blk) if bpp8 else decode_4bpp(blk)
                    if not idx.any():
                        continue
                    if tile_in_shot(shot, colors[idx]):
                        hit += 1
                if hit and (best is None or hit > best[0]):
                    best = (hit, bank)
            if best is None or best[0] < max(2, len(sample) // 2):
                continue
            bank = best[1]
            raw = cgram_raw(snap.pal, 0 if bpp8 else bank * 16,
                            256 if bpp8 else 16)
            pals = find_palette_in_rom(rom, raw)
            if not pals:
                continue
            out.append({
                "address": addr, "palette": pals[0], "bpp": 8 if bpp8 else 4,
                "comp": comp, "w": 8, "h": 8,
                "count": len(block) // (64 if bpp8 else 32),
                "palbank": bank if bank is not None else 0,
                "raw_size": len(block),
                "scene": "", "via": "bg", "pixels": best[0],
                "tiles": len(members),
            })
    return out


# ─────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--limit-runs", type=int, default=300)
    ap.add_argument("--min-bg-tiles", type=int, default=6)
    ap.add_argument("--scenes", default=None,
                    help="逗号分隔；缺省扫全部场景（每场景取最新 2 个 run）")
    args = ap.parse_args()

    rom = ROM_PATH.read_bytes()
    print(f"ROM {len(rom)} bytes")
    print("建 ROM LZ77 索引...")
    index = build_rom_index(rom)
    print(f"  {len(index)} 块\n")

    if args.scenes:
        scenes = args.scenes.split(",")
    else:
        scenes = sorted({d.parent.parent.name for d in BOT_ROOT.glob("*/**/origin")
                         if not d.parent.parent.name.startswith("_")})
    print(f"扫 {len(scenes)} 个场景...")

    results = defaultdict(list)
    n_frames = 0
    for sc in scenes:
        runs = sorted((BOT_ROOT / sc).glob("*/origin"))[-2:]
        for d in runs:
            for p in [x for x in d.glob("*.png") if x.stem.isdigit()][:2]:
                if not (d / f"{p.stem}.vram.bin").is_file():
                    continue
                try:
                    snap = Snapshot.load(d, p.stem)
                    shot = np.asarray(Image.open(p).convert("RGB"))
                except Exception:
                    continue
                n_frames += 1
                for r in harvest_obj(snap, shot, index, rom):
                    r["scene"] = sc
                    results[(r["address"], r["palette"], r["w"], r["h"],
                             r["bpp"])].append(r)
                for r in harvest_bg(snap, shot, index, rom, args.min_bg_tiles):
                    r["scene"] = sc
                    results[(r["address"], r["palette"], r["w"], r["h"],
                             r["bpp"])].append(r)
    print(f"扫了 {n_frames} 帧，得到 {len(results)} 组通过验证的配置\n")

    if not results:
        print("没有配置通过验证。")
        return 0

    import yaml
    cfg = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    existing = {int(str(p["address"]), 16): p for p in cfg["tiles"]["presets"]}

    rows = []
    for key, group in results.items():
        g0 = group[0]
        rows.append({
            "address": g0["address"], "palette": g0["palette"],
            "bpp": g0["bpp"], "comp": g0["comp"],
            "w": g0["w"], "h": g0["h"], "count": g0["count"],
            "raw_size": g0["raw_size"], "via": g0["via"],
            "palbank": g0["palbank"],
            "scenes": sorted({x["scene"] for x in group})[:5],
            "n_frames": len(group),
            "pixels": max(x["pixels"] for x in group),
        })
    rows.sort(key=lambda r: -r["n_frames"])

    print(f"{'地址':12s} {'调色板':12s} {'格式':9s} {'count':>5s} {'路':4s} "
          f"{'帧数':>4s} 场景")
    for r in rows:
        print(f"0x{r['address']:08X} 0x{r['palette']:08X} "
              f"{r['bpp']}bpp {r['w']}x{r['h']:<3d} {r['count']:5d} "
              f"{r['via']:4s} {r['n_frames']:4d} {','.join(r['scenes'][:3])}")

    new = [r for r in rows if r["address"] not in existing]
    upd = [r for r in rows
           if r["address"] in existing
           and str(existing[r["address"]].get("palette", "")).lower()
           != f"0x{r['palette']:08x}"]
    print(f"\n其中 yaml 里没有的: {len(new)} 条；已有但 palette 不同的: {len(upd)} 条")

    if not args.write:
        print("\n（未加 --write，不改 yaml）")
        return 0
    if not new and not upd:
        print("没有需要写入的配置。")
        return 0

    bak = YAML_PATH.with_suffix(".yaml.bak")
    shutil.copyfile(YAML_PATH, bak)
    print(f"\n备份 → {bak.name}")

    text = YAML_PATH.read_text(encoding="utf-8")
    # 追加到 tiles.presets 末尾（在 texts: 之前）
    marker = "\ntexts:"
    idx = text.find(marker)
    if idx < 0:
        print("[ERR] 找不到 texts: 段，无法定位插入点")
        return 1
    lines = []
    for r in new:
        pid = f"bg_{r['address']:08X}" if r["via"] == "bg" else f"obj_{r['address']:08X}"
        label = (f"BG tileset @0x{r['address']:08X}（来自 {','.join(r['scenes'][:2])}）"
                 if r["via"] == "bg"
                 else f"OBJ sheet @0x{r['address']:08X}（来自 {','.join(r['scenes'][:2])}）")
        lines.append(f"  - id: {pid}\n")
        lines.append(f"    label: {label}\n")
        lines.append("    default: false\n")
        lines.append(f"    address: '0x{r['address']:08X}'\n")
        lines.append(f"    palette: '0x{r['palette']:08X}'\n")
        lines.append(f"    format: {r['bpp']}bpp\n")
        lines.append(f"    compression: {r['comp']}\n")
        lines.append(f"    sprite_size: {r['w']}x{r['h']}\n")
        lines.append(f"    count: {r['count']}\n")
        lines.append(f"    raw_size: {r['raw_size']}\n")
        lines.append("    source: bot_harvest\n")
    text = text[:idx] + "".join(lines) + text[idx:]
    YAML_PATH.write_text(text, encoding="utf-8")
    print(f"已追加 {len(new)} 条配置 → {YAML_PATH.name}")

    # 语法自检
    try:
        yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
        print("yaml 语法检查通过")
    except Exception as e:
        print(f"[ERR] yaml 语法坏了，回滚: {e}")
        shutil.copyfile(bak, YAML_PATH)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
