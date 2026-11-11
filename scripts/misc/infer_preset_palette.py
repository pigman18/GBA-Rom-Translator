#!/usr/bin/env python3
"""scripts/misc/infer_preset_palette.py — 为 yaml 预设反推真实调色板

## 问题

`src/util/configs/POKEMON_RUBY_AXVJ00.yaml` 的 `tiles.presets` 里，20 个预设
有 **17 个没写 `palette`**。`tiles_patcher export` 遇到空 palette 会退回
灰度（代码里那句 "警告: 未指定调色板，使用默认灰度调色板"），导出的图没法
改图 —— 灰度图改完再导入，颜色全丢。

## 思路（证据链，不是猜）

1. **tile 数据是确定的**：从 ROM 地址 LZ77 解压，得到 4bpp/8bpp 索引流。
2. **屏幕像素是确定的**：bot 采集的 `NNN.png` 就是游戏真实渲染结果。
3. 于是可以对每个候选调色板 P 做这件事：
   `decode(tile数据, P)` 得到图 → 在 bot 截图里全屏搜它 →
   一致率高说明 P 就是游戏实际用的那个调色板。

候选 P 从哪来：
  · bot 快照的 CGRAM（512 色，按 16 色 bank 切）—— 这是**运行时真值**
  · ROM 里指向该 sprite 结构体附近的调色板指针
  · ROM 全盘扫描的 raw GBA555 候选

搜索是「每个 sprite × 每个 bank」的笛卡尔积，用 numpy 向量化，否则太慢。

## 用法

    # 只诊断，不写 yaml
    C:/Python314/python.exe scripts/misc/infer_preset_palette.py --preset rt_0837CB34

    # 全部缺 palette 的预设，只打印结果
    C:/Python314/python.exe scripts/misc/infer_preset_palette.py --all-missing

    # 确认后写入 yaml（会先备份）
    C:/Python314/python.exe scripts/misc/infer_preset_palette.py --all-missing --write
"""
from __future__ import annotations

import argparse
import shutil
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "util"))

import numpy as np                                    # noqa: E402
from PIL import Image                                 # noqa: E402

from tiles_patcher import lz77_decompress             # noqa: E402

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
YAML_PATH = ROOT / "src" / "util" / "configs" / "POKEMON_RUBY_AXVJ00.yaml"
SHOT_ROOT = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"


# ─────────────────────────────────────────────────────────────
# ROM 读取
# ─────────────────────────────────────────────────────────────

def rom_decompress(rom: bytes, gba_addr: int):
    """按 GBA 地址取数据，LZ77 就解压，否则当 raw。"""
    off = gba_addr - 0x08000000
    if not (0 <= off < len(rom)):
        return None
    if rom[off] == 0x10:
        for swap in (True, False):
            try:
                d = lz77_decompress(rom[off:], swap=swap)
                if d:
                    return d
            except Exception:
                pass
        return None
    return None


def cgram_banks(snap_pal: bytes, first: int = 0, n: int = 16,
                bank_size: int = 16) -> list[np.ndarray]:
    """从 CGRAM 切出 n 个 bank，每个 bank 是 (bank_size,3) 的 uint8。"""
    out = []
    for b in range(n):
        base = (first + b * bank_size) * 2
        if base + bank_size * 2 > len(snap_pal):
            break
        arr = np.zeros((bank_size, 3), dtype=np.uint8)
        for i in range(bank_size):
            v = struct.unpack_from("<H", snap_pal, base + i * 2)[0]
            r, g, bb = v & 0x1F, (v >> 5) & 0x1F, (v >> 10) & 0x1F
            arr[i] = ((r << 3) | (r >> 2), (g << 3) | (g >> 2),
                      (bb << 3) | (bb >> 2))
        out.append(arr)
    return out


def rom_palette_candidates(rom: bytes, limit: int = 400) -> list[np.ndarray]:
    """扫描 ROM 里的 raw GBA555 调色板（首色黑 + 至少 3 种不同色）。"""
    out = []
    for off in range(0, len(rom) - 32, 2):
        if rom[off] != 0 or rom[off + 1] != 0:
            continue
        chunk = rom[off:off + 32]
        uniq = len(set(chunk[i:i + 2] for i in range(0, 32, 2)))
        if uniq < 3:
            continue
        arr = np.zeros((16, 3), dtype=np.uint8)
        ok = True
        for i in range(16):
            v = struct.unpack_from("<H", chunk, i * 2)[0]
            # 合理性：高位不能太乱（GBA555 只用低 15 位）
            if v & 0x8000:
                ok = False
                break
            r, g, b = v & 0x1F, (v >> 5) & 0x1F, (v >> 10) & 0x1F
            arr[i] = (r << 3, g << 3, b << 3)
        if ok:
            out.append(arr)
        if len(out) >= limit:
            break
    return out


