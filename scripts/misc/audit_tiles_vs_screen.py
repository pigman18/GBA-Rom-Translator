#!/usr/bin/env python3
"""scripts/misc/audit_tiles_vs_screen.py — 审计：导出的图有多少真能在游戏画面上找到

## 要回答的问题

用户口径：**「导出的图和 bot 截图里的游戏画面，必须渲染一样」**。
本脚本对每条 `tiles.presets` 导出的每个 PNG，做全屏逐像素搜索，
统计「有多少 sprite / tile 真的出现在某个 bot 截图里」。

## 判据（严格，不靠肉眼）

对每个导出 PNG：
  · 取它的不透明像素作为模板
  · 在每张 bot 截图里滑窗搜索，要求**不透明像素 100% 同色**
  · 命中即记该 sprite 为 PASS

汇总到 preset 级别：
  · PASS 率 100%  ⇒ 这条预设导出的就是屏幕上的图
  · PASS 率  0%   ⇒ 导出的东西屏幕上根本没有（垃圾）
  · 介于之间      ⇒ 只有部分帧出现在 bot 覆盖到的场景里

## 用法

    C:/Python314/python.exe scripts/misc/audit_tiles_vs_screen.py
    C:/Python314/python.exe scripts/misc/audit_tiles_vs_screen.py --preset type_icons
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np                                    # noqa: E402
from PIL import Image                                 # noqa: E402

EXPORT_DIR = ROOT / "work" / "_audit"
BOT_ROOT = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"


def load_shots(limit: int = 400):
    """挑覆盖各场景的截图（优先纯 UI 场景）。"""
    prefer = ["bag", "title_menu", "dex", "pokemon_menu", "start_menu",
              "options", "navigator", "save", "trainer_card", "type_icons",
              "battle", "dialogue", "mart_oldale", "shop"]
    shots = []
    for sc in prefer:
        for d in sorted((BOT_ROOT / sc).glob("*/origin"))[-2:]:
            for p in sorted(x for x in d.glob("*.png") if x.stem.isdigit())[:3]:
                shots.append(p)
                if len(shots) >= limit:
                    return shots
    # 不足就补其他场景
    for d in sorted(BOT_ROOT.glob("*/**/origin")):
        if d.parent.parent.name.startswith("_"):
            continue
        for p in sorted(x for x in d.glob("*.png") if x.stem.isdigit())[:1]:
            shots.append(p)
            if len(shots) >= limit:
                return shots
    return shots


def find_template(shots_arr, tpl_rgb, alpha):
    """在截图集合里搜模板，返回命中数。

    全向量化：用 sliding_window_view 一次性把整张图的所有 (th,tw) 窗口
    叠成 (H-th+1, W-tw+1, th, tw, 3)，再和模板逐像素比。
    朴素 Python 双循环实测单模板 30s+（一次审计 10 分钟跑不完），
    这样是每模板 ~10ms 量级。
    """
    from numpy.lib.stride_tricks import sliding_window_view

    th, tw = tpl_rgb.shape[:2]
    n = int(alpha.sum())
    if n == 0:
        return 0
    t = tpl_rgb.astype(np.int16)
    ys, xs = np.nonzero(alpha)
    t_flat = t[ys, xs]                       # (n,3)

    hits = 0
    for arr in shots_arr:
        sh, sw = arr.shape[:2]
        if th > sh or tw > sw:
            continue
        a = arr.astype(np.int16)
        # sliding_window_view(a, (th,tw), axis=(0,1)) 得到
        # (H-th+1, W-tw+1, 3, th, tw) —— 通道轴被挤到中间，不是最后。
        win = sliding_window_view(a, (th, tw), axis=(0, 1))
        # 先按模板的不透明坐标挑像素，再比
        got = win[:, :, :, ys, xs]                       # (H, W, 3, n)
        ok = (np.moveaxis(got, 2, -1) == t_flat).all(axis=-1).all(axis=-1)
        if ok.any():
            hits += 1
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default=None, help="只审计某条（地址前缀，如 0x0836）")
    ap.add_argument("--limit-shots", type=int, default=120)
    ap.add_argument("--max-per-preset", type=int, default=12,
                    help="每条预设最多抽检多少张导出图")
    args = ap.parse_args()

    if not EXPORT_DIR.is_dir():
        print(f"[ERR] 先导出：{EXPORT_DIR} 不存在")
        return 1

    shots = load_shots(args.limit_shots)
    print(f"截图 {len(shots)} 张")
    shots_arr = [np.asarray(Image.open(p).convert("RGB")) for p in shots]
    print(f"全部载入内存\n")

    # 按地址前缀分组
    groups = {}
    for p in sorted(EXPORT_DIR.glob("*.png")):
        stem = p.stem
        if not stem.startswith("0x"):
            continue
        addr = stem.split("_")[0]
        groups.setdefault(addr, []).append(p)
    if args.preset:
        groups = {a: v for a, v in groups.items() if a.startswith(args.preset)}
    if not groups:
        print("[ERR] 没有可审计的导出图")
        return 1

    import yaml
    cfg = yaml.safe_load((ROOT / "src/util/configs/POKEMON_RUBY_AXVJ00.yaml")
                         .read_text(encoding="utf-8"))
    by_addr = {str(x["address"]).lower(): x for x in cfg["tiles"]["presets"]}

    print(f"{'地址':12s} {'文件数':>6s} {'抽检':>4s} {'命中':>4s} {'命中率':>8s}  "
          f"{'preset id':22s} 判定")
    print("-" * 90)
    rows = []
    for addr, files in sorted(groups.items()):
        files = [f for f in files if f.stem.split("_")[-1].isdigit()
                 or f.stem.endswith("_compose")]
        if not files:
            continue
        sample = files[:args.max_per_preset]
        hit = 0
        tested = 0
        for f in sample:
            try:
                im = Image.open(f).convert("RGBA")
            except Exception:
                continue
            arr = np.asarray(im)
            tpl, alpha = arr[:, :, :3], arr[:, :, 3] > 0
            if alpha.sum() < 8:
                continue
            tested += 1
            if find_template(shots_arr, tpl, alpha):
                hit += 1
        if tested == 0:
            continue
        ratio = hit / tested
        pid = by_addr.get(addr.lower(), {}).get("id", "(不在yaml)")
        verdict = ("一致 ✓" if ratio >= 0.999 else
                   "部分" if ratio > 0 else "屏幕上没有 ✗")
        rows.append((addr, len(files), tested, hit, ratio, pid, verdict))
        print(f"{addr:12s} {len(files):6d} {tested:4d} {hit:4d} "
              f"{ratio:8.0%}  {pid:22s} {verdict}")

    print("-" * 90)
    good = sum(1 for r in rows if r[4] >= 0.999)
    part = sum(1 for r in rows if 0 < r[4] < 0.999)
    bad = sum(1 for r in rows if r[4] == 0)
    print(f"\n共 {len(rows)} 条：完全一致 {good}，部分 {part}，屏幕上没有 {bad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
