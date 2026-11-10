#!/usr/bin/env python3
"""从 manifest 里找摘要页帧号（特性名所在界面）。

用法：
    python scripts/research/ruby/find_summary_frame.py <run_dir>
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


def main() -> int:
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if run is None:
        runs = sorted((ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"
                       / "pokemon_menu").glob("*"))
        runs = [r for r in runs if r.is_dir()]
        run = runs[-1]
    print(f"run: {run.name}")

    m = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    pairs = m.get("pairs") or []
    print(f"pairs: {len(pairs)}\n")

    kw = ("summary", "tab", "ability", "特性")
    for p in pairs:
        step = str(p.get("scene_step") or "")
        if any(k in step.lower() for k in kw):
            n = p.get("number")
            print(f"  #{n:>3} {step:<28} "
                  f"origin/{n:03d}.png  translated/{n:03d}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
