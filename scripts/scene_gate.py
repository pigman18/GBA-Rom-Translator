#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scene_gate.py — 全场景验证闸门（2026-11-05）

## 为什么需要这个脚本

存在理由（用户的直接质问：「是得我一个个跟进吗？你那边是没有验证手段吗？」）：

  · `bot/run.py` 一次只跑一个场景；
  · `scripts/run_verify_batch.py` 会批量跑，但**不记录 ROM 指纹**——
    换了 ROM 之后，旧的 verdict.json 还在，看起来「验过了」，其实验的是旧版本。
    实测：121 个场景里只有 1 个跑在当前 ROM 上，116 个跑在旧 ROM。
  · `bot/accept.py` 只聚合**已存在**的 verdict，不会主动补跑。

本脚本把「跑」和「判」串起来，并且强制 ROM 指纹绑定：

  1. 算出当前 ROM 的 sha256；
  2. 遍历全部场景，读各自最新 run 的 manifest.json 里记录的 translated sha256；
  3. 不匹配 ⇒ 标 stale，**必须重跑**（除非显式 --skip-stale）；
  4. 重跑后跑 verify，聚合出四张表：崩溃 / 空白 / 未汉化 / 通过。

## 用法

    # 全量重跑（换 ROM 后必须这样跑）
    python scripts/scene_gate.py --all

    # 只看指纹与判定状态，不跑模拟器
    python scripts/scene_gate.py --all --dry-run

    # 只跑指定场景
    python scripts/scene_gate.py --list options,pokemon_menu,bag

    # 强制重跑（即使指纹匹配）
    python scripts/scene_gate.py --all --force

退出码：0 全部通过；1 有 fail；2 有 stale/suspect；3 运行错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
GAME = "POKEMON_RUBY_AXVJ00"
SCENES = ROOT / "bot" / "scenes" / GAME
BOTRUNS = ROOT / "work" / GAME / "bot"
ROM = ROOT / "roms" / "outputs" / f"{GAME}_translated.gba"
SAV = ROOT / "work" / "_probe" / "teleport.sav"
PY = sys.executable

# 与 run_verify_batch.py 保持同一口径：这些不是场景，是工具脚本。
TOOLS = {
    "font_capture", "font_dump", "font_probe", "font_talk",
    "images_dump", "ref_probe", "page_sweep", "shop",
    "fr_menu", "fr_pair", "fr_pair2", "fr_text", "_diag", "_diag2",
}

# 闸门关心的缺陷维度（来自 bot/verify.py 的 reasons.dim）
CRASH_DIMS = {"s_crash", "s_reset", "s_diverged", "g_black"}


def rom_sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scene_names() -> list[str]:
    return sorted(
        f.stem for f in SCENES.glob("*.lua")
        if f.stem != "main" and not f.stem.startswith("_") and f.stem not in TOOLS
    )


def latest_run(name: str) -> Path | None:
    d = BOTRUNS / name
    if not d.is_dir():
        return None
    runs = sorted((x for x in d.iterdir() if x.is_dir()), key=lambda x: x.name)
    return runs[-1] if runs else None


def run_state(name: str, cur_sha: str) -> dict:
    """读某场景最新 run 的状态：是否有 verdict、ROM 指纹是否匹配。"""
    r = latest_run(name)
    if r is None:
        return {"scene": name, "run": None, "stale": True,
                "reason": "从未采集", "verdict": None}
    mf = r / "manifest.json"
    if not mf.is_file():
        return {"scene": name, "run": r.name, "stale": True,
                "reason": "无 manifest", "verdict": None}
    try:
        m = json.loads(mf.read_text(encoding="utf-8"))
    except Exception:
        return {"scene": name, "run": r.name, "stale": True,
                "reason": "manifest 损坏", "verdict": None}
    sha = ((m.get("roms") or {}).get("translated") or {}).get("sha256")
    vj = r / "verdict.json"
    verdict = None
    if vj.is_file():
        try:
            verdict = json.loads(vj.read_text(encoding="utf-8")).get("verdict")
        except Exception:
            verdict = None
    return {
        "scene": name, "run": r.name,
        "stale": sha != cur_sha,
        "reason": "" if sha == cur_sha else f"ROM 指纹不符（{str(sha)[:12]} != {cur_sha[:12]}）",
        "verdict": verdict,
    }


def run_scene(name: str, timeout: int) -> tuple[bool, str]:
    cmd = [PY, "-X", "utf8", str(ROOT / "bot" / "run.py"), GAME, name,
           "--save", str(SAV), "--timeout", str(timeout)]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    ok = "frame-aligned" in (p.stdout or "")
    msg = "" if ok else ((p.stderr or "") + (p.stdout or ""))[-300:].strip()
    return ok, msg


