"""把 bot 回放解析出的界面图块集写成 preset 配置，并逐条自验。

数据源只有 bot 回放的快照（vram/pal/io），不涉及译文版：
  catalog.json 里每条 = 某场景某个 BG 层里「同一块 ROM 图块集」的格子集合，
  已经把 tile 号 / palbank / 翻转都记下来了。

流程：
  1) 过滤：排除通用地图图块集、排除整屏区域、调色板必须能在 ROM 里定位
  2) 按 (图块集, 偏移, 位深, 裁剪框) 去重，保留格子最多的那份
  3) 生成 compose.type: cells 的 preset（不依赖 ROM tilemap，因为这类
     界面的 map 是程序在 RAM 里搭的，ROM 里只有空白底板）
  4) 用 tiles_patcher export 逐条导出，和回放裁图逐像素比对；不一致的剔除

用法：
  python scripts/scene_assets/emit_scene_presets.py
  python scripts/scene_assets/emit_scene_presets.py --catalog work/scene_assets/catalog.json \
      --out work/scene_presets.yaml --verify
"""
import argparse
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "misc"))

import harvest_all_scene_assets as H  # noqa: E402
from util.gba_ppu import Snapshot  # noqa: E402

MAP_GENERAL = 0x081EC74C
MAX_AREA_RATIO = 0.55
GAME_CFG = ROOT / "src" / "util" / "configs" / "POKEMON_RUBY_AXVJ00.yaml"
ROM = H.ROM_PATH


def bank_raw_addr(blob32: bytes, rom: bytes):
    i = rom.find(blob32)
    while i >= 0:
        addr = 0x08000000 + i
        if (addr - 0x08000000) % 4 == 0:
            return addr
        i = rom.find(blob32, i + 1)
    return None


