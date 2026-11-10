#!/usr/bin/env python3
"""补回 COVERAGE.md 里被替换掉的「B 类」小节标题。

背景：上一轮编辑把「### B 类有 6/13 个调用点单机到不了」这个标题
当成替换锚点，结果标题没了、内容还在。本脚本把它补回去。
"""
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "bot" / "COVERAGE.md"

HEAD = "### B 类有 6/13 个调用点单机到不了\n\n文档 §7.2 B 类的 13 个调用点分两个函数：\n\n"
ANCHOR = "- `0x0800B140`（7 个）"


def main() -> int:
    s = P.read_text(encoding="utf-8")
    if "### B 类有 6/13" in s:
        print("[skip] 标题已存在")
        return 0
    i = s.find(ANCHOR)
    if i < 0:
        print("[ERR] 找不到锚点")
        return 1
    s = s[:i] + HEAD + s[i:]
    P.write_text(s, encoding="utf-8")
    print("[OK] 已补回 B 类小节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
