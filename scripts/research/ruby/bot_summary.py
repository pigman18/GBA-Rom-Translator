#!/usr/bin/env python3
"""汇总 bot verify 结果：只看判定统计，不打印逐帧细节。

用法：
    python scripts/research/ruby/bot_summary.py [scene]
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
BOT = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"


def main() -> int:
    scenes = sys.argv[1:] or [
        d.name for d in BOT.iterdir() if d.is_dir()
    ]
    for scene in scenes:
        runs = sorted((BOT / scene).glob("*"))
        runs = [r for r in runs if r.is_dir()]
        if not runs:
            continue
        run = runs[-1]
        vj = run / "verdict.json"
        if not vj.is_file():
            print(f"{scene}: 无 verdict.json")
            continue
        d = json.loads(vj.read_text(encoding="utf-8"))

        frames = d.get("frames") or d.get("results") or []
        if not frames and isinstance(d, list):
            frames = d

        verdicts = Counter(f.get("verdict") for f in frames)
        reasons = Counter()
        for f in frames:
            for r in (f.get("reasons") or []):
                reasons[(r.get("dim"), r.get("level"))] += 1

        sims = [f.get("metrics", {}).get("scene_similarity")
                for f in frames if f.get("metrics")]
        sims = [s for s in sims if s is not None]
        med = sorted(sims)[len(sims) // 2] if sims else 0

        print(f"\n=== {scene} ===")
        print(f"  帧数 {len(frames)}  相似度中位 {med:.4f}")
        print(f"  判定: " + "  ".join(f"{k}={v}" for k, v in
                                     verdicts.most_common()))
        if reasons:
            print(f"  原因(前 6):")
            for (dim, lvl), c in reasons.most_common(6):
                print(f"    {dim}/{lvl}: {c}")

        # 汉化是否生效（retext_px > 0 表示同位置换字）
        retext = sum(f.get("metrics", {}).get("retext_px", 0) for f in frames)
        print(f"  汉化像素(retext_px 合计): {retext:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
