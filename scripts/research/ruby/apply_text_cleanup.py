#!/usr/bin/env python3
"""按三个审查员的逐条判定，清洗 texts.json。

判定来源（全部为逐条人工阅读，非启发式）：
  work/_review/audit_剧情.json       6,983 条
  work/_review/audit_补漏剧情.json   1,561 条
  work/_review/audit_UI界面.json       503 条

清洗规则（依据 TextAuditor3 的复核建议统一口径）：
  1. verdict == "garbage"                     → 删除
  2. verdict == "real" 但剥离控制码后无可见文字 → 删除（纯符号/纯控制码，非待翻译文本）
  3. verdict == "real" 且是假名顺序码表片段     → 删除（字符码表，不是文本）
  4. 其余保留

用法：
    python scripts/research/ruby/apply_text_cleanup.py --dry-run
    python scripts/research/ruby/apply_text_cleanup.py --write
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
REVIEW = ROOT / "work" / "_review"

KANA_ORDER = ("あいうえおかきくけこさしすせそたちつてとなにぬねの"
              "はひふへほまみむめもやゆよらりるれろわをん")

# 定长表区间：这些地址范围内的条目即使内容是「？？？？」也不许删。
# 它们是表的空槽占位（道具名 0x39A648 起有 67 个「？？？？？？？？」槽），
# 删掉会破坏 index 对齐，导致读取整表错位。
# (lo, hi, 说明)
PROTECTED_TABLES = [
    (0x1CAD04, 0x1CB813, "招式名"),
    (0x1CBC4C, 0x1CBEB3, "特性名"),
    (0x1CBB0C, 0x1CBB65, "属性名"),
    (0x39A648, 0x39DCA7, "道具名"),
    (0x384746, 0x38717D, "图鉴分类名"),
    (0x3C2A54, 0x3C3773, "秘密基地装饰名"),
    (0x3A1050, 0x3A1503, "树果名"),
    (0x1CA354, 0x1CACFB, "宝可梦名"),
]


def in_protected_table(addr_gba: int) -> str | None:
    """条目的 GBA 地址若落在受保护的定长表内，返回表名。"""
    off = addr_gba - 0x08000000
    for lo, hi, name in PROTECTED_TABLES:
        if lo <= off <= hi:
            return name
    return None

# 控制码形态：\NN（十六进制）、\CCxxxx、\n \l \p
_CTRL_RE = re.compile(r"\\[0-9A-Fa-f]{2}|\\[A-Za-z0-9]{2}")


def strip_controls(t: str) -> str:
    s = _CTRL_RE.sub("", t)
    return s.replace("\\n", "").replace("\\l", "").replace("\\p", "").strip()


def has_visible_text(t: str) -> bool:
    """是否为「待翻译文本」。

    ⚠️ 判据不能只看「有无假名/汉字」，否则会误删这些真实 UI 文本
    （2026-11-04 实测踩到）：
        'Ｌ‥ＵＰ Ｒ‥ＤＯＷＮ'  方向键提示
        '？？？．？ｋｇ'        单位占位符
        'ＩＤＮｏ．'            UI 标签
        '\\02．\\03ｃｍ'          带变量的单位模板
    这些剥离控制码后没有假名，但都是有效待翻译文本。

    正确判据：剥离控制码后，只要还有 **假名/汉字/拉丁字母/全角字母数字**
    任一，就算待翻译文本；纯符号、纯省略号、纯控制码才算「无需翻译」。
    """
    s = strip_controls(t)
    return bool(re.search(
        r"[\u3041-\u3096\u30A1-\u30FA\u4E00-\u9FFF"   # 假名/汉字
        r"A-Za-zＡ-Ｚａ-ｚ０-９"                        # 拉丁 / 全角字母数字
        r"]", s))


def is_kana_chart(t: str, run: int = 5) -> bool:
    """是否假名顺序排列的字符码表（如 あいうえおかきく / さしすせそたち）。"""
    core = t.replace(" ", "")
    if len(core) < 6:
        return False
    best = cur = 0
    for i in range(1, len(core)):
        a, b = core[i - 1], core[i]
        if a in KANA_ORDER and b in KANA_ORDER:
            if KANA_ORDER.index(b) == KANA_ORDER.index(a) + 1:
                cur += 1
                best = max(best, cur)
                continue
        cur = 0
    return best >= run


def load_verdicts() -> dict[str, dict]:
    """id -> 判定记录。三个文件合并。"""
    out: dict[str, dict] = {}
    for fn in ("audit_剧情.json", "audit_补漏剧情.json", "audit_UI界面.json"):
        p = REVIEW / fn
        if not p.exists():
            raise SystemExit(f"缺少审查文件: {p}")
        for e in json.loads(p.read_text(encoding="utf-8")):
            eid = e.get("id")
            if eid:
                out[eid] = e
    return out


def main() -> int:
    write = "--write" in sys.argv
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    entries = d["entries"]
    verdicts = load_verdicts()

    print("=" * 84)
    print(f"texts.json 清洗 {'（写入）' if write else '（dry-run，不写文件）'}")
    print("=" * 84)
    print(f"审查判定覆盖: {len(verdicts)} 条 / 条目 {len(entries)} 条")

    keep: list[dict] = []
    reasons: Counter = Counter()
    removed_by_mod: Counter = Counter()
    removed_samples: dict[str, list[str]] = defaultdict(list)

    for e in entries:
        eid = e.get("id")
        mod = e.get("module") or ""
        v = verdicts.get(eid)

        # 无判定记录的条目：保留（不在审查范围内，如定长表）
        if v is None:
            keep.append(e)
            continue

        text = e.get("original") or ""
        verdict = v.get("verdict")

        # 定长表内的条目一律保留：空槽占位是全表结构的一部分，
        # 删条目不删槽，否则 index 错位。
        try:
            addr = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
        except ValueError:
            addr = 0
        guard = in_protected_table(addr)

        if guard:
            why = None
        elif verdict == "garbage":
            why = "garbage"
        elif verdict == "real" and not has_visible_text(text):
            why = "no_visible_text"
        elif verdict == "real" and is_kana_chart(text):
            why = "kana_chart"
        else:
            why = None

        if why:
            reasons[why] += 1
            removed_by_mod[mod] += 1
            if len(removed_samples[why]) < 6:
                removed_samples[why].append(text[:42])
        else:
            keep.append(e)

    total_removed = sum(reasons.values())
    print()
    print("删除分类:")
    for why, n in reasons.most_common():
        print(f"  {why:<18} {n:>5}")
        for s in removed_samples[why][:3]:
            print(f"      例: {s!r}")
    print()
    print("删除按模块:")
    for m, n in removed_by_mod.most_common():
        print(f"  {m:<12} {n:>5}")
    print()
    print(f"条目: {len(entries)} → {len(keep)}   （删除 {total_removed}）")

    # 模块内条目清空检查
    before = Counter(e.get("module") for e in entries)
    after = Counter(e.get("module") for e in keep)
    print()
    print("模块条目数变化（只列有变化的）:")
    for m in sorted(set(before) | set(after)):
        if before[m] != after[m]:
            print(f"  {m:<14} {before[m]:>5} → {after[m]:>5}  ({after[m] - before[m]:+d})")
    emptied = [m for m in after if after[m] == 0]
    if emptied:
        print(f"  ⚠️ 清空的模块: {emptied}")

    if not write:
        print()
        print("dry-run 结束。确认无误后加 --write 执行。")
        return 0

    # 备份
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = TEXTS.with_suffix(f".json.bak_{stamp}")
    shutil.copy2(TEXTS, bak)
    print(f"\n已备份: {bak.name}")

    # 写入
    d["entries"] = keep
    d["count"] = len(keep)
    TEXTS.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print(f"已写入: {TEXTS}")
    print(f"新 count = {d['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
