#!/usr/bin/env python3
"""扫出「哪一组 RNG 值会在 Route118 草丛里触发遇敌」，供确定性遇敌使用。

原理：Route118 的遇敌判定在每走一步时读 gRngValue 并做骰子。
     我们没法在 Python 里复现 Gen3 的 RNG 推进，所以改用**实测扫描**：
     每轮钉一组候选值，走固定 6 格，记录是否遇敌（DISPCNT 7F60→BF40）。

本脚本只负责生成候选值清单文件和统计上一轮结果，不直接跑模拟器
（跑模拟器由 bot/run.py 完成，避免这里再起一套环境）。

用法：
  python scripts/plan_rng_sweep.py --emit      # 生成候选值清单
  python scripts/plan_rng_sweep.py --summarize <run_dir>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "work" / "rng_sweep.json"


def emit() -> int:
    # 只用高半字节变化的少量候选：Gen3 的遇敌骰子主要看低位，
    # 但为了保险同时覆盖「低 16 位全 0/全 1/交替」这类边界。
    cands = [
        0x00000000, 0x0000FFFF, 0x0000AAAA, 0x00005555,
        0x12345678, 0xDEADBEEF, 0x00000001, 0x7FFFFFFF,
        0x0000F000, 0x0000D000, 0x0000CCCC, 0x00003333,
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cands, indent=2), encoding="utf-8")
    print(f"[OK] 候选值 {len(cands)} 个 -> {OUT}")
    for c in cands:
        print(f"  0x{c:08X}")
    return 0


def summarize(run_dir: Path) -> int:
    """读一轮 bp5 场景的结果：哪一组值遇敌了。"""
    print(f"run_dir = {run_dir}")
    for side in ("origin", "translated"):
        csv = run_dir / side / "index.csv"
        if not csv.is_file():
            print(f"  {side}: 缺 index.csv")
            continue
        rows = []
        for line in csv.read_text(encoding="utf-8", errors="replace").splitlines():
            p = line.split(",")
            if len(p) >= 5 and p[0].isdigit():
                rows.append((p[2], p[4]))
        hit = [n for n, d in rows if d.upper() != "7F60"]
        print(f"  {side}: {len(rows)} 帧，非野外(DISPCNT≠7F60) 帧 = {hit[:10]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--summarize")
    a = ap.parse_args()
    if a.emit:
        return emit()
    if a.summarize:
        return summarize(Path(a.summarize))
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