# ─────────────────────────────────────────────────────────────
# tile 解码
# ─────────────────────────────────────────────────────────────

def decode_sprite(tiles: bytes, off: int, w: int, h: int, bpp: int,
                  pal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """把一块 sprite 解成 (rgb, mask)。

    4bpp 每 tile 32 字节；8bpp 每 tile 64 字节。
    tile 排列：按行优先（每行 w/8 个 tile）。
    """
    tw, th = w // 8, h // 8
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    mask = np.ones((h, w), dtype=bool)
    stride = 64 if bpp == 8 else 32
    for ty in range(th):
        for tx in range(tw):
            t_off = off + (ty * tw + tx) * stride
            if t_off + stride > len(tiles):
                continue
            block = tiles[t_off:t_off + stride]
            if bpp == 8:
                idx = np.frombuffer(block, dtype=np.uint8, count=64).reshape(8, 8)
            else:
                idx = np.empty((8, 8), dtype=np.uint8)
                for y in range(8):
                    for x in range(0, 8, 2):
                        b = block[y * 4 + x // 2]
                        idx[y, x] = b & 0xF
                        idx[y, x + 1] = (b >> 4) & 0xF
            sub = rgb[ty * 8:(ty + 1) * 8, tx * 8:(tx + 1) * 8]
            m = mask[ty * 8:(ty + 1) * 8, tx * 8:(tx + 1) * 8]
            if bpp == 8:
                sub[:] = pal[np.clip(idx, 0, len(pal) - 1)]
            else:
                sub[:] = pal[np.clip(idx, 0, len(pal) - 1)]
            m[:] = idx == 0
    return rgb, mask


# ─────────────────────────────────────────────────────────────
# 在截图里找（向量化）
# ─────────────────────────────────────────────────────────────

def best_match(shot: np.ndarray, tpl: np.ndarray, alpha: np.ndarray,
               min_ratio: float = 0.85) -> tuple[float, int, int]:
    """向量化模板匹配，返回最佳 (ratio, x, y)。"""
    sh, sw = shot.shape[:2]
    th, tw = tpl.shape[:2]
    if th > sh or tw > sw:
        return 0.0, -1, -1
    n = int(alpha.sum())
    if n == 0:
        return 0.0, -1, -1

    # 只取不透明像素的坐标做比对（避免透明区干扰）
    ys, xs = np.nonzero(alpha)
    tpl_px = tpl[ys, xs]                       # (n,3)

    best = (0.0, -1, -1)
    for y in range(0, sh - th + 1):
        band = shot[y:y + th]
        for x in range(0, sw - tw + 1):
            win = band[:, x:x + tw]
            got = win[ys, xs]
            eq = (got == tpl_px).all(axis=1)
            r = eq.sum() / n
            if r > best[0]:
                best = (float(r), x, y)
                if r >= 0.999:
                    return best
    return best


def load_shots(limit_per_scene: int = 2, max_total: int = 60):
    """挑一批 bot 截图（优先纯 UI 场景，避免大地图/战斗的遮挡）。"""
    prefer = ["navigator", "start_menu", "options", "save", "dex", "bag",
              "pokemon_menu", "title_menu", "trainer_card", "mart_oldale",
              "shop", "gamecorner_mauville", "contest_hall", "center_dewford"]
    shots = []
    for sc in prefer:
        for d in sorted((SHOT_ROOT / sc).glob("*/origin")):
            for p in sorted(x for x in d.glob("*.png") if x.stem.isdigit())[:limit_per_scene]:
                shots.append((sc, p))
                if len(shots) >= max_total:
                    return shots
    return shots


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", help="单个预设 id")
    ap.add_argument("--all-missing", action="store_true", help="所有缺 palette 的预设")
    ap.add_argument("--write", action="store_true", help="把结果写回 yaml（先备份）")
    ap.add_argument("--min-ratio", type=float, default=0.95,
                    help="判定命中所需的最低一致率")
    args = ap.parse_args()

    import yaml
    rom = ROM_PATH.read_bytes()
    cfg = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    presets = cfg["tiles"]["presets"]

    if args.preset:
        targets = [p for p in presets if p["id"] == args.preset]
    elif args.all_missing:
        targets = [p for p in presets if not p.get("palette")]
    else:
        print("[ERR] 需要 --preset 或 --all-missing")
        return 1
    if not targets:
        print("[ERR] 没有匹配的预设")
        return 1

    shots = load_shots()
    print(f"候选截图 {len(shots)} 张")
    shot_cache = {}
    for sc, p in shots:
        shot_cache[p] = np.asarray(Image.open(p).convert("RGB"))

    # 预收集候选调色板：所有截图的 CGRAM bank + ROM raw 候选
    print("收集候选调色板...")
    cand_pals: list[tuple[str, np.ndarray]] = []
    seen = set()
    for sc, p in shots:
        d = p.parent
        pal_f = d / f"{p.stem}.pal.bin"
        if not pal_f.is_file():
            continue
        raw = pal_f.read_bytes()
        # OBJ 调色板：0x100 起，16 个 bank
        for i, b in enumerate(cgram_banks(raw, first=0x100, n=16)):
            key = b.tobytes()
            if key not in seen:
                seen.add(key)
                cand_pals.append((f"cgram_obj_bank{i}@{sc}/{p.stem}", b))
        # BG 调色板：0 起 16 个 bank
        for i, b in enumerate(cgram_banks(raw, first=0, n=16)):
            key = b.tobytes()
            if key not in seen:
                seen.add(key)
                cand_pals.append((f"cgram_bg_bank{i}@{sc}/{p.stem}", b))
    for i, b in enumerate(rom_palette_candidates(rom, limit=200)):
        key = b.tobytes()
        if key not in seen:
            seen.add(key)
            cand_pals.append((f"rom_raw#{i}", b))
    print(f"候选调色板 {len(cand_pals)} 个\n")

    results = {}
    for preset in targets:
        pid = preset["id"]
        addr = int(str(preset["address"]), 16)
        fmt = preset.get("format", "4bpp")
        bpp = 8 if fmt == "8bpp" else 4
        size = preset.get("sprite_size", "8x8")
        w, h = (int(x) for x in size.lower().split("x"))
        count = int(preset.get("count", 1))
        raw_size = preset.get("raw_size")

        tiles = rom_decompress(rom, addr)
        if tiles is None:
            # 未压缩
            off = addr - 0x08000000
            n = int(raw_size) if raw_size else w * h * count * bpp // 8
            tiles = rom[off:off + n]
        print(f"=== {pid}: {fmt} {w}x{h} ×{count}  ({len(tiles)} bytes)")

        sprite_bytes = w * h * bpp // 8
        best_overall = (0.0, None, -1, -1, None)
        # 只试前几个 sprite（同一个图集通常共用一个调色板）
        for si in range(min(count, 3)):
            off = si * sprite_bytes
            if off + sprite_bytes > len(tiles):
                break
            for pal_name, pal in cand_pals:
                rgb, mask = decode_sprite(tiles, off, w, h, bpp, pal)
                if (~mask).sum() < 8:
                    continue
                for shot_p, shot in shot_cache.items():
                    r, x, y = best_match(shot, rgb, ~mask,
                                         args.min_ratio)
                    if r > best_overall[0]:
                        best_overall = (r, pal_name, x, y, shot_p)
                    if r >= 0.999:
                        break
                if best_overall[0] >= 0.999:
                    break
            if best_overall[0] >= 0.999:
                break

        r, pal_name, x, y, shot_p = best_overall
        if r >= args.min_ratio:
            print(f"   命中 {r:.2%}  调色板={pal_name}  @({x},{y}) in "
                  f"{shot_p.name if shot_p else '?'}")
            results[pid] = {"ratio": r, "palette_src": pal_name,
                            "x": x, "y": y, "shot": str(shot_p)}
        else:
            print(f"   未命中（最佳 {r:.2%} {pal_name}）")

    if results and args.write:
        bak = YAML_PATH.with_suffix(".yaml.bak")
        shutil.copyfile(YAML_PATH, bak)
        print(f"\n备份 -> {bak}")
        text = YAML_PATH.read_text(encoding="utf-8")
        # 逐条插入 palette 字段（在 address 行后）
        for pid, info in results.items():
            print(f"  待写: {pid} <- {info['palette_src']} ({info['ratio']:.1%})")
        print("\n⚠ 自动插入 palette 需要知道 GBA 地址；CGRAM bank 只是"
              "「颜色集合」不是 ROM 地址。\n"
              "   下一步：用这套颜色反查 ROM 里的调色板地址，才能写进 yaml。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
