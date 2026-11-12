#!/usr/bin/env python3
"""scripts/misc/harvest_obj_presets.py — 用 bot 的 OAM 反查 OBJ 预设配置

## 为什么只走 OBJ 路径

`tiles_presets` 里的条目分两类：

1. **OBJ sprite 图集**（`LoadCompressedObjectPic` / `LoadSpriteSheet`）
   OAM 里**显式记录**了每个 sprite 的 tile 号、palbank、尺寸、位置。
   所以用 OAM + VRAM + CGRAM 就能还原出**和屏幕上一样的整张图**，
   不存在"人猜尺寸/人猜调色板"的问题。这是能自动化的部分。

2. **BG 图块集**（charBlock 里的一堆 8x8）
   ⚠ 实测教训（2026-11-11）：背包页的 `たいせつなもの / どうぐ` 看起来
   像图，实际是**文本打印器逐字写进 tilemap 的字模**，不是静态图片。
   把整个 charBlock 按 8x8 导出只能得到一堆碎片（用户当场指出"裂开了"）。
   这类必须靠 `compose`（tilemap）表达，而 tilemap 是运行时构造的，
   ROM 里没有静态表 —— 所以**不适合自动生成 preset**。

## 做法（OBJ）

对每个 bot 快照帧：
  1. `parse_oam` 取每个可见 OBJ 的 tile 号 / palbank / 尺寸 / 位置
  2. 从 VRAM OBJ 区取这些 tile 的原始字节
  3. 逐 tile 在 ROM 全部 LZ77 块里搜 → 命中即得 address
  4. palbank 去 CGRAM 取那 16 色 → 在 ROM 里搜 → 命中即得 palette
  5. **像素验证**：按 OAM 拼出的 sprite 必须与截图同位置逐像素一致
     （不透明像素 100% 同色才算通过）
  6. 只有通过验证的才写进 yaml

## 用法

    C:/Python314/python.exe scripts/misc/harvest_obj_presets.py
    C:/Python314/python.exe scripts/misc/harvest_obj_presets.py --write
"""
from __future__ import annotations

import argparse
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

_CACHE: dict[bytes, tuple | None] = {}


def build_index(rom: bytes):
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


def find_block(index, tile: bytes):
    if tile in _CACHE:
        return _CACHE[tile]
    hit = None
    for addr, data, comp in index:
        i = data.find(tile)
        if i >= 0:
            hit = (addr, i, comp)
            break
    _CACHE[tile] = hit
    return hit


def cgram_raw(pal: bytes, first: int, n: int) -> bytes:
    return pal[first * 2:(first + n) * 2]


def find_palette(rom: bytes, raw: bytes):
    out, i = [], rom.find(raw)
    while i >= 0:
        out.append(0x08000000 + i)
        i = rom.find(raw, i + 1)
    out.sort(key=lambda a: ((a - 0x08000000) % 4 != 0, a))
    return out


