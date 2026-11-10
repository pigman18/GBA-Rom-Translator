#!/usr/bin/env python3
"""texts_31: 伪假名判据 —— 用项目自己的日文词表做真伪裁决。

texts_29 的「假名占比」误杀正常台词，texts_30 的「裸F7/F8」漏掉大量伪假名
（如 'わいんいゃせろはざらやぇ？ずせぱチカゅツ' —— 全是合法字形，但不成词）。

正确做法：**用词表命中率**。真日文台词由常用词构成，能在项目 lexicon +
官方语料里命中子串；随机排列的伪假名几乎命中不了。

判据：
  W1 用 lexicon（招式/道具/地点/属性/特性/性格/图鉴/短语/UI）+ reference_corpus
     的日文行构建「常用日文词集合」
  W2 对每条文本，切出长度>=2 的假名片段，统计能命中词表/词库的比例
  W3 命中率 < 阈值 且 长度 >= 8 → 判伪假名

用法: python scripts/research/ruby/texts_31_kana_plausibility.py
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
LEX = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "lexicon"
CORPUS = ROOT / "src" / "util" / "configs" / "reference_corpus"
OUT = ROOT / "work" / "_probe" / "texts_kana_verdict.json"


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


def build_vocab() -> set[str]:
    """构建常用日文词/片段集合。"""
    vocab: set[str] = set()
    for p in LEX.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict):
            for k in d:
                vocab.add(k)
        elif isinstance(d, list):
            for k in d:
                if isinstance(k, str):
                    vocab.add(k)
    # 参考语料里的日文行（拆成词片段）
    for p in CORPUS.rglob("*.txt"):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for line in txt.splitlines()[:20000]:
            for w in re.split(r"[\s　\n]+", line):
                if 2 <= len(w) <= 8:
                    vocab.add(w)
    return vocab


def core_text(s: str) -> str:
    s = re.sub(r"\\CC[0-9A-Fa-f]+", "", s)
    s = re.sub(r"\\btn[0-9A-Fa-f]{2}", "", s)
    s = re.sub(r"\\\?[0-9A-Fa-f]{2}", "", s)
    s = re.sub(r"\\[0-9A-Fa-f]{2}", "", s)
    s = re.sub(r"\[[^\]]*\]", "", s)
    return s.replace("\n", "").replace("\r", "").replace("\\l", "").strip()


def kana_chunks(s: str) -> list[str]:
    """切出连续假名片段（平假名/片假名），长度>=2。"""
    out = []
    buf = []
    for ch in s:
        if ("\u3040" <= ch <= "\u309f") or ("\u30a0" <= ch <= "\u30ff"):
            buf.append(ch)
        else:
            if len(buf) >= 2:
                out.append("".join(buf))
            buf = []
    if len(buf) >= 2:
        out.append("".join(buf))
    return out


def main() -> int:
    vocab = build_vocab()
    print(f"词表/语料片段规模: {len(vocab):,}")

    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    story = [e for e in d["entries"] if e.get("module") == "剧情"]
    fb = [e for e in story if "fallback" in e]

    def plausible(text: str) -> tuple[float, int, int]:
        """返回 (命中率, 命中片段数, 片段总数)。"""
        core = core_text(text)
        chunks = kana_chunks(core)
        if not chunks:
            return 0.0, 0, 0
        hit = 0
        for c in chunks:
            # 片段本身或其中任一子串命中词表即算
            if c in vocab:
                hit += 1
                continue
            found = False
            for L in range(len(c) - 1, 1, -1):
                for i in range(len(c) - L + 1):
                    if c[i:i + L] in vocab:
                        found = True
                        break
                if found:
                    break
            if found:
                hit += 1
        return hit / len(chunks), hit, len(chunks)

    print()
    print("=" * 112)
    print("校准：用「已知正常」与「已知伪」样本定阈值")
    print("=" * 112)
    # 正常样本：已有的战斗提示
    normal_samples = ["\\0Dは \\16で\nじめんタイプの わざが あたらない！",
                      "\\0Cは \\0Dから\n\\13を うばいとった！",
                      "あ！ やせいの\n\\03が とびだしてきた！"]
    for s in normal_samples:
        r, h, n = plausible(s)
        print(f"  正常样例 命中率 {r:.0%} ({h}/{n})  {core_text(s)[:40]!r}")
    pseudo_samples = ["わいんいゃせろはざらやぇ？ずせぱチカゅツ",
                      "むいろいフしゃねツよ？ょゥぶゅシ",
                      "タパほくネパほくＢトほく う‥な‥な・なクパほくミパほく"]
    for s in pseudo_samples:
        r, h, n = plausible(s)
        print(f"  伪样例   命中率 {r:.0%} ({h}/{n})  {s[:40]!r}")

    print()
    print("=" * 112)
    print(f"对 71 条 fallback 逐条判定（阈值：命中率 < 50% 且 片段数 >= 2）")
    print("=" * 112)
    bad, keep = [], []
    for e in fb:
        text = e.get("original") or ""
        core = core_text(text)
        r, h, n = plausible(core)
        if n >= 2 and r < 0.50:
            bad.append((e, r, h, n))
        else:
            keep.append((e, r, h, n))

    print(f"\n  判伪假名: {len(bad)}")
    print(f"  保留    : {len(keep)}\n")
    print("  === 判伪清单 ===")
    for e, r, h, n in bad:
        print(f"    0x{to_int(e.get('address')):08X} 命中{r:.0%}({h}/{n})  "
              f"{core_text(e.get('original') or '')[:50]!r}")
    print()
    print("  === 保留清单（前 20）===")
    for e, r, h, n in keep[:20]:
        print(f"    0x{to_int(e.get('address')):08X} 命中{r:.0%}({h}/{n})  "
              f"{core_text(e.get('original') or '')[:50]!r}")

    OUT.write_text(json.dumps(
        {"delete": [{"address": e.get("address"), "original": e.get("original"),
                     "hit_rate": r} for e, r, h, n in bad],
         "keep": [{"address": e.get("address"), "original": e.get("original"),
                   "hit_rate": r} for e, r, h, n in keep]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
