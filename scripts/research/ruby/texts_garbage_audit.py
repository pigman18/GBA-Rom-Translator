#!/usr/bin/env python3
"""量化 scan 模块里的伪文本（不删任何东西，只出分类统计）。

判据全部基于「日文句子的客观特征」，不用主观启发式：

  A. 真句子特征（满足任一即倾向真台词）
     1. 含换行 \n 或 \l \p
     2. 含句读 。！？、…
     3. 含空格分隔的「词 + 助词」形态（日文正常排版用空格分词）
     4. 长度 >= 12 且假名字符 > 60%

  B. 伪文本特征（客观可判，不与 A 冲突才判伪）
     1. 全角字母数字占多数（Ｗ０８９ / ＥＶＥＮＴ０ = 表项名，非台词）
     2. 单字或双字 + 大量填充空格（'え あ ' / 'み   '）
     3. 假名字符重复模式：同一 2-gram 出现 >= 4 次
     4. 含非日文字符（Ä Ü ｋ ヌ 混排 = 解码错位）
     5. 长度 <= 4 且不含标点

用法：
    python scripts/research/ruby/texts_garbage_audit.py
"""
from __future__ import annotations

import json
import re
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

KANA = set("ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞ"
           "ただちぢっつづてでとどなにぬねのはばぱひびぴふぶぷへべぺほぼぽ"
           "まみむめもゃやゅゆょよらりるれろゎわゐゑをん"
           "ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾ"
           "タダチヂッツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポ"
           "マミムメモャヤュユョヨラリルレロヮワヰヱヲンヴー")
PUNCT = set("。！？、…‥「」『』（）・～ー！？，．：；")

ALNUM_RE = re.compile(r"[A-Za-zＡ-Ｚａ-ｚ０-９0-9]")
NONJP_RE = re.compile(r"[ÄÜäöüÄ-ſｋ-ﾟ]")   # 混排乱码（排除全角假名区）


def is_real_sentence(t: str) -> bool:
    """是否像真台词。"""
    if not t:
        return False
    if "\n" in t or "\\n" in t or "\\l" in t or "\\p" in t:
        return True
    if any(c in PUNCT for c in t):
        return True
    # 空格分词 + 长度
    core = t.replace(" ", "")
    if len(core) >= 12:
        kana = sum(1 for c in core if c in KANA)
        if kana / max(1, len(core)) > 0.6:
            return True
    return False


def garbage_reason(t: str) -> str | None:
    """返回伪文本理由，None = 不算伪。"""
    if not t:
        return "empty"
    core = t.replace(" ", "").replace("\n", "")

    # 1 字母数字占多数（表项名）
    alnum = len(ALNUM_RE.findall(t))
    if alnum and alnum >= max(1, len(core) // 2):
        return "alnum_dominant"

    # 2 单/双字 + 填充
    if len(core) <= 2 and len(t) > len(core):
        return "few_chars_padding"

    # 3 2-gram 重复
    if len(core) >= 8:
        grams = Counter(core[i:i + 2] for i in range(len(core) - 1))
        if grams and grams.most_common(1)[0][1] >= 4:
            return "repeated_ngram"

    # 4 乱码混排
    if NONJP_RE.search(core):
        return "mojibake"

    # 5 极短无标点
    if len(core) <= 4 and not any(c in PUNCT for c in core):
        return "too_short"

    return None


def main() -> int:
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    entries = d["entries"]

    print("=" * 92)
    print("scan 模块伪文本审计（只统计，不删除）")
    print("=" * 92)

    grand: Counter = Counter()
    for mod in ("剧情", "补漏剧情", "UI界面"):
        es = [e for e in entries if e.get("module") == mod]
        if not es:
            continue
        real = garbage = 0
        reasons: Counter = Counter()
        samples: dict[str, str] = {}
        for e in es:
            t = e.get("original") or ""
            if is_real_sentence(t):
                real += 1
                continue
            why = garbage_reason(t)
            if why:
                garbage += 1
                reasons[why] += 1
                samples.setdefault(why, t)
            else:
                real += 1

        print(f"\n--- {mod}  共 {len(es)} 条 ---")
        print(f"  真台词  {real:>5}  ({real * 100 // len(es)}%)")
        print(f"  伪文本  {garbage:>5}  ({garbage * 100 // len(es)}%)")
        for why, n in reasons.most_common():
            print(f"     {why:<20} {n:>5}   例: {samples[why]!r}")
        grand[mod] = (real, garbage)

    print()
    print("=" * 92)
    print(f"{'模块':<12}{'总数':>7}{'真台词':>8}{'伪文本':>8}{'假阳性风险':>12}")
    tot_r = tot_g = 0
    for mod, (r, g) in grand.items():
        tot_r += r
        tot_g += g
        print(f"{mod:<12}{r + g:>7}{r:>8}{g:>8}{'':>12}")
    print(f"{'合计':<12}{tot_r + tot_g:>7}{tot_r:>8}{tot_g:>8}")
    print()
    print("⚠️ 判据是统计性的，删除前必须逐条人工确认")
    print("   尤其 too_short（可能是正常短对话如「はい」「そうか」）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
