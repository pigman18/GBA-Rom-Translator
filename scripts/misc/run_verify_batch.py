#!/usr/bin/env python3
"""批量跑场景采集（历史名 run_verify_batch；verify.py 已删除）。

只调用 bot/run.py 采集 origin/translated 帧对。画面验收按 bot/SKILL.md。

用法：
  python scripts/misc/run_verify_batch.py --all
  python scripts/misc/run_verify_batch.py --list a,b,c
  python scripts/misc/run_verify_batch.py --skip-done   # 跳过已有 manifest 的
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCENES = ROOT / "bot" / "scenes" / "POKEMON_RUBY_AXVJ00"
BOTRUNS = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"
SAV = ROOT / "work" / "_probe" / "teleport.sav"

TOOLS = {
    "font_capture", "font_dump", "font_probe", "font_talk",
    "images_dump", "ref_probe", "page_sweep", "shop",
    "fr_menu", "fr_pair", "fr_pair2", "fr_text", "_diag", "_diag2",
}


def has_manifest(name: str) -> bool:
    d = BOTRUNS / name
    if not d.is_dir():
        return False
    runs = sorted([x for x in d.iterdir() if x.is_dir()], key=lambda x: x.name)
    return bool(runs) and (runs[-1] / "manifest.json").is_file()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", default=None)
    ap.add_argument("--skip-done", action="store_true")
    ap.add_argument("--timeout", type=int, default=1200)
    a = ap.parse_args()

    if a.list:
        names = [x.strip() for x in a.list.split(",") if x.strip()]
    elif a.all:
        names = sorted(f.stem for f in SCENES.glob("*.lua")
                       if f.stem != "main" and not f.stem.startswith("_")
                       and f.stem not in TOOLS)
    else:
        print(__doc__)
        return 2

    if a.skip_done:
        names = [n for n in names if not has_manifest(n)]

    print(f"共 {len(names)} 个场景（采集 only；审图见 bot/SKILL.md）\n", flush=True)
    err = []
    for i, n in enumerate(names, 1):
        cmd = [sys.executable, str(ROOT / "bot" / "run.py"),
               "POKEMON_RUBY_AXVJ00", n, "--save", str(SAV),
               "--timeout", str(a.timeout)]
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        ok = "frame-aligned" in (p.stdout or "")
        print(f"[{i:>3}/{len(names)}] {'OK ' if ok else 'ERR'} {n}", flush=True)
        if not ok:
            err.append(n)

    print(f"\n完成 {len(names)}，失败 {len(err)}")
    for n in err:
        print(f"  {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
