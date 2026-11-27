"""排查译文里的参数错位（\\0X 被替换成 \\CC.. 等）。

条 372 的实例：
  JP: \\02の\\nわざポイントが ふえた！\\CC09
  CN: \\CC09的招式威力提升\\n了!\\CC09
\\02（宝可梦名参数）被替换成了 \\CC09（控制码），名字显示会错乱。
"""
from __future__ import annotations
import json
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts_translated.json"


def params(s: str) -> list[str]:
    """取出 \\0X 形式的参数（\\00..\\0F, \\CC 不算）。"""
    out = []
    i = 0
    while i < len(s) - 1:
        if s[i] == "\\" and s[i + 1] == "0":
            out.append(s[i:i + 3])
            i += 3
            continue
        i += 1
    return out


def main() -> None:
    d = json.loads(P.read_text("utf-8"))
    swapped = []
    for i, e in enumerate(d):
        o = e.get("original") or ""
        t = e.get("translated") or ""
        if not t:
            continue
        po, pt = params(o), params(t)
        if po and not pt:
            swapped.append((i, o, t))
    print(f"原文有 \\0X 参数、译文完全没有：{len(swapped)} 条")
    for i, o, t in swapped[:15]:
        print(f"[{i}]")
        print(f"  JP: {o[:75]!r}")
        print(f"  CN: {t[:75]!r}")


if __name__ == "__main__":
    main()
