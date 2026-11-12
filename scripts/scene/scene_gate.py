#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scene_gate.py — 全场景采集闸门（ROM 指纹绑定）

`bot/verify.py` / `bot/accept.py` 已删除。本脚本只负责：

  1. 算出当前产物 ROM 的 sha256；
  2. 对照各场景最新 run 的 manifest.roms.translated.sha256；
  3. stale / 缺失 ⇒ 重跑 `bot/run.py` 采集；
  4. 汇总「已采集 / stale / 采集失败」。

画面是否合格（撞 UI / 日文→中文或不丢字 / 文字颜色）按 `bot/SKILL.md`
由子代理看图判定，本脚本不产出伪分。

用法：

    python scripts/scene/scene_gate.py --all
    python scripts/scene/scene_gate.py --all --dry-run
    python scripts/scene/scene_gate.py --list options,pokemon_menu,bag
    python scripts/scene/scene_gate.py --all --force

退出码：0 全部已采集且指纹匹配；1 有采集失败；2 仍有 stale；3 运行错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent.parent
GAME = "POKEMON_RUBY_AXVJ00"
SCENES = ROOT / "bot" / "scenes" / GAME
BOTRUNS = ROOT / "work" / GAME / "bot"
ROM = ROOT / "roms" / "outputs" / f"{GAME}_translated.gba"
SAV = ROOT / "work" / "_probe" / "teleport.sav"
PY = sys.executable

TOOLS = {
    "font_capture", "font_dump", "font_probe", "font_talk",
    "images_dump", "ref_probe", "page_sweep", "shop",
    "fr_menu", "fr_pair", "fr_pair2", "fr_text", "_diag", "_diag2",
}


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
    r = latest_run(name)
    if r is None:
        return {"scene": name, "run": None, "stale": True,
                "reason": "从未采集", "pairs": 0}
    mf = r / "manifest.json"
    if not mf.is_file():
        return {"scene": name, "run": r.name, "stale": True,
                "reason": "无 manifest", "pairs": 0}
    try:
        m = json.loads(mf.read_text(encoding="utf-8"))
    except Exception:
        return {"scene": name, "run": r.name, "stale": True,
                "reason": "manifest 损坏", "pairs": 0}
    sha = ((m.get("roms") or {}).get("translated") or {}).get("sha256")
    pairs = len(m.get("pairs") or [])
    return {
        "scene": name, "run": r.name,
        "stale": sha != cur_sha,
        "reason": "" if sha == cur_sha else f"ROM 指纹不符（{str(sha)[:12]} != {cur_sha[:12]}）",
        "pairs": pairs,
    }


def run_scene(name: str, timeout: int) -> tuple[bool, str]:
    cmd = [PY, "-X", "utf8", str(ROOT / "bot" / "run.py"), GAME, name,
           "--save", str(SAV), "--timeout", str(timeout)]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    ok = "frame-aligned" in (p.stdout or "")
    msg = "" if ok else ((p.stderr or "") + (p.stdout or ""))[-300:].strip()
    return ok, msg


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
    print("[gate] review policy: bot/SKILL.md (no verify.py)")

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
    print(f"[gate] 场景 {len(names)}：当前 ROM 上已采集 {len(fresh)}，"
          f"stale {len(stale)}")

    if a.dry_run:
        for s in states:
            flag = "STALE" if s["stale"] else f"CAPTURED({s['pairs']})"
            print(f"  {flag:16s} {s['scene']:26s} {s['reason']}")
        return 0

    todo = [s["scene"] for s in states if a.force or s["stale"]]
    if a.skip_stale:
        todo = []
    err = []
    if todo:
        print(f"[gate] 需重跑 {len(todo)} 个场景（预计较久，逐条输出）\n")
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

    result = {n: run_state(n, cur) for n in names}
    still_stale = [n for n, d in result.items() if d["stale"]]
    captured = [n for n, d in result.items() if not d["stale"] and d["pairs"] > 0]
    empty = [n for n, d in result.items() if not d["stale"] and d["pairs"] == 0]

    bar = "=" * 78
    print("\n" + bar)
    print(f"采集汇总  {GAME}   ROM sha256={cur[:16]}")
    print(bar)
    print(f"  场景总数      : {len(names)}")
    print(f"  已采集(当前ROM): {len(captured)}")
    print(f"  仍 stale      : {len(still_stale)}")
    print(f"  空 pairs      : {len(empty)}")
    print("  画面验收      : 按 bot/SKILL.md 子代理看图（本脚本不判 pass/fail）")

    if a.json:
        Path(a.json).write_text(json.dumps({
            "rom_sha256": cur,
            "rom_path": str(ROM),
            "total": len(names),
            "captured": captured,
            "empty": empty,
            "stale": still_stale,
            "capture_errors": [n for n, _ in err],
            "detail": result,
            "review": "bot/SKILL.md",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[out] {a.json}")

    if err or empty:
        return 1
    if still_stale:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
