#!/usr/bin/env python3
"""批量跑场景并汇总窗口数（供铺量时快速迭代）。

用法：
  python scripts/run_batch.py --list a,b,c
  python scripts/run_batch.py --all-new          # 只跑还没采集过的
  python scripts/run_batch.py --scene xxx
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCENES = ROOT / "bot" / "scenes" / "POKEMON_RUBY_AXVJ00"
BOTRUNS = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"
SAV = ROOT / "work" / "_probe" / "teleport.sav"
PY = sys.executable

RE_WIN = re.compile(r"^\[win\]", re.M)


def latest_run(name: str):
    d = BOTRUNS / name
    if not d.is_dir():
        return None
    runs = sorted([x for x in d.iterdir() if x.is_dir()], key=lambda x: x.name)
    return runs[-1] if runs else None


def win_count(name: str) -> int:
    run = latest_run(name)
    if run is None:
        return -1
    log = run / "origin" / "scene.log"
    if not log.is_file():
        return -1
    return len(RE_WIN.findall(log.read_text(encoding="utf-8", errors="replace")))


def warp_line(name: str) -> str:
    run = latest_run(name)
    if run is None:
        return ""
    log = run / "origin" / "scene.log"
    if not log.is_file():
        return ""
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if "[WARP] hit" in line or "[WARP] TIMEOUT" in line:
            return " ".join(line.split())
    return ""


def run_one(name: str, timeout: int = 900) -> tuple[bool, int]:
    cmd = [PY, str(ROOT / "bot" / "run.py"), "POKEMON_RUBY_AXVJ00", name,
           "--save", str(SAV), "--timeout", str(timeout)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    ok = "frame-aligned" in (p.stdout or "")
    return ok, win_count(name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", default=None)
    ap.add_argument("--all-new", action="store_true")
    ap.add_argument("--scene", default=None)
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()

    if a.scene:
        names = [a.scene]
    elif a.list:
        names = [x.strip() for x in a.list.split(",") if x.strip()]
    elif a.all_new:
        names = sorted(f.stem for f in SCENES.glob("*.lua")
                       if f.stem != "main" and win_count(f.stem) < 0)
    else:
        print(__doc__)
        return 2

    print(f"共 {len(names)} 个场景\n")
    bad = []
    for i, n in enumerate(names, 1):
        ok, w = run_one(n, a.timeout)
        mark = "OK " if ok else "ERR"
        low = "  <<< 少" if 0 <= w <= 1 else ""
        print(f"[{i:>3}/{len(names)}] {mark} {n:<26} win={w}{low}")
        if not ok or w <= 1:
            bad.append((n, w, ok))

    print(f"\n完成 {len(names)} 个，需要校准/重试 {len(bad)} 个：")
    for n, w, ok in bad:
        print(f"  {n:<26} win={w} {'(运行失败)' if not ok else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
