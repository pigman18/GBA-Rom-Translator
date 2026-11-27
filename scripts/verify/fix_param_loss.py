"""修复译文里的 \\0X 参数丢失（2026-11-27）。

【问题】
102 条译文把原文开头的 \\0X（宝可梦名/玩家名/道具名参数）整个丢了，
导致游戏里名字位置空着或错位。例：

  [372] JP: \\02の\\nわざポイントが ふえた！\\CC09
        CN: \\CC09的招式威力提升\\n了!\\CC09     ← \\02 丢了

【修复策略（只做能机械判定的部分）】
  A. 原文以 \\0X 开头、译文以 \\n 或中文开头 ⇒ 把 \\0X 补回译文开头，
     并去掉译文多余的前导 \\n。
  B. 其余（参数出现在句中、或译文结构已大改）不碰，列出来人工处理。

用法：
    python scripts/verify/fix_param_loss.py --dry-run    # 只看会改什么
    python scripts/verify/fix_param_loss.py --apply      # 实际写入
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts_translated.json"


def lead_params(s: str) -> str:
    """取出字符串开头的连续 \\0X 参数（如 \\01\\05）。"""
    i = 0
    while i + 2 < len(s) and s[i] == "\\" and s[i + 1] == "0":
        i += 3
    return s[:i]


def has_param(s: str) -> bool:
    return lead_params(s) != ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="实际写入")
    ap.add_argument("--dry-run", action="store_true", help="只打印")
    a = ap.parse_args()

    d = json.loads(P.read_text("utf-8"))
    fixes: list[tuple[int, str, str, str]] = []   # (idx, old, new, reason)
    manual: list[tuple[int, str, str]] = []

    for i, e in enumerate(d):
        o = e.get("original") or ""
        t = e.get("translated") or ""
        if not t:
            continue
        lp = lead_params(o)
        if not lp:
            continue
        if has_param(t):
            continue  # 译文已有参数，跳过
        # ★ 保守规则：译文里若已出现同名参数（只是不在开头），不自动补，
        #   否则会变成 \02...\02 重复。这类交给人工。
        if any(p in t for p in [lp[i:i + 3] for i in range(0, len(lp), 3)]):
            manual.append((i, o, t))
            continue
        # A 类：原文开头有参数、译文没有 ⇒ 补回
        body = t
        changed = False
        while body.startswith("\\n"):
            body = body[2:]
            changed = True
        while body.startswith("\\p"):
            body = body[2:]
            changed = True
        if body.startswith("\n"):
            body = body[1:]
            changed = True
        new = lp + body
        # 只在「去掉前导换行」或「纯属补参数」时自动改
        if changed or body != t:
            fixes.append((i, t, new, "补回开头参数"))
        else:
            manual.append((i, o, t))

    print(f"可自动修复: {len(fixes)} 条")
    print(f"需人工判断: {len(manual)} 条")
    print()
    for i, old, new, why in fixes[:20]:
        print(f"[{i}] {why}")
        print(f"  旧: {old[:70]!r}")
        print(f"  新: {new[:70]!r}")
    if len(fixes) > 20:
        print(f"  ...（共 {len(fixes)} 条）")

    if a.apply and fixes:
        shutil.copy2(P, P.with_suffix(".json.bak_param"))
        for i, _old, new, _why in fixes:
            d[i]["translated"] = new
        P.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
        print(f"\n[OK] 已写入 {len(fixes)} 条，备份 {P.name}.bak_param")
    else:
        print("\n[dry-run] 未写入。加 --apply 执行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
