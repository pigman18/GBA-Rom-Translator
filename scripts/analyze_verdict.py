#!/usr/bin/env python3
"""分析 verdict.json 的失败原因分布，判断哪些是真问题、哪些是判据误报。

用法：
  python scripts/analyze_verdict.py <run_dir>
  python scripts/analyze_verdict.py --all        # 扫所有场景最新一次
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOTRUNS = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"


def load_verdict(run: Path):
    p = run / "verdict.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def tag_of(reason) -> str:
    """把 reason 归成短标签。

    实际结构（2026-11-04 实测 verdict.json）：
        {"dim": "a_translated", "level": "suspect", "msg": "..."}
    所以取 dim（维度）当标签最准确。
    """
    if isinstance(reason, dict):
        return str(reason.get("dim") or reason.get("kind") or "dict")
    s = str(reason)
    if s.startswith("[") and "/" in s:
        return s[1:].split("/")[0]
    if "/" in s:
        return s.split("/")[0]
    return s[:24]


def summarize(run: Path, name: str) -> tuple:
    d = load_verdict(run)
    if d is None:
        return None
    rows = d.get("frames") or []
    counts = Counter(r.get("verdict") for r in rows)
    reasons = Counter()
    for r in rows:
        rs = r.get("reasons") or []
        for x in rs:
            reasons[tag_of(x)] += 1
    sims = [r.get("metrics", {}).get("scene_similarity") for r in rows
            if isinstance(r.get("metrics"), dict)]
    sims = [s for s in sims if isinstance(s, (int, float))]
    low = [s for s in sims if s < 0.5]
    return {
        "name": name, "run": run.name, "n": len(rows),
        "counts": dict(counts), "reasons": dict(reasons),
        "sim_low": len(low), "sim_n": len(sims),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="?")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()

    targets = []
    if a.all:
        for sd in sorted(BOTRUNS.iterdir()):
            if not sd.is_dir() or sd.name.startswith("_"):
                continue
            runs = sorted([x for x in sd.iterdir() if x.is_dir()],
                          key=lambda x: x.name)
            if runs:
                targets.append((sd.name, runs[-1]))
    elif a.run_dir:
        p = Path(a.run_dir)
        targets.append((p.parent.name, p))
    else:
        print(__doc__)
        return 2

    agg = Counter()
    n_scene = 0
    for name, run in targets:
        s = summarize(run, name)
        if s is None:
            continue
        n_scene += 1
        c = s["counts"]
        tot = s["n"]
        bad = (c.get("fail", 0) + c.get("suspect", 0))
        agg.update(s["reasons"])
        if not a.all:
            print(f"{name}  run={s['run']}")
            print(f"  帧数 {tot}  判定 {c}")
            print(f"  相似度<0.5 的帧: {s['sim_low']}/{s['sim_n']}")
            print("  失败标签：" + ", ".join(f"{k}×{v}"
                  for k, v in sorted(s["reasons"].items(), key=lambda x: -x[1])))
        else:
            print(f"{name:<26} 帧={tot:<4} fail={c.get('fail',0):<4} "
                  f"suspect={c.get('suspect',0):<4} "
                  f"sim<0.5={s['sim_low']}")

    print(f"\n=== 汇总（{n_scene} 个场景）===")
    for k, v in agg.most_common(12):
        print(f"  {k:<20} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
