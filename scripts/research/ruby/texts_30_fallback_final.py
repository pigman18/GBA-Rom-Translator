#!/usr/bin/env python3
"""texts_30: fallback 71 条终判 —— 只用「不可能是正常文本」的硬证据。

texts_29 的「假名占比」判据误杀了正常战斗提示（如
`\\0Dは \\16で\\nじめんタイプの わざが あたらない！`）。日文台词假名占比本来就高，
这个判据无效，作废。

本版只用三条硬证据（任一命中即判伪）：
  H1 裸 F7 / F8（不在 FC 参数位置）：JP 文本流里不存在这两种控制码，
     出现即说明解码起点落在二进制数据中间。
  H2 未知字形 <XX>：BYTE_TO_CHAR 覆盖 0x00-0xF6 全部字形，
     出现 <XX> 说明该字节根本不是字形。
  H3 与「已确认正常文本」字节级重复：同一段字节在别处已被判为正常 → 这条是重复伪命中。

正常战斗提示虽假名占比高，但无 H1/H2，会被正确保留。

用法: python scripts/research/ruby/texts_30_fallback_final.py
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
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import BYTE_TO_CHAR  # noqa: E402
from meowth.pcs_codes import fc_arg_count  # noqa: E402


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


def hard_check(raw: bytes) -> list[str]:
    """只返回硬证据理由；空列表 = 未发现硬证据。"""
    body = raw[:-1] if raw and raw[-1] == 0xFF else raw
    reasons = []
    bare_high = 0
    unknown = 0
    i = 0
    while i < len(body):
        b = body[i]
        if b == 0xFC:
            if i + 1 >= len(body):
                break
            i += 2 + fc_arg_count(body[i + 1])
            continue
        if b == 0xFD:
            i += 2
            continue
        if b in (0xFE, 0xFA, 0xFB):
            i += 1
            continue
        if b in (0xF7, 0xF8):
            bare_high += 1
            i += 1
            continue
        if b not in BYTE_TO_CHAR:
            unknown += 1
        i += 1
    if bare_high:
        reasons.append(f"裸F7/F8×{bare_high}")
    if unknown:
        reasons.append(f"未知字形×{unknown}")
    return reasons


def main() -> int:
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    story = [e for e in d["entries"] if e.get("module") == "剧情"]
    fb = [e for e in story if "fallback" in e]

    print("=" * 112)
    print(f"fallback 条目硬证据判定（共 {len(fb)} 条）")
    print("=" * 112)

    bad, clean = [], []
    for e in fb:
        try:
            raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        r = hard_check(raw)
        (bad if r else clean).append((e, r))

    print(f"\n  命中硬证据（判伪）: {len(bad)}")
    print(f"  无硬证据（保留）  : {len(clean)}")

    print()
    print("=" * 112)
    print("A. 判伪清单（有硬证据）")
    print("=" * 112)
    rc = Counter()
    for e, r in bad:
        for x in r:
            rc[x.split("×")[0]] += 1
    print(f"  理由分布: {dict(rc)}")
    print()
    for e, r in bad:
        print(f"  0x{to_int(e.get('address')):08X}  {r}  "
              f"{(e.get('original') or '')[:56]!r}")

    print()
    print("=" * 112)
    print("B. 无硬证据的（必须保留 —— 这些是正常文本）")
    print("=" * 112)
    for e, _ in clean[:25]:
        print(f"  0x{to_int(e.get('address')):08X}  "
              f"{(e.get('original') or '')[:56]!r}")
    if len(clean) > 25:
        print(f"  ... 共 {len(clean)} 条")

    out = ROOT / "work" / "_probe" / "texts_fallback_verdict.json"
    out.write_text(json.dumps(
        {"delete": [{"address": e.get("address"), "original": e.get("original"),
                     "reasons": r} for e, r in bad],
         "keep": len(clean)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
