#!/usr/bin/env python3
"""texts_08: 语义校验——用项目自带 lexicon（日文→中文）核对定长表内容。

判据（不靠猜，靠词表命中率）：
  真实的名表槽，其解码文本应当能在对应 lexicon 里命中（或至少大部分命中）。
  如果 declared_start 处命中率低、而 start±k*stride 处命中率高，
  就说明 texts.json 的 start 偏了 k 个槽。

lexicon:
  招式名 -> 招式.json      招式说明 -> 招式.json (只查键)
  特性名 -> 特性.json      道具名   -> 道具.json
  属性名 -> 属性.json      宝可梦名 -> 图鉴.json
  性格名 -> 性格.json

用法: python scripts/research/ruby/texts_08_semantic.py
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
LEX = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "lexicon"

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402

# 模块 -> (lexicon 文件, 是否用键集合)
MODULE_LEX = {
    "招式名": ("招式.json", "keys"),
    "特性名": ("特性.json", "keys"),
    "道具名": ("道具.json", "keys"),
    "属性名": ("属性.json", "keys"),
    "宝可梦名": ("图鉴.json", "keys"),
    "性格名": ("性格.json", "keys"),
}


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


def load_keys(fn: str) -> set[str]:
    p = LEX / fn
    d = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(d, dict):
        return set(d.keys())
    return set(d)


def slot_text(rom: bytes, off: int, window: int, eos: int = 0xFF) -> str:
    limit = min(len(rom), off + window)
    for i in range(off, limit):
        if rom[i] == eos:
            return decode_pcs(rom[off:i + 1])
    return ""


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]

    print("=" * 112)
    print("语义校验：声明起点 vs 滑动起点的词表命中率")
    print("=" * 112)

    results = {}
    for name, (fn, _mode) in MODULE_LEX.items():
        m = mods.get(name)
        if not m:
            continue
        keys = load_keys(fn)
        r = m.get("read") or {}
        start = to_int(m.get("start"))
        end = to_int(m.get("end"))
        stride = r.get("stride") or r.get("entry_size")
        eos = int(r.get("eos", 0xFF))
        no = int(r.get("name_offset") or 0)
        n = (end - start + 1) // stride

        print(f"\n--- {name}  lexicon={fn}({len(keys)} 键) start=0x{start:06X} "
              f"stride={stride} n={n} name_offset={no}")
        rows = []
        for delta in range(-3, 4):
            cand = start + delta * stride
            if cand < 0:
                continue
            hit = 0
            ex = []
            for k in range(n):
                off = cand + k * stride + no
                t = slot_text(rom, off, stride - no, eos)
                if t in keys:
                    hit += 1
                    if len(ex) < 3:
                        ex.append(t)
            rows.append((hit, delta, cand, ex))
        rows.sort(reverse=True)
        for hit, delta, cand, ex in rows[:4]:
            mark = "  <== declared" if delta == 0 else ""
            print(f"    命中 {hit:>3}/{n} ({hit/n:5.1%})  delta={delta:+d} "
                  f"start=0x{cand:06X}{mark}  例={ex}")
        top_hit, top_delta, top_addr, _ = rows[0]
        declared = next((h for h, dlt, _, _ in rows if dlt == 0), 0)
        results[name] = {
            "declared_start": start, "declared_hit": declared,
            "best_start": top_addr, "best_hit": top_hit,
            "delta_slots": top_delta, "n": n, "lexicon_size": len(keys),
        }

    out = ROOT / "work" / "_probe" / "texts_semantic.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n" + "=" * 112)
    print("汇总")
    print("=" * 112)
    for name, f in results.items():
        flag = ""
        if f["delta_slots"] != 0 and f["best_hit"] > f["declared_hit"]:
            flag = f"  <== 建议起点 0x{f['best_start']:06X} ({f['delta_slots']:+d} 格)"
        print(f"  {name:<8} 声明命中 {f['declared_hit']:>3}/{f['n']} "
              f"({f['declared_hit']/f['n']:5.1%})  最佳 {f['best_hit']:>3} "
              f"delta={f['delta_slots']:+d}{flag}")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
