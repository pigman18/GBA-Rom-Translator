"""全图鉴批量采集：重用官方 fix_encounter.py，不自己重写槽逻辑。

【为什么调官方工具而不是自己 pack】
  槽结构 `struct WildPokemon { u8 minLevel; u8 maxLevel; u16 species; }`，
  以及「表定位」「写完读回校验」都在 scripts/encounter/fix_encounter.py 里
  做了实测与断言。我上一版自己 pack 时把 level/species 顺序搞反，
  写出的 species 变成 3084 —— 官方工具不会犯这个错，直接复用它。

【场景选择】
  `battle_scent`（香甜气息强制遇敌）就是为「改遇敌表固定 species」设计的，
  见 bot/scenes/POKEMON_RUBY_AXVJ00/battle_scent.lua 头注：
    不靠钉 RNG、不靠写 gBattleMons species，而是改遇敌表；
    12 槽同物种 ⇒ ChooseWildMonIndex_Land() 无论落哪档结果都一样。

【产出】
  work/POKEMON_RUBY_AXVJ00/sweep/<sid>/translated.png
  work/POKEMON_RUBY_AXVJ00/sweep/index.json
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
SWEEP = ROOT / "work/POKEMON_RUBY_AXVJ00/sweep"
INDEX = ROOT / "work/_species_index.json"
# 官方工具与产物路径从 game.json 读，避免在 .py 里硬编码游戏 ID（DONT.md）
GAME_JSON = ROOT / "configs/POKEMON_RUBY_AXVJ00/game.json"


def load_paths() -> tuple[Path, Path, Path, str]:
    cfg = json.loads(GAME_JSON.read_text(encoding="utf-8"))
    gid = cfg.get("gameId") or cfg.get("id") or "POKEMON_RUBY_AXVJ00"
    rom = ROOT / "roms/outputs" / f"{gid}_translated.gba"
    origin = ROOT / "roms/origin/POKEMON_RUBY_AXVJ00.gba"
    sav = ROOT / "roms/outputs" / f"{gid}_translated.sav"
    return rom, origin, sav, gid


def fix_encounter(roms: list[Path], species: int) -> bool:
    """调官方工具把 land 表 12 槽固定为同一种 species（自带读回校验）。"""
    cmd = [sys.executable, "scripts/encounter/fix_encounter.py", "apply",
           "--species", str(species), "--rom", *[str(r) for r in roms]]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(ROOT))
    out = (p.stdout or "") + (p.stderr or "")
    ok = "已固定为" in out and "[MISMATCH]" not in out and "定位 species" not in out
    if not ok:
        print(f"    [!] fix_encounter 异常:\n{out[-400:]}")
    return ok


def run_bot(gid: str, save: Path, o: Path, t: Path, sid: int) -> Path | None:
    p = subprocess.run(
        [sys.executable, "bot/run.py", gid, "battle_scent",
         "--save", str(save), "--origin", str(o), "--translated", str(t),
         "--timeout", "150"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT),
    )
    out = (p.stdout or "") + (p.stderr or "")
    m = re.search(r"frame-aligned pairs: (.+?manifest\.json)", out)
    if not m:
        print(f"    [!] bot 无输出: {out.strip()[-300:]}")
        return None
    run_dir = Path(m.group(1)).parent
    dst = SWEEP / str(sid)
    dst.mkdir(parents=True, exist_ok=True)
    # 采最后一帧（血条稳定态）
    frames = sorted(int(f.stem) for f in (run_dir / "translated").glob("*.png")
                    if f.stem.isdigit())
    if not frames:
        return None
    last = frames[-1]
    for side in ("origin", "translated"):
        src = run_dir / side / f"{last:03d}.png"
        if src.exists():
            shutil.copy2(src, dst / f"{side}.png")
    (dst / "meta.json").write_text(json.dumps(
        {"sid": sid, "frame": last, "run": str(run_dir)}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=386)
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    rom, origin, sav, gid = load_paths()
    for p in (rom, origin, sav):
        if not p.exists():
            print(f"[ERR] 缺文件 {p}")
            return 1

    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    targets = ([int(x) for x in args.only.split(",") if x.strip()]
               if args.only else list(range(args.start, args.end + 1)))

    SWEEP.mkdir(parents=True, exist_ok=True)
    stage = ROOT / "bot/.stage"
    stage.mkdir(parents=True, exist_ok=True)
    rec_path = SWEEP / "index.json"
    rec = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.exists() else {}

    # ★ 以「实际文件是否存在」为准，不信任 index 的 CAPTURED 标记。
    #   踩过：清目录后 index 仍写 CAPTURED，后续跑全部跳过，最终 299 条记录空转。
    for k in list(rec):
        d = Path(rec[k].get("dir", ""))
        if not (d / "translated.png").exists():
            del rec[k]
    rec_path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已有有效采集 {len(rec)} 只")

    print(f"目标 {len(targets)} 只，产物 {rom.name}")
    ok = fail = 0
    for n, sid in enumerate(targets, 1):
        meta = idx.get(str(sid))
        if not meta:
            continue
        if str(sid) in rec:
            continue
        zh = meta["zh"]
        print(f"[{n}/{len(targets)}] {sid:>3} {zh} ({meta['chars']}字)")

        t = stage / f"sw_t_{sid}.gba"
        o = stage / f"sw_o_{sid}.gba"
        try:
            shutil.copy2(rom, t)
            shutil.copy2(origin, o)
            if not fix_encounter([t, o], sid):
                fail += 1
                rec[str(sid)] = {"zh": zh, "chars": meta["chars"], "status": "PATCHFAIL"}
                continue
            d = run_bot(gid, sav, o, t, sid)
            if d is None:
                fail += 1
                rec[str(sid)] = {"zh": zh, "chars": meta["chars"], "status": "NORUN"}
                continue
            ok += 1
            rec[str(sid)] = {"zh": zh, "chars": meta["chars"],
                             "status": "CAPTURED", "dir": str(d)}
        finally:
            t.unlink(missing_ok=True)
            o.unlink(missing_ok=True)
            rec_path.write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                                encoding="utf-8")

    print(f"\n完成：{ok} 成功 / {fail} 失败 -> {rec_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