def harvest_frame(snap: Snapshot, shot: np.ndarray, index, rom: bytes):
    """返回该帧通过像素验证的 OBJ 配置。"""
    if not snap.obj_on:
        return []
    out = []
    for o in parse_oam(snap):
        if o.affine:
            continue
        stride = 64 if o.bpp8 else 32
        wt, ht = o.w // 8, o.h // 8
        tiles, offs = [], []
        votes = defaultdict(int)
        for ty in range(ht):
            for tx in range(wt):
                off = OBJ_VRAM + (o.tile_no + ty * wt + tx) * stride
                if off + stride > len(snap.vram):
                    continue
                blk = snap.vram[off:off + stride]
                h = find_block(index, blk)
                if h is None:
                    # ★ 不因为个别 tile 找不到就放弃整个 sprite：
                    #   游戏载入 VRAM 时会做重排/补齐，个别 tile 可能被改写。
                    #   只要多数 tile 能定位，就能确定 ROM 块。
                    continue
                tiles.append(blk)
                offs.append(h[1])
                votes[h[0]] += 1
        total = wt * ht
        if not votes or len(tiles) < max(2, total // 2):
            continue

        addr = max(votes, key=votes.get)
        block = next((d for a, d, c in index if a == addr), None)
        comp = next((c for a, d, c in index if a == addr), "lz77_swap")
        if block is None:
            continue
        base = min(offs)
        per = wt * ht * stride
        count = len(block) // per
        if count == 0:
            continue
        # ★ 决定性闸门：必须是「完整 sprite」引用该块。
        #   判据：该 sprite 的每个 8x8 都命中同一块（len(tiles) == total）。
        #   反例（实测）：0x081BBE94 只有 48 个 tile，被 16x16 sprite 部分
        #   引用就成立 ⇒ 导出的是无关碎片，必须排除。
        if len(tiles) != total:
            continue
        if count > 64:
            continue
        # 允许块尾有少量对齐/附加数据（实测 0x0836CDA4 是 1312B，
        # 32x8 的 per=128 ⇒ 10 帧 + 32B 尾巴），但不能差超过一帧。
        if count * per + per < len(block):
            continue

        # 调色板
        first = 0x100 + (0 if o.bpp8 else o.palbank * 16)
        raw = cgram_raw(snap.pal, first, 256 if o.bpp8 else 16)
        pals = find_palette(rom, raw)
        if not pals:
            continue

        # 像素验证
        x0, y0 = max(0, o.x), max(0, o.y)
        sx, sy = x0 - o.x, y0 - o.y
        w = min(o.w - sx, shot.shape[1] - x0)
        hh = min(o.h - sy, shot.shape[0] - y0)
        if w <= 0 or hh <= 0:
            continue
        sub = o.rgb[sy:sy + hh, sx:sx + w].astype(np.int16)
        m = o.mask[sy:sy + hh, sx:sx + w]
        op = ~m
        if op.sum() < 8:
            continue
        eq = np.abs(sub - shot[y0:y0 + hh, x0:x0 + w].astype(np.int16)).max(axis=2) == 0
        ratio = float((eq & op).sum()) / int(op.sum())
        # ★ 不要求 100%：sprite 常被更高优先级层、窗口、混合压住，
        #   整块全等几乎不可能。用「不透明像素同色率」多帧取多数票更稳。
        #   这里只要单帧 ≥ 90% 就记为有效样本；最终按帧数投票。
        if ratio < 0.90:
            continue

        out.append({
            "address": addr, "palette": pals[0], "bpp": 8 if o.bpp8 else 4,
            "comp": comp, "w": o.w, "h": o.h, "count": count,
            "palbank": o.palbank, "raw_size": len(block),
            "pixels": int(op.sum()), "ratio": ratio,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--limit-runs", type=int, default=0, help="0=全部")
    args = ap.parse_args()

    rom = ROM_PATH.read_bytes()
    print(f"ROM {len(rom)} bytes")
    print("建 ROM LZ77 索引...")
    index = build_index(rom)
    print(f"  {len(index)} 块")

    runs = [d for d in sorted(BOT_ROOT.glob("*/**/origin"))
            if not d.parent.parent.name.startswith("_")]
    if args.limit_runs:
        runs = runs[:args.limit_runs]
    print(f"扫 {len(runs)} 个 run...")

    results = defaultdict(list)
    n = 0
    for d in runs:
        for p in [x for x in d.glob("*.png") if x.stem.isdigit()][:1]:
            if not (d / f"{p.stem}.vram.bin").is_file():
                continue
            try:
                snap = Snapshot.load(d, p.stem)
                shot = np.asarray(Image.open(p).convert("RGB"))
            except Exception:
                continue
            n += 1
            for r in harvest_frame(snap, shot, index, rom):
                r["scene"] = d.parent.parent.name
                results[(r["address"], r["w"], r["h"], r["palbank"])].append(r)
    print(f"扫 {n} 帧，{len(results)} 组通过像素验证\n")

    if not results:
        print("没有通过验证的 OBJ 配置。")
        return 0

    import yaml
    cfg = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    existing = {int(str(x["address"]), 16): x for x in cfg["tiles"]["presets"]}

    rows = []
    for key, g in results.items():
        g0 = g[0]
        pals = [x["palette"] for x in g]
        addr = g0["address"]
        rows.append({
            "address": addr,
            "palette": max(set(pals), key=pals.count),
            "bpp": g0["bpp"], "comp": g0["comp"],
            "w": g0["w"], "h": g0["h"], "count": g0["count"],
            "raw_size": g0["raw_size"], "palbank": g0["palbank"],
            "scenes": sorted({x["scene"] for x in g})[:4],
            "frames": len(g),
            "in_yaml": addr in existing,
            "yaml_pal": str(existing[addr].get("palette") or "") if addr in existing else "",
        })
    rows.sort(key=lambda r: -r["frames"])

    print(f"{'地址':12s} {'新palette':12s} {'格式':14s} {'cnt':>4s} "
          f"{'帧':>4s} {'yaml':6s} 场景")
    for r in rows:
        tag = "已有✓" if r["in_yaml"] and r["yaml_pal"] else ("缺pal" if r["in_yaml"] else "缺条目")
        print(f"0x{r['address']:08X} 0x{r['palette']:08X} "
              f"{r['bpp']}bpp {r['w']}x{r['h']:<3d} {r['count']:4d} "
              f"{r['frames']:4d} {tag:6s} {','.join(r['scenes'][:3])}")

    need_pal = [r for r in rows if r["in_yaml"] and not r["yaml_pal"]]
    missing = [r for r in rows if not r["in_yaml"]]
    print(f"\n可补 palette 的已有条目: {len(need_pal)}")
    print(f"yaml 里没有的 OBJ 条目: {len(missing)}")

    if not args.write:
        print("\n（未加 --write，不改 yaml）")
        return 0

    bak = YAML_PATH.with_suffix(".yaml.bak")
    shutil.copyfile(YAML_PATH, bak)
    print(f"\n备份 → {bak.name}")
    text = YAML_PATH.read_text(encoding="utf-8")

    for r in need_pal:
        lines = text.splitlines(keepends=True)
        in_block, insert_at = False, None
        for i, ln in enumerate(lines):
            if ln.strip() == f"- id: {existing[r['address']]['id']}":
                in_block = True
                continue
            if in_block:
                if ln.lstrip().startswith("- id:"):
                    break
                if ln.strip().startswith("palette:"):
                    lines[i] = f"    palette: '0x{r['palette']:08X}'\n"
                    insert_at = None
                    break
                if ln.strip().startswith("address:"):
                    insert_at = i + 1
        if insert_at is not None:
            lines.insert(insert_at, f"    palette: '0x{r['palette']:08X}'\n")
        text = "".join(lines)
        print(f"  补 palette: {existing[r['address']]['id']} ← 0x{r['palette']:08X}")

    if missing:
        idx = text.find("\ntexts:")
        block = []
        for r in missing:
            pid = f"obj_{r['address']:08X}"
            block.append(f"  - id: {pid}\n")
            block.append(f"    label: OBJ sheet @0x{r['address']:08X}"
                         f"（{r['w']}x{r['h']}，来自 {','.join(r['scenes'][:2])}）\n")
            block.append("    default: false\n")
            block.append(f"    address: '0x{r['address']:08X}'\n")
            block.append(f"    palette: '0x{r['palette']:08X}'\n")
            block.append(f"    format: {r['bpp']}bpp\n")
            block.append(f"    compression: {r['comp']}\n")
            block.append(f"    sprite_size: {r['w']}x{r['h']}\n")
            block.append(f"    count: {r['count']}\n")
            block.append(f"    raw_size: {r['raw_size']}\n")
            block.append("    source: bot_harvest\n")
            print(f"  新增条目: {pid} 0x{r['palette']:08X}")
        text = text[:idx] + "".join(block) + text[idx:]

    YAML_PATH.write_text(text, encoding="utf-8")
    try:
        yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
        print("\nyaml 语法检查通过")
    except Exception as e:
        print(f"[ERR] yaml 语法坏了，回滚: {e}")
        shutil.copyfile(bak, YAML_PATH)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
