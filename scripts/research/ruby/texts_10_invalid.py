#!/usr/bin/env python3
"""texts_10: 无效/低价值条目分类统计（决定每条该不该留）。

分类（互斥优先级，一条只落一类）：
  A 占位符    —— 全由 ？/ー/-/空格 组成（游戏内动态覆盖或空槽）
  B 乱码       —— 解码文本里出现非常见字符、或可打印率极低
  C 极短碎片   —— 去除控制码后有效字符 <= 1（单字，翻译价值极低）
  D 碎片起点   —— 原文以小写假名/标点开头，且同地址+偏移处存在更长串（指向串中部）
  E 正常       —— 其余

同时统计：
  - 每条是否被某个 u32 指针真实指向（pointer_sources 为空且 ROM 无指针）
  - 内容在 ROM 内重复出现（另一份存在）

用法: python scripts/research/ruby/texts_10_invalid.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
OUT = ROOT / "work" / "_probe" / "texts_invalid.json"

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import BYTE_TO_CHAR, decode_pcs  # noqa: E402

PLACEHOLDER_CHARS = set("？?ー-‐―─…‥・ 　×▼")
KANA_LOWER_START = set("ぁぃぅぇぉゃゅょっ")
PUNCT_START = set("。、，！？：；・ー…‥）」』】〉》〕｝〕　 ")


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


def strip_ctrl(t: str) -> str:
    t = re.sub(r"\\CC[0-9A-Fa-f]+", "", t)
    t = re.sub(r"\\btn[0-9A-Fa-f]{2}", "", t)
    t = re.sub(r"\\\?[0-9A-Fa-f]{2}", "", t)
    t = re.sub(r"\\[0-9A-Fa-f]{2}", "", t)
    t = re.sub(r"\[[^\]]*\]", "", t)
    t = re.sub(r"\\(pk|mn|Po|Ke|Bl|Lo|Ck|Lv|qo|qc|sm|sf|au|ad|al|ar|pn|p|l|n|e|d|\+|<|>|\.|r)", "", t)
    t = t.replace("\n", "").replace("\r", "").replace("\\l", "")
    return t.strip()


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    entries = d["entries"]
    mods = d["modules"]

    # 全局 u32 指针目标集合（真实引用）
    ref_targets: set[int] = set()
    for off in range(0, len(rom) - 4, 1):
        if rom[off + 3] not in (0x08, 0x09):
            continue
        v = int.from_bytes(rom[off:off + 4], "little")
        if 0x08000000 <= v < 0x0A000000:
            ref_targets.add(v - 0x08000000)

    by_mod: dict[str, list] = defaultdict(list)
    for e in entries:
        by_mod[e.get("module")].append(e)

    print("=" * 118)
    print("A. 每模块无效/低价值条目分类")
    print("=" * 118)
    hdr = (f"{'module':<20} {'n':>6} {'占位':>6} {'乱码':>6} {'极短':>6} "
           f"{'碎片':>6} {'正常':>6} {'零引用':>7} {'可分删':>7}")
    print(hdr)
    print("-" * len(hdr))

    summary = {}
    all_buckets: dict[str, list] = defaultdict(list)
    for name, m in mods.items():
        els = by_mod.get(name, [])
        cnt = Counter()
        zero_ref = 0
        for e in els:
            orig = e.get("original") or ""
            core = strip_ctrl(orig)
            is_ptr = bool(e.get("is_pointer_based"))
            addr = to_int(e.get("address")) or 0
            off = addr - 0x08000000 if addr >= 0x08000000 else addr
            if e.get("pointer_sources"):
                has_ref = True
            else:
                has_ref = off in ref_targets
            if not has_ref:
                zero_ref += 1

            if core and set(core) <= PLACEHOLDER_CHARS:
                cnt["占位"] += 1
                all_buckets[f"{name}|占位"].append(e)
            elif core and any(ch not in BYTE_TO_CHAR.values() and ch not in "？?！？。、， 　" and
                              not ch.isprintable() for ch in core):
                cnt["乱码"] += 1
                all_buckets[f"{name}|乱码"].append(e)
            elif len(core) <= 1:
                cnt["极短"] += 1
                all_buckets[f"{name}|极短"].append(e)
            elif core and core[0] in (KANA_LOWER_START | PUNCT_START):
                cnt["碎片"] += 1
                all_buckets[f"{name}|碎片"].append(e)
            else:
                cnt["正常"] += 1
        deletable = cnt["占位"] + cnt["乱码"] + cnt["极短"]
        summary[name] = {
            "n": len(els), "placeholder": cnt["占位"], "garbage": cnt["乱码"],
            "too_short": cnt["极短"], "fragment": cnt["碎片"], "normal": cnt["正常"],
            "zero_ref": zero_ref, "deletable": deletable,
        }
        print(f"{name:<20} {len(els):>6} {cnt['占位']:>6} {cnt['乱码']:>6} "
              f"{cnt['极短']:>6} {cnt['碎片']:>6} {cnt['正常']:>6} "
              f"{zero_ref:>7} {deletable:>7}")

    print()
    print("=" * 118)
    print("B. 全 ROM 唯一内容重复检测（同 original_hex 出现 >1 次）")
    print("=" * 118)
    by_hex: dict[str, list] = defaultdict(list)
    for e in entries:
        h = (e.get("original_hex") or "").replace(" ", "").lower()
        if h:
            by_hex[h].append(e)
    dup_groups = {h: v for h, v in by_hex.items() if len(v) > 1}
    redundant = sum(len(v) - 1 for v in dup_groups.values())
    print(f"重复组 {len(dup_groups):,}，冗余条目 {redundant:,}")
    per_mod = Counter()
    for h, v in dup_groups.items():
        for e in v[1:]:
            per_mod[e.get("module")] += 1
    for m, c in per_mod.most_common():
        print(f"  {m:<22} {c:>6}")

    print()
    print("=" * 118)
    print("C. 样本：各模块「占位 / 乱码 / 极短」前几条")
    print("=" * 118)
    for key in sorted(all_buckets):
        mod, kind = key.split("|")
        if kind == "碎片":
            continue
        v = all_buckets[key]
        if not v:
            continue
        print(f"\n  [{mod} / {kind}] n={len(v)}")
        for e in v[:4]:
            print(f"    0x{to_int(e.get('address')):08X} "
                  f"{(e.get('original') or '')[:50]!r}")

    OUT.write_text(json.dumps(
        {"summary": summary,
         "dup_redundant_by_module": dict(per_mod),
         "dup_groups": len(dup_groups),
         "total_redundant": redundant},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
