"""排查译文里的控制码损坏（战斗信息文本质量问题）。

【背景】
2026-11-27 用户反馈「日版汉化的战斗信息翻译得乱七八糟」。
抽查发现不只是译得差，还有**数据结构损坏**：

  条[362] 原文 「\\03」 -> 译文 「\\n03」   ← \0X 参数被插进了换行
  条[432] 原文 \\02は あたらしく\\n\\03を...  -> 译文 \\p想学习新招式\\n\\02...
                                           ← \\03 丢了、\\02 挪位、\\n 变 \\p
  条[495] 原文 \\04という\\nトレーナーの...  -> 译文 名叫\\n的训练家...
                                           ← \\04 参数整个丢了

这类损坏会让游戏显示乱码或错位，必须先修，再谈翻译质量。

【本脚本查什么】
  1. 字面量反斜杠 n/p（应为真换行）：译文里出现 ``\n`` 两个字符而非换行
  2. 参数被挪位：``\0X`` 在原文与译文里的**相对顺序**不一致
  3. ``\n0X``：参数被吞进换行序列
  4. 原文有 ``\0X``、译文完全没有对应项

用法：
    python scripts/verify/check_ctrl_codes.py
    python scripts/verify/check_ctrl_codes.py --limit 30
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts_translated.json"

# \0X 形式的参数（\00 \01 \02 ... \0A \0C）
PARAM = re.compile(r"\\0[0-9A-Fa-f]")
# 字面量反斜杠 + n/p（本应是真换行，说明被二次转义）
LITERAL_NL = re.compile(r"\\[np]")


def analyze(text: str) -> dict:
    """返回该文本的控制码特征。"""
    params = PARAM.findall(text)
    return {
        "params": params,
        "has_literal_nl": bool(LITERAL_NL.search(text)),
        "real_newlines": text.count("\n"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=20, help="每类最多显示几条")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    a = ap.parse_args()

    data = json.loads(TEXTS.read_text("utf-8"))

    cat_literal: list[tuple[int, str, str]] = []   # 字面量 \n 残留
    cat_order: list[tuple[int, str, str]] = []     # 参数顺序变了
    cat_missing: list[tuple[int, str, str]] = []   # 原文有参数、译文没有
    cat_nl_param: list[tuple[int, str, str]] = []  # \n 后面紧跟 0X

    for i, e in enumerate(data):
        o = e.get("original", "") or ""
        t = e.get("translated", "") or ""
        if not t:
            continue
        oi, ti = analyze(o), analyze(t)

        if ti["has_literal_nl"]:
            cat_literal.append((i, o, t))
        if oi["params"] and not ti["params"]:
            cat_missing.append((i, o, t))
        elif oi["params"] and ti["params"] and oi["params"] != ti["params"]:
            cat_order.append((i, o, t))
        # \n 后跟 0X：多半是 \0X 被吞
        if re.search(r"\\n\s*0[0-9A-Fa-f]", t):
            cat_nl_param.append((i, o, t))

    if a.json:
        print(json.dumps({
            "literal_nl": [x[0] for x in cat_literal],
            "param_order": [x[0] for x in cat_order],
            "param_missing": [x[0] for x in cat_missing],
            "nl_then_param": [x[0] for x in cat_nl_param],
        }, ensure_ascii=False, indent=1))
        return 0

    print(f"总条目 {len(data)}")
    print()
    print(f"① 译文含字面量 \\n / \\p（应为真换行）：{len(cat_literal)} 条")
    for i, o, t in cat_literal[:a.limit]:
        print(f"   [{i}]")
        print(f"     JP: {o[:90]!r}")
        print(f"     CN: {t[:90]!r}")
    print()
    print(f"② 参数被吞进换行（\\n 紧跟 0X）：{len(cat_nl_param)} 条")
    for i, o, t in cat_nl_param[:a.limit]:
        print(f"   [{i}]")
        print(f"     JP: {o[:90]!r}")
        print(f"     CN: {t[:90]!r}")
    print()
    print(f"③ 原文有参数、译文全丢：{len(cat_missing)} 条")
    for i, o, t in cat_missing[:a.limit]:
        print(f"   [{i}] JP: {o[:80]!r}")
        print(f"        CN: {t[:80]!r}")
    print()
    print(f"④ 参数顺序/个数不一致：{len(cat_order)} 条")
    for i, o, t in cat_order[:a.limit]:
        print(f"   [{i}] JP: {o[:80]!r}")
        print(f"        CN: {t[:80]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