def dump_presets(presets) -> str:
    """手写 yaml：cells 表每格一行，safe_dump 会拆成 3 行太臃肿。"""
    out = ["tiles:", "  presets:"]
    for p in presets:
        out.append(f"  - id: {p['id']}")
        out.append(f"    label: {p['label']}")
        out.append(f"    default: {'true' if p['default'] else 'false'}")
        out.append(f"    address: '{p['address']}'")
        out.append(f"    format: {p['format']}")
        out.append(f"    compression: {p['compression']}")
        if "raw_size" in p:
            out.append(f"    raw_size: {p['raw_size']}")
        out.append(f"    palette: '{p['palette']}'")
        out.append(f"    palette_size: {p['palette_size']}")
        out.append("    compose:")
        c = p["compose"]
        out.append("      type: cells")
        out.append(f"      width: {c['width']}")
        out.append(f"      height: {c['height']}")
        out.append(f"      crop: {json.dumps(c['crop'])}")
        if c.get("offset"):
            out.append(f"      offset: {json.dumps(c['offset'])}")
        if c.get("sources"):
            out.append("      sources:")
            for s in c["sources"]:
                extra = (f", raw_size: {s['raw_size']}" if s.get("raw_size")
                         else "")
                out.append(f"      - {{address: '{s['address']}', "
                           f"compression: {s['compression']}{extra}}}")
        if c.get("palette_banks"):
            out.append("      palette_banks:")
            for b in sorted(c["palette_banks"], key=lambda x: int(x)):
                out.append(f"        {b}: '{c['palette_banks'][b]}'")
        out.append("      cells:")
        for cell in c["cells"]:
            out.append(f"      - [{', '.join(str(v) for v in cell)}]")
        out.append("    source: scene_capture")
        out.append("    note: '" + p["note"].replace("'", "") + "'")
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=str(ROOT / "work" / "scene_assets"
                                             / "catalog.json"))
    ap.add_argument("--out", default=str(ROOT / "work" / "scene_presets.yaml"))
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    rom = ROM.read_bytes()

    groups = defaultdict(list)
    for e in catalog:
        if int(e["tileset"]["address"], 16) == MAP_GENERAL:
            continue
        if e["cell_count"] < 6:
            continue
        srcs = e.get("sources") or [{"address": e["tileset"]["address"],
                                     "compression": e["tileset"]["compression"]}]
        key = (srcs[0]["address"], e["tileset"]["offset"], e["bpp"],
               tuple(e["crop"]), len(srcs))
        groups[key].append(e)

    picked = [max(v, key=lambda e: (e["cell_count"], e.get("replay", 1.0)))
              for v in groups.values()]
    picked.sort(key=lambda e: (e["tileset"]["address"], e["crop"][1], e["crop"][0]))

    # ── OBJ：只保「文字条」──
    # 1) 高 > 40px 的是立绘/宝可梦大图，不是文字条，不收；
    # 2) 同场景里两块重叠 ≥80% 的条（同一张图在 ROM 里有一份字节完全相同
    #    的副本），落哪块都可能改错，直接都丢掉。
    def _obj_only(e):
        if e.get("layer") != "obj" or e["crop"][3] > 40:
            return False
        # 3) 纯色实心块是装饰（列表滚动条、底条）：ui_sweep 图鉴列表左侧那条
        #    蓝色竖条整块只有 1 种颜色。注意只判「1 色」，别误杀「白底黑字」
        #    这种正常文字条（它们也只有 2 色）。
        im = Image.open(ROOT / e["png"]).convert("RGBA")
        px = [p for p in im.getdata() if p[3] > 0]
        return len(set(px)) > 1

    def _overlap(a, b):
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        w = min(ax + aw, bx + bw) - max(ax, bx)
        h = min(ay + ah, by + bh) - max(ay, by)
        if w <= 0 or h <= 0:
            return 0.0
        return (w * h) / min(aw * ah, bw * bh)

    kept: list[dict] = []
    for e in picked:
        if e.get("layer") == "obj" and not _obj_only(e):
            continue
        clash = [k for k in kept
                 if k["scene"] == e["scene"]
                 and _overlap(k["crop"], e["crop"]) >= 0.8]
        if clash:
            print(f"  重叠丢弃 {e['png']} (与 {clash[0]['png']} 重叠)")
            continue
        kept.append(e)
    picked = kept
    print(f"候选组 {len(picked)}（原始条目 {len(catalog)}）")

    presets = []
    skipped = []
    for e in picked:
        snap = Snapshot.load(H.BOT_ROOT / e["scene"] / e["frame"].split("/")[0]
                             / "origin", e["frame"].split("/")[1])
        banks = sorted({(int(c[2]) >> 12) & 0xF for c in e["cells"]})
        bank_base = 512 if e.get("layer") == "obj" else 0
        bank_addrs = {}
        for b in banks:
            a = bank_raw_addr(bytes(snap.pal[bank_base + b * 32:bank_base + (b + 1) * 32]),
                              rom)
            if not a:
                bank_addrs = {}
                break
            bank_addrs[b] = a
        if bank_addrs:
            pal_addr = f"0x{bank_addrs[min(bank_addrs)]:08X}"
            pal_size = 32 * (max(bank_addrs) + 1)
        else:
            pal = e["palette"]
            # 整块 LZ 调色板：解压后从 bank0 连续，只要格子用的 bank 从 0 起
            # 且块内偏移为 0，就能直接拿块地址当 palette（和背包 preset 同法）
            if (pal.get("compression") in ("lz77", "lz77_swap")
                    and pal.get("offset") == 0 and min(banks) == 0):
                pal_addr = f"0x{pal['address']:08X}"
                pal_size = 32 * (max(banks) + 1)
            elif pal.get("compression") == "none":
                pal_addr = f"0x{pal['address'] + pal['offset']:08X}"
                pal_size = pal["size"]
            else:
                skipped.append((e, "调色板既无 raw 副本，也不是从 bank0 起的整块"))
                continue

        ts = e["tileset"]
        srcs = e.get("sources") or [{"address": ts["address"],
                                     "compression": ts["compression"]}]
        comp = srcs[0]["compression"]
        if comp == "raw":
            comp = "none"
        stride = 64 if e["bpp"] == 8 else 32
        crop = e["crop"]
        cells = [list(map(int, c[:3])) + ([int(c[3])] if len(c) > 3 else [])
                 for c in e["cells"]]
        multi = len(srcs) > 1
        if not multi:
            cells = [c[:3] for c in cells]
        pid = (f"scene_{int(srcs[0]['address'], 16):08x}_{ts['offset']:03x}"
               f"_{crop[0]}_{crop[1]}_{crop[2]}x{crop[3]}")
        if multi:
            pid += f"_s{len(srcs)}"
        preset = {
            "id": pid,
            "label": f"{e['scene']} 界面图块 {srcs[0]['address']}",
            "default": False,
            "address": srcs[0]["address"],
            "format": f"{e['bpp']}bpp",
            "compression": comp,
        }
        if comp == "none":
            max_tile = max((c[2] & 0x3FF) for c in cells if len(c) < 4 or c[3] == 0)
            preset["raw_size"] = (max_tile + 1) * stride
        preset["palette"] = pal_addr
        preset["palette_size"] = pal_size
        preset["compose"] = {
            "type": "cells",
            "width": max(30, max(c[0] for c in cells) + 1),
            "height": max(20, max(c[1] for c in cells) + 1),
            "crop": list(crop),
            "cells": cells,
        }
        if multi:
            s_desc = []
            for si, s in enumerate(srcs):
                c2 = s["compression"]
                s_desc.append({"address": s["address"],
                               "compression": "none" if c2 == "raw" else c2})
                tiles = [c[2] & 0x3FF for c in cells
                         if len(c) > 3 and c[3] == si]
                if s_desc[-1]["compression"] == "none":
                    s_desc[-1]["raw_size"] = (max(tiles) + 1) * stride if tiles else 0
            preset["compose"]["sources"] = s_desc
        if e.get("phase") and any(int(v) for v in e["phase"]):
            preset["compose"]["offset"] = [int(v) for v in e["phase"]]
        if bank_addrs:
            preset["compose"]["palette_banks"] = {
                str(b): f"0x{a:08X}" for b, a in bank_addrs.items()}
        layer_txt = (f"BG{e['bg']}" if "bg" in e else "OBJ 精灵")
        preset["source"] = "scene_capture"
        preset["note"] = (f"bot 回放解析：场景 {e['scene']}（{e['frame']}）{layer_txt}，"
                          f"{e['cell_count']} 格 / 图块集覆盖 {ts['coverage']}。"
                          "map 由程序在 RAM 里搭，故用 cells 表而非 ROM tilemap。")
        preset["_ref_png"] = e["png"]
        if args.debug:
            print("  ", pid, "pal", pal_addr, pal_size,
                  "banks", preset["compose"].get("palette_banks"))
        presets.append(preset)

    # ── 自验：逐条导出，与回放裁图比对 ──
    if args.verify and presets:
        cfg = yaml.safe_load(GAME_CFG.read_text(encoding="utf-8"))
        tmp_cfg = ROOT / "work" / "_verify_config.yaml"
        bad = []
        for p in presets:
            cfg["tiles"]["presets"] = [{k: v for k, v in p.items()
                                        if not k.startswith("_")}]
            tmp_cfg.write_text(yaml.safe_dump(cfg, allow_unicode=True,
                                              sort_keys=False), encoding="utf-8")
            out_dir = ROOT / "work" / "verify_presets" / p["id"]
            out_dir.mkdir(parents=True, exist_ok=True)
            r = subprocess.run(
                [sys.executable, "-m", "util.tiles_patcher", "export", str(ROM),
                 "--preset", p["id"], "--config", str(tmp_cfg),
                 "-o", str(out_dir)],
                cwd=str(ROOT / "src"), capture_output=True, text=True,
                env={**__import__("os").environ,
                     "PYTHONPATH": str(ROOT / "src") + ";" +
                     __import__("os").environ.get("PYTHONPATH", "")},
            )
            if r.returncode != 0:
                bad.append((p["id"], "导出失败: " + (r.stderr or r.stdout)[-200:]))
                continue
            pngs = list(out_dir.glob("*_compose.png"))
            if not pngs:
                bad.append((p["id"], "没有 compose 输出"))
                continue
            got = np.asarray(Image.open(pngs[0]).convert("RGBA"))
            want = np.asarray(Image.open(ROOT / p["_ref_png"]).convert("RGBA"))
            if want.shape != got.shape:
                bad.append((p["id"], f"尺寸不一致 {got.shape} vs {want.shape}"))
                continue
            # 只比「导出里真正画出来的像素」：bbox 内仍可能有运行时字形格，
            # 那部分 preset 本来就不负责（由字体层渲染），透明即跳过。
            # 覆盖率按「导出自身画了多少」算 —— 文字条本来就大片透明，
            # 拿 bbox 面积当分母会把正确的条误杀。
            mask = got[..., 3] > 0
            want_mask = want[..., 3] > 0
            if mask.sum() < 16:
                bad.append((p["id"], f"几乎全透明 {int(mask.sum())}"))
                continue
            uncovered = int((mask & ~want_mask).sum())
            if uncovered > 0.1 * mask.sum():
                bad.append((p["id"],
                            f"导出有 {uncovered}/{int(mask.sum())} px 对不上参考"))
            diff = np.abs(want[..., :3].astype(int) - got[..., :3].astype(int))
            worst = int(diff[mask].max()) if mask.any() else 0
            if worst > 8:
                bad.append((p["id"], f"像素不一致 最大差 {worst}"))
                continue
        for pid, why in bad:
            print(f"  ✗ {pid}: {why}")
            presets = [p for p in presets if p["id"] != pid]

    for p in presets:
        p.pop("_ref_png", None)
    text = dump_presets(presets)
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"\n写出 {len(presets)} 条 preset → {args.out}")
    if skipped:
        print(f"跳过 {len(skipped)} 条：")
        for e, why in skipped[:10]:
            print(f"  - {e['scene']} {e['tileset']['address']}+{e['tileset']['offset']:X}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
