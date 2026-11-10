#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bot/accept.py — 一键验收：跑 verify + 聚合 + 分级 + 给出可定位清单。

存在理由（本工程 111 轮循环的直接教训）：
  * bot/run.py 只在加 --verify 时才调 verify.py，实际运行的批次常常没加，
    于是采集了截图却没有 verdict。
  * verify.py 单次只评一个 run_dir，没有跨场景聚合，没人看得出「52% 帧失败」。
  * 没有分级，人只能逐页肉眼过 —— 这就是「反馈不过来」。

用法：
  python bot/accept.py                       # 聚合所有最新 run 的 verdict（不重跑 verify）
  python bot/accept.py --verify              # 先对没 verdict.json 的 run 跑一遍 verify
  python bot/accept.py --since 20261029      # 只看某个日期之后
  python bot/accept.py --json out.json       # 同时写机器可读结果
  python bot/accept.py --top 10              # 只显示最严重的 N 条

退出码：0 = 全部 pass；2 = 有 suspect；1 = 有 fail。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOT = Path(__file__).resolve().parent


def shoots_root(game: str) -> Path:
    """场景截图根目录：work/{gameId}/bot（2026-11-02 由 bot/shoots 迁入）。"""
    return ROOT / "work" / game / "bot"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DIM_LABEL = {
    "g_garble": "乱码/竖条残片",
    "g_collide": "撞UI/压图形",
    "g_overflow": "溢出窗口边框",
    "g_newink": "新增墨色(自造字形)",
    "g_area": "区域色差",
    "a_translated": "未见汉化",
    "a_prove": "读档证明",
    "s_scene": "非同一场景(对照失效)",
    "g_black": "整帧空白(崩溃/软复位)",
    "s_reset": "软复位回开场",
    "s_crash": "崩溃/死循环",
    "s_diverged": "永久偏离(状态分叉)",
}


def latest_runs(game: str, since: str | None):
    """每个场景取最新（或 since 之后全部）的 run 目录。"""
    gdir = shoots_root(game)
    if not gdir.is_dir():
        return []
    out = []
    for scene in sorted(gdir.iterdir()):
        if not scene.is_dir():
            continue
        runs = sorted((d for d in scene.iterdir() if d.is_dir()), key=lambda d: d.name)
        if since:
            runs = [d for d in runs if d.name >= since]
        else:
            runs = runs[-1:]
        out.extend((scene.name, d) for d in runs)
    return out


def ensure_verdict(run_dir: Path) -> None:
    if (run_dir / "verdict.json").is_file():
        return
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(BOT / "verify.py"), str(run_dir)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode not in (0, 1, 2):
        print("[warn] verify failed for %s (rc=%d)\n%s"
              % (run_dir.name, proc.returncode, (proc.stderr or "")[-400:]))


def collect(runs):
    frame_v = Counter()
    dim_fail = Counter()
    dim_suspect = Counter()
    scene_dim = defaultdict(Counter)
    items = []

    for scene, run_dir in runs:
        vj = run_dir / "verdict.json"
        if not vj.is_file():
            continue
        try:
            data = json.loads(vj.read_text(encoding="utf-8"))
        except Exception:
            continue
        for f in data.get("frames", []):
            v = f.get("verdict", "?")
            frame_v[v] += 1
            for r in f.get("reasons", []):
                dim = r.get("dim", "?")
                lvl = r.get("level", "?")
                label = DIM_LABEL.get(dim, dim)
                if lvl == "fail":
                    dim_fail[label] += 1
                elif lvl == "suspect":
                    dim_suspect[label] += 1
                scene_dim[scene][label] += 1
                if lvl == "fail":
                    items.append({
                        "scene": scene,
                        "run": run_dir.name,
                        "frame": f.get("number"),
                        "step": f.get("scene_step"),
                        "dim": dim,
                        "label": label,
                        "msg": r.get("msg", ""),
                        "png": str(run_dir / "translated" / ("%03d.png" % (f.get("number") or 0))),
                    })
    return frame_v, dim_fail, dim_suspect, scene_dim, items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", nargs="?", default="POKEMON_RUBY_AXVJ00")
    ap.add_argument("--verify", action="store_true", help="缺 verdict.json 时先跑 verify")
    ap.add_argument("--since", default=None, help="只取 run 名 >= 该前缀，如 20261029")
    ap.add_argument("--json", default=None, help="把结果写成 JSON")
    ap.add_argument("--top", type=int, default=0, help="只列最严重的前 N 条")
    a = ap.parse_args()

    runs = latest_runs(a.game, a.since)
    if not runs:
        print("[ERR] 没有找到 run 目录：%s" % shoots_root(a.game))
        return 3
    if a.verify:
        for _scene, d in runs:
            ensure_verdict(d)

    frame_v, dim_fail, dim_suspect, scene_dim, items = collect(runs)
    total = sum(frame_v.values())
    if not total:
        print("[ERR] 一个 verdict.json 都没读到")
        return 3

    print("=" * 84)
    print("验收汇总  game=%s  runs=%d" % (a.game, len(runs)))
    print("=" * 84)
    print("  帧 %d :  pass=%d  suspect=%d  fail=%d   (FAIL %.1f%%)"
          % (total, frame_v["pass"], frame_v["suspect"], frame_v["fail"],
             100.0 * frame_v["fail"] / total))
    print()

    print("-" * 84)
    print("缺陷类别（按 fail 次数）")
    print("-" * 84)
    print("  %-26s %6s %9s" % ("类别", "fail", "suspect"))
    for label, n in dim_fail.most_common():
        print("  %-26s %6d %9d" % (label, n, dim_suspect.get(label, 0)))
    for label, n in dim_suspect.most_common():
        if label not in dim_fail:
            print("  %-26s %6d %9d" % (label, 0, n))
    print()

    print("-" * 84)
    print("场景 × 类别")
    print("-" * 84)
    labels = sorted(set(dim_fail) | set(dim_suspect))
    short = [l[:6] for l in labels]
    print("  %-14s" % "scene" + "".join("%-8s" % s for s in short))
    for scene in sorted(scene_dim):
        print("  %-14s" % scene
              + "".join("%-8s" % (scene_dim[scene].get(l, 0) or ".") for l in labels))
    print()

    # 按场景严重度排序（fail 数降序），优先修最惨的
    sev = Counter(it["scene"] for it in items)
    print("-" * 84)
    print("优先修复顺序（按 fail 条目数）")
    print("-" * 84)
    for scene, n in sev.most_common():
        print("  %-14s %3d 条" % (scene, n))
    print()

    show = items[: a.top] if a.top else items
    print("-" * 84)
    print("可定位清单（前 %d / 共 %d 条）" % (len(show), len(items)))
    print("-" * 84)
    for it in show:
        print("  [%s] %s 帧%s (%s)" % (it["label"], it["scene"], it["frame"], it["step"]))
        print("        %s" % it["msg"])
        print("        png: %s" % it["png"])

    if a.json:
        Path(a.json).write_text(json.dumps({
            "frames": dict(frame_v),
            "dim_fail": dict(dim_fail),
            "dim_suspect": dict(dim_suspect),
            "scene_dim": {k: dict(v) for k, v in scene_dim.items()},
            "items": items,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n[out] %s" % a.json)

    return 1 if frame_v["fail"] else (2 if frame_v["suspect"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())
