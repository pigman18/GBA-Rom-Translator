#!/usr/bin/env python3
"""src/util/sprite_export.py — 从 bot 运行时快照导出「和屏幕一致」的图片资源

## 与 tiles_patcher.py 的根本区别

| | tiles_patcher.py（静态） | 本模块（运行时） |
|---|---|---|
| 数据来源 | ROM 里 LZ77 解压的 tile | bot 采集的 VRAM/OAM/CGRAM 快照 |
| 调色板 | yaml 里**人猜**的地址 | CGRAM 实际生效的 512 色 |
| 拼合方式 | yaml 里**人猜**的 compose/bank_list | OAM 里的 tile 号/palbank/翻转/尺寸 |
| 正确性证据 | 无（肉眼看着像就行） | 与 bot 截图**逐像素比对** |

`docs/TILES_CANDIDATES_AXVJ.md` 记录过静态导出的问题：横幅那条 palette 是错的，
compose 结构推不出来。运行时导出没有这些问题 —— 游戏自己已经拼好放在 VRAM 里了。

## 核心保证：导出图 = 屏幕上的那张图

每个 sprite 的像素全部来自：
  · VRAM 0x06010000 起的 OBJ 区（tile 数据）
  · CGRAM 0x05000200 起的 OBJ 调色板（真实颜色，**不受 BLD 压暗影响**）
  · OAM 里的 tile 号、palbank、H/V 翻转、尺寸、位置

导出后可用 `verify()` 与 bot 截图逐像素比对：不透明像素 100% 同色才算通过。

## ⚠ 已知边界（实测，不是猜测）

- **只覆盖 OBJ（精灵）**。BG 文本/仿射层需要 BGxHOFS/VOFS、PA/PB/PC/PD，
  这些是只写寄存器，读回来是 open bus 垃圾（实测 0x1C10）。
- **半透明/objwindow 的 OBJ** 在屏幕上是混合结果，导出的是「原始素材」，
  与屏幕像素必然不同 —— 这是特性不是 bug，`verify` 会把它们标出来。
- **被其它层遮挡的 OBJ** 在截图上看到的是遮挡后的样子，`verify` 会判低；
  这属于「图层合成」问题，不是提取错误。

## 用法

    from util.sprite_export import export_from_snapshot
    res = export_from_snapshot(side_dir, "001", out_dir, verify=True)
    print(res["summary"])

命令行：

    C:/Python314/python.exe -m util.sprite_export --scene bag --frame 003
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

try:
    from PIL import Image
except ImportError:                                        # pragma: no cover
    print("[ERR] 需要 Pillow")
    raise SystemExit(3)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from util.gba_ppu import (                                 # noqa: E402
    SCREEN_H, SCREEN_W, ObjSprite, Snapshot, parse_oam,
)


def _crop_visible(o: ObjSprite) -> tuple[int, int, int, int]:
    """返回 sprite 在屏幕上的可见区域 (x0, y0, w, h) 以及内部偏移。"""
    x0, y0 = max(0, o.x), max(0, o.y)
    sx, sy = x0 - o.x, y0 - o.y
    w = min(o.w - sx, SCREEN_W - x0)
    h = min(o.h - sy, SCREEN_H - y0)
    return x0, y0, w, h, sx, sy


def verify_sprite(o: ObjSprite, ref: np.ndarray, tol: int = 0) -> dict:
    """把 sprite 与截图同位置逐像素比对。

    只统计 sprite 不透明的像素 —— 透明区屏幕上显示的是别的层，
    拿它比没有意义。
    """
    x0, y0, w, h, sx, sy = _crop_visible(o)
    if w <= 0 or h <= 0:
        return {"opaque": 0, "match": 0, "ratio": None, "note": "完全出屏"}
    sub = o.rgb[sy:sy + h, sx:sx + w].astype(np.int16)
    m = o.mask[sy:sy + h, sx:sx + w]
    op = ~m
    n = int(op.sum())
    if n == 0:
        return {"opaque": 0, "match": 0, "ratio": None, "note": "全透明"}
    eq = np.abs(sub - ref[y0:y0 + h, x0:x0 + w]).max(axis=2) <= tol
    k = int((eq & op).sum())
    return {"opaque": n, "match": k, "ratio": k / n, "note": ""}


def export_from_snapshot(side_dir, frame: str, out_dir,
                         verify: bool = True, tol: int = 0,
                         min_pixels: int = 1) -> dict:
    """从一个 bot 快照导出全部可见 OBJ 精灵。

    参数
    ----
    side_dir : bot 采集的 origin/ 或 translated/ 目录
    frame    : 帧号（"001"）
    out_dir  : 导出目录
    verify   : 是否与同目录的 {frame}.png 逐像素比对
    tol      : 允许的通道误差（0 = 严格）
    min_pixels: 不透明像素少于此值的不导出（滤掉 1px 噪点/光标）

    返回 {"sprites": [...], "summary": {...}, "sheet": 路径}
    """
    side_dir = Path(side_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    snap = Snapshot.load(side_dir, frame)
    if not snap.obj_on:
        return {"sprites": [], "summary": {"note": "本帧 OBJ 层未开启"}, "sheet": None}

    ref = None
    if verify:
        png = side_dir / f"{frame}.png"
        if png.is_file():
            ref = np.asarray(Image.open(png).convert("RGB")).astype(np.int16)

    objs = parse_oam(snap)
    records = []
    for o in objs:
        op = int((~o.mask).sum())
        if op < min_pixels:
            continue
        rec = {
            "index": o.index,
            "screen": {"x": o.x, "y": o.y, "w": o.w, "h": o.h},
            "tile_no": o.tile_no,
            "bpp": 8 if o.bpp8 else 4,
            "palbank": o.palbank,
            "priority": o.priority,
            "hflip": o.hflip,
            "vflip": o.vflip,
            "affine": o.affine,
            "mode": o.mode,
            "opaque_pixels": op,
        }
        name = f"obj{o.index:03d}_t{o.tile_no}_{o.w}x{o.h}"
        rgba = np.dstack([o.rgb, np.where(o.mask, 0, 255).astype(np.uint8)])
        p = out_dir / f"{name}.png"
        Image.fromarray(rgba, "RGBA").save(p)
        rec["file"] = p.name
        if ref is not None:
            rec["verify"] = verify_sprite(o, ref, tol)
        records.append(rec)

    # 汇总
    summary = {"frame": frame, "obj_total": len(objs),
               "obj_exported": len(records)}
    if ref is not None:
        ok = sum(1 for r in records
                 if r.get("verify", {}).get("ratio") == 1.0)
        low = [r for r in records
               if (r.get("verify", {}).get("ratio") or 0) < 1.0
               and (r.get("verify", {}).get("ratio") is not None)]
        summary.update({
            "verified_exact": ok,
            "verified_low": len(low),
            "low_detail": [
                {"file": r["file"], "ratio": round(r["verify"]["ratio"], 4),
                 "mode": r["mode"], "opaque": r["verify"]["opaque"]}
                for r in low
            ],
        })

    # 拼一张预览表（所有 sprite 横向排列，便于人眼过一遍）
    sheet = None
    if records:
        imgs = [Image.open(out_dir / r["file"]) for r in records]
        pad = 4
        W = sum(i.width + pad for i in imgs) + pad
        H = max(i.height for i in imgs) + pad * 2
        canvas = Image.new("RGBA", (W, H), (40, 40, 40, 255))
        x = pad
        for im in imgs:
            canvas.alpha_composite(im, (x, pad))
            x += im.width + pad
        sheet = out_dir / f"_sheet_{frame}.png"
        canvas.save(sheet)

    (out_dir / f"_index_{frame}.json").write_text(
        json.dumps({"summary": summary, "sprites": records},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    return {"sprites": records, "summary": summary,
            "sheet": str(sheet) if sheet else None}


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="从 bot 运行时快照导出与屏幕一致的精灵资源")
    ap.add_argument("--scene", default=None, help="场景名（如 bag / dex / title_menu）")
    ap.add_argument("--run", default=None, help="具体 run 目录，缺省取最新")
    ap.add_argument("--side", default="origin", choices=["origin", "translated"])
    ap.add_argument("--frame", default=None, help="帧号；缺省导出该 run 全部帧")
    ap.add_argument("--out", default=None, help="输出目录（缺省 work/{game}/sprites/{scene}）")
    ap.add_argument("--tol", type=int, default=0, help="比对容差（0=严格）")
    ap.add_argument("--min-pixels", type=int, default=4,
                    help="不透明像素少于此值不导出（默认 4，滤光标噪点）")
    ap.add_argument("--all-frames", action="store_true",
                    help="导出该 run 的所有帧（默认只导 --frame 或最新一帧）")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[2]
    game = "POKEMON_RUBY_AXVJ00"
    base = root / "work" / game / "bot"
    if not args.scene:
        print("[ERR] 需要 --scene")
        return 1
    runs = sorted(base.glob(f"{args.scene}/*/{args.side}"))
    if not runs:
        print(f"[ERR] 场景 {args.scene} 没有采集目录")
        return 1
    d = Path(args.run) / args.side if args.run else runs[-1]
    if not d.is_dir():
        print(f"[ERR] 目录不存在: {d}")
        return 1

    out_dir = Path(args.out) if args.out else root / "work" / game / "sprites" / args.scene

    frames = sorted(p.stem for p in d.glob("*.png") if p.stem.isdigit())
    if args.frame:
        frames = [args.frame]
    elif not args.all_frames:
        frames = frames[-1:]

    print(f"源: {d}")
    print(f"帧: {frames}")
    print(f"输出: {out_dir}\n")

    grand_ok = grand_all = 0
    for f in frames:
        res = export_from_snapshot(d, f, out_dir, verify=True,
                                   tol=args.tol, min_pixels=args.min_pixels)
        s = res["summary"]
        print(f"帧 {f}: 可见 OBJ {s.get('obj_total', 0)}，导出 {s.get('obj_exported', 0)}")
        if "verified_exact" in s:
            print(f"   逐像素精确 {s['verified_exact']}，"
                  f"不一致 {s['verified_low']}")
            for ld in s.get("low_detail", [])[:6]:
                print(f"     - {ld['file']}: {ld['ratio']:.1%} "
                      f"(mode={ld['mode']}, {ld['opaque']}px)")
            grand_ok += s["verified_exact"]
            grand_all += s.get("obj_exported", 0)
        if res["sheet"]:
            print(f"   预览: {res['sheet']}")

    if grand_all:
        print(f"\n{'='*56}")
        print(f"合计精确 {grand_ok}/{grand_all} ({grand_ok/grand_all:.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