def read_verdict_detail(name: str) -> dict:
    """读出最新 run 的 verdict 明细，供闸门分类。"""
    r = latest_run(name)
    if r is None or not (r / "verdict.json").is_file():
        return {}
    try:
        v = json.loads((r / "verdict.json").read_text(encoding="utf-8"))
    except Exception:
        return {}
    dims = Counter()
    for f in v.get("frames", []):
        for reason in f.get("reasons", []):
            if reason.get("level") == "fail":
                dims[reason.get("dim", "?")] += 1
    return {"verdict": v.get("verdict"), "counts": v.get("counts") or {},
            "fail_dims": dict(dims), "run": r.name}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="全部场景")
    ap.add_argument("--list", default=None, help="逗号分隔的场景名")
    ap.add_argument("--dry-run", action="store_true", help="只报状态，不跑模拟器")
    ap.add_argument("--force", action="store_true", help="指纹匹配也重跑")
    ap.add_argument("--skip-stale", action="store_true", help="不重跑 stale（不推荐）")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--json", default=str(ROOT / "work" / "scene_gate.json"))
    a = ap.parse_args()

    if not ROM.is_file():
        print(f"[ERR] 产物 ROM 不存在: {ROM}")
        return 3
    cur = rom_sha(ROM)
    print(f"[gate] ROM {ROM.name}  sha256={cur[:16]}  "
          f"{ROM.stat().st_size} B  mtime={time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ROM.stat().st_mtime))}")

    if a.list:
        names = [x.strip() for x in a.list.split(",") if x.strip()]
    elif a.all:
        names = scene_names()
    else:
        print(__doc__)
        return 3

    if not SAV.is_file():
        print(f"[ERR] 共用存档不存在: {SAV}")
        return 3

    states = [run_state(n, cur) for n in names]
    stale = [s for s in states if s["stale"]]
    fresh = [s for s in states if not s["stale"]]
    print(f"[gate] 场景 {len(names)}：当前 ROM 上已跑 {len(fresh)}，"
          f"stale {len(stale)}")

    if a.dry_run:
        for s in states:
            flag = "STALE" if s["stale"] else (s["verdict"] or "no-verdict").upper()
            print(f"  {flag:12s} {s['scene']:26s} {s['reason']}")
        return 0

    todo = [s["scene"] for s in states if a.force or s["stale"]]
    if a.skip_stale:
        todo = []
    if todo:
        print(f"[gate] 需重跑 {len(todo)} 个场景（预计较久，逐条输出）\n")
        err = []
        t0 = time.time()
        for i, n in enumerate(todo, 1):
            ok, msg = run_scene(n, a.timeout)
            el = time.time() - t0
            print(f"[{i:>3}/{len(todo)}] {'OK ' if ok else 'ERR'} {n}"
                  f"  ({el:.0f}s)", flush=True)
            if not ok:
                err.append((n, msg))
        if err:
            print(f"\n[gate] 运行失败 {len(err)} 个：")
            for n, m in err:
                print(f"  {n}: {m.splitlines()[0] if m else ''}")

    # ── 聚合 ────────────────────────────────────────────────────────────
    result = {}
    for n in names:
        st = run_state(n, cur)
        detail = read_verdict_detail(n)
        result[n] = {**st, **detail}

    def bucket(pred):
        return [n for n, d in result.items() if pred(d)]

    crashed = bucket(lambda d: not d["stale"] and
                     (set((d.get("fail_dims") or {})) & CRASH_DIMS))
    black = bucket(lambda d: not d["stale"] and
                   "g_black" in (d.get("fail_dims") or {}))
    failed = bucket(lambda d: not d["stale"] and d.get("verdict") == "fail"
                    and n_not_in(n, crashed))
    suspect = bucket(lambda d: not d["stale"] and d.get("verdict") == "suspect")
    passed = bucket(lambda d: not d["stale"] and d.get("verdict") == "pass")
    still_stale = bucket(lambda d: d["stale"])

    bar = "=" * 78
    print("\n" + bar)
    print(f"闸门汇总  {GAME}   ROM sha256={cur[:16]}")
    print(bar)
    print(f"  场景总数      : {len(names)}")
    print(f"  已跑(当前ROM) : {len(names) - len(still_stale)}")
    print(f"  仍 stale      : {len(still_stale)}")
    print(f"  pass          : {len(passed)}")
    print(f"  suspect       : {len(suspect)}")
    print(f"  fail          : {len(failed)}")
    print(f"  ★ 崩溃/空白   : {len(crashed)}  ({', '.join(crashed[:8])}"
          f"{' …' if len(crashed) > 8 else ''})")

    if crashed:
        print("\n" + "-" * 78)
        print("崩溃/空白场景（最高优先级）")
        print("-" * 78)
        for n in crashed:
            d = result[n]
            print(f"  {n:26s} {d.get('run')}")
            for dim, cnt in (d.get("fail_dims") or {}).items():
                if dim in CRASH_DIMS:
                    print(f"      {dim}: {cnt} 帧")

    if a.json:
        Path(a.json).write_text(json.dumps({
            "rom_sha256": cur,
            "rom_path": str(ROM),
            "total": len(names),
            "passed": passed,
            "suspect": suspect,
            "failed": failed,
            "crashed": crashed,
            "stale": still_stale,
            "detail": result,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[out] {a.json}")

    if still_stale:
        return 2
    if crashed or failed:
        return 1
    if suspect:
        return 2
    return 0


def n_not_in(n: str, pool: list) -> bool:
    return n not in pool


if __name__ == "__main__":
    raise SystemExit(main())
