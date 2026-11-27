"""排查「前导参数占位丢失」——导致游戏里漏出日文原文的主因。

【问题实例（用户 2026-11-27 截图指出的那句）】
  条 6652  原文 `は どうする？`   （开头是半角空格，作为「宝可梦名」的占位）
           译文 `怎么办?`         （占位被删）
  游戏运行时把名字填进那个空格 ⇒ 正常显示「バシャーモは どうする？」→「火焰鸡要怎么做？」
  占位丢掉之后 ⇒ 名字塞不进去，画面显示「バシャーモ怎么办?」
                 既是未翻译的日文，又缺主语。

  对比同型条目（这些是对的）：
  条 724  `\\0Fは どうする？` → `\\0F怎么办?`   ← 参数保留，名字能填入
  条 787  `\\20は どうする？` → `\\20怎么办?`

【本脚本查什么】
  原文以「半角空格」或「参数」开头，但译文不以同类占位开头的条目。
  这类几乎必然导致漏出日文/名字错位。

用法：
    python scripts/verify/find_leading_placeholder.py --limit 25
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TR = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts_translated.json"


def starts_with_param(s: str) -> bool:
    return len(s) >= 3 and s[0] == "\\" and s[1] == "0"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()

    data = json.loads(TR.read_text("utf-8"))
    lost_space: list[tuple[int, str, str]] = []
    lost_param: list[tuple[int, str, str]] = []

    for i, e in enumerate(data):
        o = e.get("original") or ""
        t = e.get("translated") or ""
        if not o or not t:
            continue

        oym = o.startswith(" ")
        tym = t.startswith(" ")
        op = starts_with_param(o)
        tp = starts_with_param(t)

        # 原文以空格占位，译文既不以空格也不以参数开头 ⇒ 占位丢失
        if oym and not tym and not tp:
            lost_space.append((i, o, t))
        # 原文以参数开头，译文不以参数开头 ⇒ 参数丢失
        elif op and not tp:
            lost_param.append((i, o, t))

    print(f"① 原文以空格占位开头、译文丢了占位：{len(lost_space)} 条")
    for i, o, t in lost_space[:a.limit]:
        print(f"   [{i}] JP={o[:60]!r}")
        print(f"         CN={t[:60]!r}")
    print()
    print(f"② 原文以 \\0X 参数开头、译文丢了参数：{len(lost_param)} 条")
    for i, o, t in lost_param[:a.limit]:
        print(f"   [{i}] JP={o[:60]!r}")
        print(f"         CN={t[:60]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
