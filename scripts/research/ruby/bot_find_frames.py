#!/usr/bin/env python3
"""定位关键帧的截图，便于人工核对。

用法：
    python scripts/research/ruby/bot_find_frames.py pokemon_menu party
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
BOT = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"


def main() -> int:
    scene = sys.argv[1] if len(sys.argv) > 1 else "pokemon_menu"
    kw = sys.argv[2].lower() if len(sys.argv) > 2 else ""

    runs = sorted((BOT / scene).glob("*"))
    runs = [r for r in runs if r.is_dir()]
    if not runs:
        sys.exit(f"无 run: {scene}")
    run = runs[-1]
    print(f"run: {run}")

    m = run / "manifest.json"
    d = json.loads(m.read_text(encoding="utf-8"))

    # manifest 里的 frame 列表可能在 contract / dumps
    for key in ("frames", "contract", "dumps", "pairs"):
        v = d.get(key)
        if isinstance(v, list) and v:
            print(f"\n{key}: {len(v)} 项")
            print(f"  首项: {json.dumps(v[0], ensure_ascii=False)[:200]}")
            break
        if isinstance(v, dict):
            print(f"\n{key}: dict keys={list(v.keys())[:6]}")

    # 直接列 png 与 verdict 对照
    vj = run / "verdict.json"
    if vj.is_file():
        vd = json.loads(vj.read_text(encoding="utf-8"))
        frames = vd if isinstance(vd, list) else (vd.get("frames") or [])
        print(f"\nverdict frames: {len(frames)}")
        hits = []
        for f in frames:
            step = str(f.get("scene_step") or "")
            if kw and kw in step.lower():
                hits.append(f)
        if not hits and frames:
            hits = frames[:3]
        for f in hits[:8]:
            n = f.get("number")
            step = f.get("scene_step")
            v = f.get("verdict")
            sim = (f.get("metrics") or {}).get("scene_similarity")
            print(f"  #{n:>3} {step:<30} {v:<8} sim={sim}")
            for side in ("origin", "translated"):
                p = run / side / f"{n:03d}.png"
                if p.is_file():
                    print(f"      {side}: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
