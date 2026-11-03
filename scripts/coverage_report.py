#!/usr/bin/env python3
"""统计每个场景采到的「窗口实例」与「文本窗口」数量，判断覆盖质量。

── 为什么要这个 ────────────────────────────────────────────────────────
warp 成功只代表「到了那张地图」，不代表「采到了窗口」。
用户要求「窗口覆盖全」，所以要能回答：
  · 这个场景里有几帧出现了通过真实性校验的窗口（scan_wins 的 [win] 行）
  · 出现了哪些不同的 template 地址（不同模板 = 不同窗口）
  · 有几帧真的在打印文本（text 指针 + index 推进）

数据来源：每个 run 的 origin/scene.log（bot.lua 会打 [win] 与 [SHOT] 行）。

用法：
  python scripts/coverage_report.py                     # 扫全部场景最新一次 run
  python scripts/coverage_report.py --scene gym_mauville
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOTRUNS = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"

RE_WIN = re.compile(r"^\[win\] 0x([0-9A-F]{8}) state=(\d+) textMode=(\d+) "
                    r"fontNum=(\d+)([^T]*)TILE_BASE=0x([0-9A-F]{4})")
RE_TPL = re.compile(r"tpl@0x([0-9A-F]{8})")
RE_SHOT = re.compile(r"^\[SHOT (\d+)\] name=(\S+)")


def latest_run(scene_dir: Path):
    runs = [d for d in scene_dir.iterdir() if d.is_dir()]
    return max(runs, key=lambda d: d.name) if runs else None


def analyze(log: Path):
    """返回 dict：shots / win_frames / tpls / tms / fns"""
    shots = 0
    win_frames = 0       # 有多少个 SHOT 帧里出现真实窗口
    tpls = set()
    tms = defaultdict(int)
    fns = defaultdict(int)
    cur_has_win = False

    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = RE_SHOT.match(line)
        if m:
            if cur_has_win:
                win_frames += 1
            cur_has_win = False
            shots += 1
            continue
        m = RE_WIN.match(line)
        if m:
            cur_has_win = True
            tms[m.group(3)] += 1
            fns[m.group(4)] += 1
        m = RE_TPL.search(line)
        if m and "tpl@" in line:
            tpls.add(m.group(1))
    if cur_has_win:
        win_frames += 1
    return {"shots": shots, "win_frames": win_frames,
            "tpls": tpls, "tms": tms, "fns": fns}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default=None)
    a = ap.parse_args()

    if not BOTRUNS.is_dir():
        print(f"[ERR] {BOTRUNS} 不存在")
        return 1

    rows = []
    for sd in sorted(BOTRUNS.iterdir()):
        if not sd.is_dir():
            continue
        name = sd.name
        if a.scene and name != a.scene:
            continue
        if name.startswith("_"):
            continue                      # 跳过探针
        run = latest_run(sd)
        if run is None:
            continue
        # 用 origin 与 translated 的并集（两侧窗口结构一致，但保险起见取 origin）
        log = run / "origin" / "scene.log"
        if not log.is_file():
            continue
        st = analyze(log)
        rows.append((name, st))

    if not rows:
        print("没有可统计的场景")
        return 1

    print(f"{'场景':<22} {'帧':>4} {'有窗口帧':>7} {'模板数':>6}  textMode(/fontNum)")
    print("-" * 92)
    tot_f = tot_w = 0
    all_tpl = set()
    for name, st in rows:
        tot_f += st["shots"]
        tot_w += st["win_frames"]
        all_tpl |= st["tpls"]
        tm = ",".join(f"{k}x{v}" for k, v in sorted(st["tms"].items())) or "-"
        fn = ",".join(f"{k}x{v}" for k, v in sorted(st["fns"].items())) or "-"
        print(f"{name:<22} {st['shots']:>4} {st['win_frames']:>7} "
              f"{len(st['tpls']):>6}  tm[{tm}] fn[{fn}]")

    print("-" * 92)
    print(f"合计：{len(rows)} 个场景，{tot_f} 帧，其中 {tot_w} 帧含真实窗口")
    print(f"去重后的 template 地址：{len(all_tpl)} 个")
    for t in sorted(all_tpl):
        print(f"  tpl@0x{t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
