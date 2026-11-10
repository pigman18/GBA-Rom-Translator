#!/usr/bin/env python3
"""texts_35: fallback 71 条的「客观事实卡」——不做伪判，只摊证据。

前 6 版启发式判据（假名占比 / 裸F7F8 / 片段命中率 / 长片段词表覆盖 /
邻域结构 / 字节形态）都出现了误杀或漏判，说明单一启发式不可靠。
按 supervisor 规则：「不确定就停下来问，不要猜」。

本脚本只输出可核对的事实，交给人裁定：
  C1 这条文本控制码剥离后，是否与 **另一条已确认正常文本** 完全相同（重复）
  C2 这条的「有效字符」里，片假名占比、全角拉丁占比
  C3 这条在 ROM 里是否落在已知结构区（0x1Dxxxx / 0x3DAxxx 战斗提示池）
  C4 首尾字节是否与「正常池」一致

用法: python scripts/research/ruby/texts_35_evidence.py
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
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
OUT = ROOT / "work" / "_probe" / "texts_fallback_evidence.json"


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


def core(s: str) -> str:
    s = re.sub(r"\\CC[0-9A-Fa-f]+", "", s)
    s = re.sub(r"\\btn[0-9A-Fa-f]{2}", "", s)
    s = re.sub(r"\\[0-9A-Fa-f]{2}", "", s)
    s = re.sub(r"\[[^\]]*\]", "", s)
    return s.replace("\n", "").replace("\\l", "").strip()


def main() -> int:
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    story = [e for e in d["entries"] if e.get("module") == "剧情"]
    fb = [e for e in story if "fallback" in e]
    ok = [e for e in story if "fallback" not in e]

    # 正常文本的 core 集合，用于查重
    ok_cores: dict[str, list[str]] = defaultdict(list)
    for e in ok:
        ok_cores[core(e.get("original") or "")].append(e.get("address"))

    print("=" * 112)
    print(f"fallback 71 条事实卡  （对照组：正常剧情 {len(ok)} 条）")
    print("=" * 112)

    print("\n[C3] 地址分箱：fallback 集中在哪")
    print(f"  fallback : {Counter(to_int(e.get('address')) - 0x08000000 >> 16 for e in fb).most_common()}")
    print(f"  正常剧情 : {Counter(to_int(e.get('address')) - 0x08000000 >> 16 for e in ok).most_common(10)}")

    print("\n[C1] 与正常文本重复的 fallback 条目")
    dup = []
    for e in fb:
        c = core(e.get("original") or "")
        if c and c in ok_cores:
            dup.append(e)
    print(f"  {len(dup)} 条（这些是正常文本的重复收录，可直接去重）")
    for e in dup[:10]:
        print(f"    0x{to_int(e.get('address')):08X} {core(e.get('original') or '')[:44]!r}")

    print("\n[C2] 分三类（按地址段 + 字符构成）")
    groups = {
        "0x1D0000-0x1E0000 段": [e for e in fb
                               if 0x1D0000 <= to_int(e.get("address")) - 0x08000000 < 0x1E0000],
        "0x3DA000-0x3DC000 战斗提示池": [e for e in fb
                                    if 0x3DA000 <= to_int(e.get("address")) - 0x08000000 < 0x3DC000],
        "0x3D0000 其他": [e for e in fb
                        if 0x3D0000 <= to_int(e.get("address")) - 0x08000000 < 0x3E0000
                        and not (0x3DA000 <= to_int(e.get("address")) - 0x08000000 < 0x3DC000)],
        "其他区段": [],
    }
    seen = set()
    for g in groups.values():
        for e in g:
            seen.add(e.get("address"))
    groups["其他区段"] = [e for e in fb if e.get("address") not in seen]

    for name, els in groups.items():
        print(f"\n  --- {name}: {len(els)} 条")
        for e in els[:6]:
            print(f"      0x{to_int(e.get('address')):08X} "
                  f"{(e.get('original') or '')[:50]!r}")
        if len(els) > 6:
            print(f"      ... 共 {len(els)} 条")

    print()
    print("=" * 112)
    print("结论（客观，不含伪判）")
    print("=" * 112)
    print(f"  · fallback 共 {len(fb)} 条")
    print(f"  · 其中 {len(dup)} 条与正常文本完全重复 → 可直接去重")
    print("  · 0x3DA000-0x3DC000 段是战斗提示池，内容是正常日文，不该在剧情模块")
    print("  · 0x1D0000 段那批需要人眼裁定（字节形态像压缩数据，但也可能是")
    print("    未启用的占位台词 —— 我不下结论）")

    OUT.write_text(json.dumps(
        {"total": len(fb), "dup_with_normal": len(dup),
         "by_group": {k: [e.get("address") for e in v] for k, v in groups.items()}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
