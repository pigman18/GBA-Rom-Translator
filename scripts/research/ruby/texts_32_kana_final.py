#!/usr/bin/env python3
"""texts_32: 伪假名终判 —— 用「假名片段平均长度」+「词表覆盖率」双判据。

前几版判据的教训：
  - texts_29「假名占比」→ 误杀正常战斗提示（日文假名本来就多）
  - texts_30「裸F7/F8」   → 只抓到 3 条，漏掉大量纯假名乱码
  - texts_31「片段命中率」→ 伪乱码能被单字片段刷到 50%，区分度不够

本版观察：真日文台词由「词」组成，假名片段较长且能被词表整体覆盖；
随机排列的伪假名以 1-2 字的碎片为主，平均片段长度低。

双判据（同时满足才判伪）：
  K1 假名片段平均长度 < 2.2（碎片化）
  K2 长片段（>=3 字）中命中词表的比例 < 50%

校准基准用已知正常/伪样本。

用法: python scripts/research/ruby/texts_32_kana_final.py
"""
from __future__ import annotations

import json
import re
import sys
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
OUT = ROOT / "work" / "_probe" / "texts_kana_final.json"


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
    vocab: set[str] = set()
    for p in LEX.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict):
            vocab.update(k for k in d if isinstance(k, str))
    for p in CORPUS.rglob("*.txt"):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for line in txt.splitlines()[:30000]:
            for w in re.split(r"[\s　\n]+", line):
                if 2 <= len(w) <= 10:
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
    out, buf = [], []
    for ch in s:
        if ("\u3040" <= ch <= "\u309f") or ("\u30a0" <= ch <= "\u30ff"):
            buf.append(ch)
        else:
            if buf:
                out.append("".join(buf))
            buf = []
    if buf:
        out.append("".join(buf))
    return out


def score(text: str, vocab: set[str]) -> dict:
    core = core_text(text)
    chunks = kana_chunks(core)
    if not chunks:
        return {"avg": 0.0, "n": 0, "long_hit": 1.0, "long_n": 0, "pseudo": False}
    avg = sum(len(c) for c in chunks) / len(chunks)
    longs = [c for c in chunks if len(c) >= 3]
    hit = sum(1 for c in longs if c in vocab)
    long_hit = hit / len(longs) if longs else 1.0
    # 校准结论：伪样本 long_hit 全为 0%，正常样本多为 >=33%。
    # 故判据 = 有长片段 且 long_hit == 0 且 片段数 >= 2。
    pseudo = len(longs) >= 2 and long_hit == 0.0
    return {"avg": avg, "n": len(chunks), "long_hit": long_hit,
            "long_n": len(longs), "pseudo": pseudo}


def main() -> int:
    vocab = build_vocab()
    print(f"词表规模 {len(vocab):,}\n")

    print("=" * 112)
    print("校准")
    print("=" * 112)
    cal = [
        ("正常", "\\0Dは \\16で\nじめんタイプの わざが あたらない！"),
        ("正常", "\\0Cは \\0Dから\n\\13を うばいとった！"),
        ("正常", "あ！ やせいの\n\\03が とびだしてきた！"),
        ("正常", "ポケモンを すでに ６ぴき もってるときに\nあたらしく ポケモンを つかまえる"),
        ("伪", "わいんいゃせろはざらやぇ？ずせぱチカゅツ"),
        ("伪", "むいろいフしゃねツよ？ょゥぶゅシ"),
        ("伪", "タパほくネパほくＢトほく う‥な‥な・なクパほくミパほく"),
        ("伪", "ねふごくみふごくい <F8>ひごくたふごく ぉひくユげせくやにごく"),
    ]
    for kind, s in cal:
        r = score(s, vocab)
        print(f"  {kind}  avg={r['avg']:.2f} long_hit={r['long_hit']:.0%}"
              f"({r['long_n']}) n={r['n']}  判伪={r['pseudo']}  {core_text(s)[:38]!r}")

    print()
    print("=" * 112)
    print("对 71 条 fallback 判定")
    print("=" * 112)
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    fb = [e for e in d["entries"]
          if e.get("module") == "剧情" and "fallback" in e]

    bad, keep = [], []
    for e in fb:
        r = score(e.get("original") or "", vocab)
        (bad if r["pseudo"] else keep).append((e, r))

    print(f"\n  判伪: {len(bad)}   保留: {len(keep)}\n")
    print("  === 判伪 ===")
    for e, r in bad:
        print(f"    0x{to_int(e.get('address')):08X} avg={r['avg']:.2f} "
              f"long={r['long_hit']:.0%}  "
              f"{core_text(e.get('original') or '')[:48]!r}")
    print()
    print("  === 保留（正常文本，前 15）===")
    for e, r in keep[:15]:
        print(f"    0x{to_int(e.get('address')):08X} avg={r['avg']:.2f} "
              f"long={r['long_hit']:.0%}  "
              f"{core_text(e.get('original') or '')[:48]!r}")

    OUT.write_text(json.dumps(
        {"delete": [{"address": e.get("address"), "original": e.get("original"),
                     "score": r} for e, r in bad],
         "keep_count": len(keep)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
