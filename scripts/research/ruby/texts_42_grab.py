#!/usr/bin/env python3
"""texts_42: 用「剧情 fallback 通道」的等价 filter 给新模块抢归属（验证 3.3 思路）。

texts_41 结论：
  · 0x3B2 那 68 条没有指针，靠剧情的 fallback_filters 收进来
  · fallback_filters = require_pointer(True) + real_ref(True) + dialogue_shape + garbage
  · dialogue_shape 的 pointer_ok=false 允许无指针文本通过 → 这就是入口

所以新模块要抢这批，应当沿用同样的 fallback 通道，而不是指针 filter。

本脚本对比三种「新模块」定义在同一区段的产出，找精确的那个：
  A. scan + 剧情同款 fallback_filters
  B. scan + dialogue_shape 单独
  C. scan + dialogue_shape + garbage_heuristic

用法: python scripts/research/ruby/texts_42_grab.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.path.insert(0, str(".")) if False else (sys.path,)):
    pass

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

sys.path.insert(0, str(ROOT / "src"))
import util.texts_patcher as TP  # noqa: E402


def to_int(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    try:
        return int(s, 16) if s.lower().startswith("0x") else int(s, 10)
    except ValueError:
        return None


def off_of(e) -> int:
    return to_int(e.get("address")) - 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    ptr_index = TP._build_ptr_index(rom)

    ZONES = {"词库-0x3B2": (0x3B2000, 0x3B29FF),
             "战斗提示": (0x3DA000, 0x3DBFFF)}

    story_fb = d["modules"]["剧情"].get("fallback_filters") or []
    print("剧情 fallback_filters:", [f.get("id") for f in story_fb])

    # 从剧情 fallback 里挑出「允许无指针」的那条
    shape = [f for f in story_fb if f.get("type") == "dialogue_shape_filter"]
    garb = [f for f in story_fb if f.get("type") == "garbage_heuristic_filter"]

    VARIANTS = {
        "A 剧情同款fallback": story_fb,
        "B dialogue_shape": shape,
        "C dialogue_shape+garbage": shape + garb,
        "D 裸扫": None,
    }

    for zname, (lo, hi) in ZONES.items():
        target = {off_of(e) for e in d["entries"] if lo <= off_of(e) <= hi}
        print()
        print("=" * 112)
        print(f"{zname}  0x{lo:06X}..0x{hi:06X}  文件现有 {len(target)} 条")
        print("=" * 112)
        print(f"  {'变体':<24} {'收到':>6} {'命中现有':>8} {'精确率':>7} "
              f"{'覆盖率':>7}")
        print("  " + "-" * 62)
        best = None
        for vname, vflt in VARIANTS.items():
            m = {"id": zname, "type": "scan",
                 "start": f"0x{lo:X}", "end": f"0x{hi:X}"}
            if vflt is not None:
                m["fallback_filters"] = vflt
            try:
                out = TP.extract_module(rom, m, "AXVJ", ptr_index=ptr_index,
                                        filters=None)
            except Exception as exc:  # noqa: BLE001
                print(f"  {vname:<24} 异常 {exc}")
                continue
            got = {off_of(e) for e in out}
            inter = got & target
            prec = len(inter) / len(got) if got else 0
            rec = len(inter) / len(target) if target else 0
            print(f"  {vname:<24} {len(got):>6} {len(inter):>8} {prec:>6.0%} "
                  f"{rec:>6.0%}")
            if best is None or (len(inter), -len(got)) > best[0]:
                best = ((len(inter), -len(got)), vname, got)
        if best:
            _, bname, bgot = best
            print(f"\n  最佳: {bname}")
            extra = sorted(bgot - target)[:8]
            if extra:
                print(f"    会多收 {len(bgot - target)} 条，样本: {[hex(x) for x in extra]}")
            miss = sorted(target - bgot)[:8]
            if miss:
                print(f"    会漏 {len(target - bgot)} 条，样本: {[hex(x) for x in miss]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
