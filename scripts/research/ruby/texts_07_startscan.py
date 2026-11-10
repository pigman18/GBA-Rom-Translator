#!/usr/bin/env python3
"""texts_07: 定长表（stride/struct）真实起点扫描。

思路：对一个定长表的候选起点做小窗口扫描（declared_start ± K*stride），
每个候选按模块自己的 eos 语义统计「合法槽」数，取合法数最高者作为真实起点。
  合法槽 = 在槽窗内能读到 eos，且 eos 前每个字节都是合法字形或控制字节。

这直接给出「texts.json 的 start 是否偏了、偏了几个槽」的字节级证据，
不依赖符号表、不靠猜。

用法: python scripts/research/ruby/texts_07_startscan.py
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import BYTE_TO_CHAR  # noqa: E402


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


def slot_valid(rom: bytes, off: int, window: int, eos: int) -> bool:
    """槽内能否读到 eos，且 eos 前全为合法字形/控制字节。"""
    limit = min(len(rom), off + window)
    if off >= limit:
        return False
    for i in range(off, limit):
        b = rom[i]
        if b == eos:
            return i > off
        if b >= 0xFA:
            if b == eos:
                return i > off
            continue
        if b in BYTE_TO_CHAR:
            continue
        return False
    return False


def score(rom: bytes, start: int, stride: int, n: int, eos: int,
          name_offset: int = 0) -> int:
    ok = 0
    for k in range(n):
        off = start + k * stride + name_offset
        w = stride - name_offset
        if slot_valid(rom, off, w, eos):
            ok += 1
    return ok


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]
    by_mod: dict[str, int] = {}
    for e in d["entries"]:
        by_mod[e.get("module")] = by_mod.get(e.get("module"), 0) + 1

    print("=" * 120)
    print("定长表起点扫描：在 declared_start 附近按格子滑动，找合法槽最多的起点")
    print("=" * 120)

    findings = {}
    for name, m in mods.items():
        if m.get("type") not in ("stride", "struct"):
            continue
        r = m.get("read") or {}
        start = to_int(m.get("start"))
        end = to_int(m.get("end"))
        stride = r.get("stride") or r.get("entry_size")
        if not start or not stride:
            continue
        eos_raw = r.get("eos", 0xFF)
        eos = 0xFF if eos_raw is None else int(eos_raw)
        name_offset = int(r.get("name_offset") or 0)
        n_cfg = by_mod.get(name, 0)
        n_slots = (end - start + 1) // stride

        print(f"\n--- {name}  type={m.get('type')} start=0x{start:06X} "
              f"stride={stride} eos=0x{eos:02X} name_offset={name_offset} "
              f"slots={n_slots} cfg_entries={n_cfg}")

        # 在 ±4 格内滑动
        best = []
        for delta in range(-4, 5):
            cand = start + delta * stride
            if cand < 0:
                continue
            n = n_slots
            s = score(rom, cand, stride, n, eos, name_offset)
            best.append((s, delta, cand, n))
        best.sort(reverse=True)
        base_s = score(rom, start, stride, n_slots, eos, name_offset)
        print(f"    declared 起点合法槽: {base_s}/{n_slots}")
        print("    候选（合法槽数 / 偏移格 / 起点）：")
        for s, delta, cand, n in best[:5]:
            mark = "  <== declared" if delta == 0 else ""
            print(f"      {s:>4}/{n}  delta={delta:+d}  start=0x{cand:06X}{mark}")

        top_s, top_delta, top_addr, _ = best[0]
        findings[name] = {
            "type": m.get("type"),
            "declared_start": start,
            "best_start": top_addr,
            "delta_slots": top_delta,
            "declared_ok": base_s,
            "best_ok": top_s,
            "slots": n_slots,
            "stride": stride,
            "eos": eos,
            "name_offset": name_offset,
        }

    out = ROOT / "work" / "_probe" / "texts_startscan.json"
    out.write_text(json.dumps(findings, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {out}")

    print("\n" + "=" * 120)
    print("汇总：起点明显偏移（|delta|>=1 且合法槽显著提升）")
    print("=" * 120)
    for name, f in findings.items():
        if f["delta_slots"] != 0 and f["best_ok"] > f["declared_ok"]:
            print(f"  {name:<20} 声明 0x{f['declared_start']:06X} "
                  f"-> 实测 0x{f['best_start']:06X} ({f['delta_slots']:+d} 格)  "
                  f"合法 {f['declared_ok']}/{f['slots']} -> {f['best_ok']}/{f['slots']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
