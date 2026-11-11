#!/usr/bin/env python3
"""scripts/misc/harvest_yaml_from_bot.py — 从 bot 快照反推 yaml 的 tiles 配置

## 要解决的事

`src/util/configs/POKEMON_RUBY_AXVJ00.yaml` 的 `tiles.presets` 有 20 条，
其中 17 条**没有 palette**。`tiles_patcher export` 遇到空 palette 会退化成
灰度图（"警告: 未指定调色板，使用默认灰度调色板"），导出的图没法改图再导入
—— 而验收流程正是「tiles_patcher 导出 → 改图 → 导入」。

缺的是**配置**，不是工具。本脚本从 bot 已有的运行时快照把配置捞出来。

## 原理（每步都有实测依据，2026-11-11）

bot 每帧存 `{vram,pal,oam,io}.bin`：
  · `vram.bin` 0x06000000+96KB —— 游戏**已经解压好**的 tile
  · `pal.bin`  0x05000000+1KB  —— CGRAM 实际生效的 512 色
  · `oam.bin`  0x07000000+1KB  —— 每个精灵的 tile 号 / 调色板 bank / 尺寸

流程：
  1. **OAM** 给出「这个 sprite 用了哪几个 8x8 tile、哪个 palbank」
  2. 逐个 tile 的原始字节在 **ROM 所有 LZ77 解压块**里做子串搜索
     ⇒ 命中即得 `address`（tile 数据的 ROM 地址）
  3. 用 palbank 去 **CGRAM** 取那 16 色（8bpp 取 256 色）
  4. 这 16 色在 ROM 里直接搜 ⇒ 命中即得 `palette`（调色板的 ROM 地址）

## 实测样例（title_menu 帧 001，全部 tile 100% 命中）

    OBJ[0..4] 32x8 4bpp palbank=9   → tile 0x0836CDA4  调色板 0x0836CD84
    OBJ[5]    64x32 8bpp palbank=15 → tile 0x0836EC6C  调色板 0x083E1A58

`0x0836CD84` 恰好位于 `0x0836CDA4` 前 0x20 字节 —— 标准结构体布局
`{palette, ..., tiles@+0x20}`，与 `gdb_patcher` 的 `SpriteTemplate` 结论一致。

## 用法

    C:/Python314/python.exe scripts/misc/harvest_yaml_from_bot.py          # 只打印
    C:/Python314/python.exe scripts/misc/harvest_yaml_from_bot.py --diff   # 对照 yaml
    C:/Python314/python.exe scripts/misc/harvest_yaml_from_bot.py --write  # 写回（先备份）
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "util"))

from tiles_patcher import lz77_decompress             # noqa: E402
from util.gba_ppu import Snapshot, parse_oam          # noqa: E402

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
YAML_PATH = ROOT / "src" / "util" / "configs" / "POKEMON_RUBY_AXVJ00.yaml"
BOT_ROOT = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"
OBJ_VRAM = 0x10000


def build_rom_index(rom: bytes):
    """所有 LZ77 解压块 → [(GBA 地址, 内容, 压缩方式)]。"""
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


def find_tile(index, tile: bytes):
    """在索引里搜一个 8x8 tile，返回 [(addr, offset, comp)]。"""
    return [(a, d.find(tile), c) for a, d, c in index if tile in d]


def cgram_bank(pal: bytes, bank: int, colors: int = 16) -> bytes:
    """CGRAM 的 OBJ 区某个 bank 的原始 GBA555 字节。"""
    off = (0x100 + bank * 16) * 2
    return pal[off:off + colors * 2]


def find_palette(rom: bytes, bank_bytes: bytes):
    """在 ROM 里搜调色板字节，4 字节对齐的排前面。"""
    out, i = [], rom.find(bank_bytes)
    while i >= 0:
        out.append(0x08000000 + i)
        i = rom.find(bank_bytes, i + 1)
    out.sort(key=lambda a: ((a - 0x08000000) % 4 != 0, a))
    return out


def collect(limit_runs: int = 400, frames_per_run: int = 2):
    """遍历 bot 快照，返回每个可见 OBJ 的记录（按 tile 内容去重）。

    ★ 必须**跨场景采样**，不能只取字母序前 N 个 run：
      实测按字母序前 60 个 run 全是 bag 场景（只有 9 个唯一 sprite），
      而 title_menu 一个帧就有 7 个 sprite 且 100% 能反查 ROM。
      bag 里多是光标/动态生成的小图，反查不到 ROM；素材图集中在
      title_menu / dex / pokemon_menu / trainer_card 这类界面。
    """
    seen = {}
    # 每个场景取最新几个 run，保证覆盖面
    per_scene: dict[str, list[Path]] = {}
    for d in sorted(BOT_ROOT.glob("*/**/origin")):
        sc = d.parent.parent.name
        if sc.startswith("_"):
            continue
        per_scene.setdefault(sc, []).append(d)

    # 优先这些「素材图密集」的场景
    prefer = ["title_menu", "dex", "pokemon_menu", "trainer_card", "bag",
              "navigator", "start_menu", "options", "save", "contest_hall",
              "mart_oldale", "shop", "gamecorner_mauville", "gym_dewford"]
    order = [s for s in prefer if s in per_scene] + \
            [s for s in sorted(per_scene) if s not in prefer]

    runs = []
    for sc in order:
        runs.extend(per_scene[sc][-3:])       # 每场景取最新 3 个 run
    if limit_runs:
        runs = runs[:limit_runs]

    for d in runs:
        pngs = [p for p in d.glob("*.png") if p.stem.isdigit()][:frames_per_run]
        for p in pngs:
            if not (d / f"{p.stem}.vram.bin").is_file():
                continue
            try:
                snap = Snapshot.load(d, p.stem)
            except Exception:
                continue
            if not snap.obj_on:
                continue
            for o in parse_oam(snap):
                if o.affine:
                    continue
                stride = 64 if o.bpp8 else 32
                wt, ht = o.w // 8, o.h // 8
                tiles, ok = [], True
                for ty in range(ht):
                    for tx in range(wt):
                        tno = o.tile_no + ty * wt + tx
                        off = OBJ_VRAM + tno * stride
                        if off + stride > len(snap.vram):
                            ok = False
                            break
                        tiles.append(snap.vram[off:off + stride])
                    if not ok:
                        break
                if not ok:
                    continue
                key = (o.w, o.h, o.bpp8,
                       hashlib.md5(b"".join(tiles)).hexdigest())
                if key in seen:
                    continue
                seen[key] = {
                    "tiles": tiles, "w": o.w, "h": o.h, "bpp8": o.bpp8,
                    "palbank": o.palbank,
                    "pal_bytes": cgram_bank(snap.pal, o.palbank,
                                            256 if o.bpp8 else 16),
                    "scene": d.parent.parent.name, "frame": p.stem,
                }
    return list(seen.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--limit-runs", type=int, default=400)
    args = ap.parse_args()

    rom = ROM_PATH.read_bytes()
    print(f"ROM {len(rom)} bytes")
    print("建 ROM LZ77 索引...")
    index = build_rom_index(rom)
    print(f"  {len(index)} 个解压块")

    print("从 bot 快照收集 sprite...")
    sprites = collect(args.limit_runs)
    print(f"  {len(sprites)} 个唯一 sprite\n")

    found = []
    for sp in sprites:
        hits_per_tile = [find_tile(index, t) for t in sp["tiles"]]
        if not all(hits_per_tile):
            continue
        cnt = defaultdict(int)
        for hs in hits_per_tile:
            for a, _o, _c in hs:
                cnt[a] += 1
        if not cnt:
            continue
        addr = max(cnt, key=cnt.get)
        if cnt[addr] < len(sp["tiles"]) * 0.8:
            continue
        offs = []
        for hs in hits_per_tile:
            m = [o for a, o, _c in hs if a == addr]
            if not m:
                break
            offs.append(min(m))
        if len(offs) != len(sp["tiles"]):
            continue
        found.append({**sp, "rom_addr": addr, "rom_off": min(offs),
                      "pal_addrs": find_palette(rom, sp["pal_bytes"])})

    print(f"反查：{len(found)} 个 sprite 定位到 ROM，"
          f"{sum(1 for f in found if f['pal_addrs'])} 个同时定位到调色板\n")

    by_addr = defaultdict(list)
    for f in found:
        by_addr[f["rom_addr"]].append(f)

    print("=" * 70)
    print("从 bot 快照捞到的 tiles 配置：")
    print("=" * 70)
    for addr in sorted(by_addr):
        g = by_addr[addr]
        palbanks = sorted({x["palbank"] for x in g})
        pals = [pa for x in g for pa in x["pal_addrs"]]
        sizes = sorted({f'{x["w"]}x{x["h"]}' for x in g})
        bpps = sorted({8 if x["bpp8"] else 4 for x in g})
        scenes = sorted({x["scene"] for x in g})[:4]
        pal_s = f"0x{pals[0]:08X}" if pals else "未找到"
        print(f"  0x{addr:08X}  {bpps}bpp {','.join(sizes)}  "
              f"palbank={palbanks}  调色板={pal_s}")
        print(f"      来源: {', '.join(scenes)}")

    if not (args.diff or args.write):
        return 0

    import yaml
    cfg = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    presets = cfg["tiles"]["presets"]
    yaml_by_addr = {int(str(p["address"]), 16): p for p in presets}

    print("\n" + "=" * 70)
    print("与 yaml 对照：")
    print("=" * 70)
    updates = {}
    for addr in sorted(by_addr):
        p = yaml_by_addr.get(addr)
        if not p:
            continue
        g = by_addr[addr]
        pals = [pa for x in g for pa in x["pal_addrs"]]
        cur = p.get("palette")
        # ★ bpp 要以 **yaml 预设自己的 format** 为准，不是 bot 侧看到的。
        #   实测：0x0836CDA4 这个 ROM 块同时被 4bpp(32x8 版权字) 和
        #   8bpp(32x32) 的 sprite 引用；按 bot 侧 any(bpp8) 判会误判成
        #   8bpp 从而跳过，但这个预设本身是 4bpp，反推完全有效。
        preset_bpp8 = str(p.get("format", "4bpp")) == "8bpp"

        # ★ 只补空值，绝不覆盖已有 palette。
        #   实测反例：title_banner 现有 0x0836D148（灰白系，正确），
        #   bot 抓到 0x083E1A58（绿色渐变，是别的资源）。8bpp 的 256 色
        #   调色板在 CGRAM 里跨多个 bank，按 bank 取前 16 色会撞上邻居，
        #   所以 8bpp 的反推结果不可信 —— 有现值时必须保留现值。
        if cur:
            print(f"  {p['id']:16s} 现有={cur}  保留（不覆盖）")
            continue
        if not pals:
            print(f"  {p['id']:16s} 现有=(空)  bot 侧未找到调色板")
            continue
        if preset_bpp8:
            print(f"  {p['id']:16s} 现有=(空)  8bpp 反推不可靠，跳过")
            continue

        # 4bpp：优先选紧邻 tile 数据的调色板（结构体布局 palette 在 tiles 前）
        near = [a for a in pals if 0 < addr - a <= 0x100]
        new = near[0] if near else pals[0]
        updates[p["id"]] = new
        gap = addr - new
        print(f"  {p['id']:16s} 现有=(空) → 0x{new:08X}"
              f"（距 tile {gap:+d}B{'，紧邻✓' if near else ''}）")

    if args.write and updates:
        bak = YAML_PATH.with_suffix(".yaml.bak")
        shutil.copyfile(YAML_PATH, bak)
        print(f"\n备份 → {bak.name}")
        text = YAML_PATH.read_text(encoding="utf-8")
        for pid, new in updates.items():
            lines = text.splitlines(keepends=True)
            in_block, insert_at = False, None
            for i, ln in enumerate(lines):
                if ln.strip() == f"- id: {pid}":
                    in_block = True
                    continue
                if in_block:
                    if ln.lstrip().startswith("- id:"):
                        break
                    if ln.strip().startswith("palette:"):
                        lines[i] = f"    palette: '0x{new:08X}'\n"
                        insert_at = None
                        break
                    if ln.strip().startswith("address:"):
                        insert_at = i + 1
            if insert_at is not None:
                lines.insert(insert_at, f"    palette: '0x{new:08X}'\n")
            text = "".join(lines)
        YAML_PATH.write_text(text, encoding="utf-8")
        print(f"已写入 {len(updates)} 条 palette → {YAML_PATH.name}")
        print("验证：重跑 tiles_patcher export --all，看是否还有灰度警告")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
