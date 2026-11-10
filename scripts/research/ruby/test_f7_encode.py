#!/usr/bin/env python3
"""单测：F7 编码改造后，汉字的字节输出是否正确。

期望：
  单字「拍」 → F7 hi lo FF          （4 字节）
  两字「拍击」 → F7 hi lo F7 hi lo FF（7 字节）
  对照改造前 F9 00 hi lo：单字 5 字节，两字 9 字节

用法：
    python scripts/research/ruby/test_f7_encode.py
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from meowth.charmap import Charmap  # noqa: E402


def main() -> int:
    cm = Charmap(target_lang="zh-Hans")
    cm._escape = True

    cases = [
        ("拍", "单字"),
        ("拍击", "两字"),
        ("连环巴掌", "四字"),
        ("A", "ASCII"),
        ("1", "数字"),
        ("。", "句号"),
        ("　", "全角空格"),
        (" ", "半角空格"),
    ]

    print("=== 编码结果 ===")
    ok = True
    for text, label in cases:
        try:
            enc = cm.encode(text)
        except Exception as e:
            print(f"  {label:<6} {text!r:<10} ERROR {e}")
            ok = False
            continue
        hx = enc.hex(" ")
        # 校验：汉字必须 F7 开头，不能有 F9 00
        bad = ""
        if "f9 00" in hx:
            bad = "  ❌ 仍有 F9 00"
            ok = False
        if label in ("单字", "两字", "四字"):
            if not hx.startswith("f7"):
                bad += "  ❌ 不是 F7 开头"
                ok = False
            # 字节数校验
            n_chars = len(text)
            need = 3 * n_chars + 1
            if len(enc) != need:
                bad += f"  ❌ 长度 {len(enc)} != {need}"
                ok = False
        print(f"  {label:<6} {text!r:<10} -> {hx:<28} ({len(enc)}B){bad}")

    print()
    print("=== stride=8 表能否放下 ===")
    for text in ("拍击", "连环巴掌"):
        enc = cm.encode(text)
        fits = len(enc) <= 8
        print(f"  {text!r}: {len(enc)}B  放得进 stride=8: {'✓' if fits else '✗'}")

    print()
    print("=== 全角空格 ===")
    print(f"  '　' -> {cm.encode('　').hex(' ')}")
    print(f"  ' ' -> {cm.encode(' ').hex(' ')}")

    print()
    print("通过" if ok else "有失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
