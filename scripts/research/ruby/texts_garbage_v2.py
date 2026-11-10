#!/usr/bin/env python3
"""scan 模块伪文本判别 v2 —— 基于字节/字符客观特征。

v1 的教训（2026-11-04）：
  - 词表命中法不可用：词表只收词条，判不了句子。
    剧情的真台词 `これが ジムの かんばん だから…` 也被判成未命中。
  - 长度法不可用：`ハルカ`/`ダイゴ` 是人名，`く   ` 是垃圾，长度一样。

v2 判据（区分度实测有效）：

  真文本特征（任一命中 → 判真）：
    T1. 含日文词间空格（正常排版：`これが ジムの かんばん だから`）
        判定：有空格且被空格切开后每段都非空、且段数 >= 2
    T2. 含控制码占位 `\\NN`（`\\10は \\13で` 这种，是脚本字符串的变量占位）
    T3. 含换行 `\\n` 且行内有 >= 6 个假名

  伪文本特征（客观，命中即判伪）：
    G1. 全角字母数字密度 >= 0.3（`ＯＢＪテキストＡＤＤ` / `Ｗ０８９`）
    G2. 同一 2-gram 重复 >= 3 次（`Ｆはく` x6、`まちちち`）
    G3. 非日文字符混排（Ä Ü ｋ 等，解码错位）
    G4. 去除空格后 <= 2 字且原串有填充空格（`く   ` / `た お `）
    G5. 多字段（被空格切开 >= 3 段）但每段都 <= 2 字（`え あ う え`）

用法：
    python scripts/research/ruby/texts_garbage_v2.py            # 统计
    python scripts/research/ruby/texts_garbage_v2.py --list 补漏剧情  # 逐条
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

KANA_RE = re.compile(
    r"[\u3041-\u3096\u30A1-\u30FA\u30FC]")
ALNUM_RE = re.compile(r"[Ａ-Ｚａ-ｚ０-９]")
MOJIBAKE_RE = re.compile(r"[\u00A0-\u024F]{2,}|\uFF71-\uFF9F(?=\s)")
CTRL_RE = re.compile(r"\\[0-9A-Fa-f]{2}")


def kana_ratio(s: str) -> float:
    core = re.sub(r"\s", "", s)
    if not core:
        return 0.0
    return len(KANA_RE.findall(core)) / len(core)


def has_word_spacing(s: str) -> bool:
    """日文正常排版：空格分词，每段 >= 2 字且段数 >= 2。"""
    parts = [p for p in s.replace("\n", " ").split(" ") if p]
    if len(parts) < 2:
        return False
    return sum(1 for p in parts if len(p) >= 2) >= 2


def classify(t: str) -> tuple[str, str]:
    """返回 (real|garbage, reason)。"""
    if not t:
        return "garbage", "empty"

    core = re.sub(r"\s", "", t)

    # ---- 伪文本特征（先判，因为它们更客观）----
    alnum = len(ALNUM_RE.findall(core))
    if core and alnum / len(core) >= 0.3:
        return "garbage", "alnum_dense"

    if len(core) >= 8:
        grams = Counter(core[i:i + 2] for i in range(len(core) - 1))
        if grams and grams.most_common(1)[0][1] >= 3:
            return "garbage", "ngram_repeat"

    if MOJIBAKE_RE.search(core):
        return "garbage", "mojibake"

    if len(core) <= 2 and len(t) > len(core):
        return "garbage", "tiny_with_padding"

    parts = [p for p in t.replace("\n", " ").split(" ") if p]
    if len(parts) >= 3 and all(len(p) <= 2 for p in parts):
        return "garbage", "all_short_parts"

    # ---- 真文本特征 ----
    if CTRL_RE.search(t):
        return "real", "has_ctrl_code"
    if has_word_spacing(t) and kana_ratio(t) >= 0.5:
        return "real", "word_spacing"
    if "\n" in t and len(KANA_RE.findall(core)) >= 6:
        return "real", "multiline"

    return "unknown", "no_clear_signal"


def main() -> int:
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    entries = d["entries"]
    want_list = None
    if len(sys.argv) >= 3 and sys.argv[1] == "--list":
        want_list = sys.argv[2]

    print("=" * 96)
    print("scan 模块伪文本判别 v2（客观字符特征，不做删除）")
    print("=" * 96)

    only_real_risk = []

    for mod in ("剧情", "补漏剧情", "UI界面"):
        es = [e for e in entries if e.get("module") == mod]
        if not es:
            continue
        if want_list and mod != want_list:
            continue

        cnt: Counter = Counter()
        samples: dict[str, list[str]] = {}
        for e in es:
            t = e.get("original") or ""
            kind, why = classify(t)
            cnt[(kind, why)] += 1
            samples.setdefault(why, [])
            if len(samples[why]) < 3:
                samples[why].append(t[:60])

        print(f"\n--- {mod}  共 {len(es)} 条 ---")
        for (kind, why), n in cnt.most_common():
            print(f"  {kind:<8}{why:<18}{n:>6}  ({n * 100 // len(es)}%)")
            for s in samples[why][:2]:
                print(f"      例: {s!r}")

        real = sum(n for (k, w), n in cnt.items() if k == "real")
        garb = sum(n for (k, w), n in cnt.items() if k == "garbage")
        unk = sum(n for (k, w), n in cnt.items() if k == "unknown")
        print(f"  → 真 {real}   伪 {garb}   未判 {unk}")

        if unk:
            # 未判的全部列出来给人工看
            unk_items = [e.get("original") or "" for e in es
                         if classify(e.get("original") or "")[0] == "unknown"]
            print(f"\n  未判 {len(unk_items)} 条，前 12 条：")
            for t in unk_items[:12]:
                print(f"      {t[:70]!r}")

    print()
    print("=" * 96)
    print("说明：'未判' 是一律保留的，不会删。删除只针对明确命中伪文本特征的。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
