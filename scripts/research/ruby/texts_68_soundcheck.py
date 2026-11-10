#!/usr/bin/env python3
"""texts_68: 音效检查菜单（サウンドチェック）的边界与内容定性。

texts_67 决定性发现：0x3A575B 那段是
  '… サウンドチェック'  （= Sound Check，音效检查菜单标题）
后面紧跟 ＶＯＩＣＥ / ＶＯＬＵＭＥ / ＰＡＮＰＯＴ / ＰＩＴＣＨ / ＬＥＮＧＴＨ /
ＲＥＬＥＡＳＥ / ＰＲＯＧＲＥＳＳ / ＣＨＯＲＵＳ / ＰＲＩＯＲＩＴＹ —— 全是音频参数名。

这是一个**开发者调试菜单**（Sound Check / Sound Test），不是玩家流程界面。

本脚本：
  1. 确定该区段的完整边界
  2. 列出区段内所有「会显示给操作者」的字符串
  3. 与补漏剧情 C 类 17 条对照

用法: python scripts/research/ruby/texts_68_soundcheck.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402


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


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))

    print("=" * 112)
    print("1) 音效检查菜单区段 0x3A5740..0x3A5C00 全部可读串")
    print("=" * 112)
    segs = []
    start = 0x3A5740
    for i in range(0x3A5740, 0x3A5C00):
        if rom[i] == 0xFF:
            t = decode_pcs(rom[start:i + 1])
            if t and len(t.strip()) >= 2:
                segs.append((start, t))
            start = i + 1
    for off, t in segs:
        print(f"  0x{off:06X} {t!r}")

    print()
    print("=" * 112)
    print("2) 补漏剧情 C 类 17 条 —— 它们全都落在这个菜单里")
    print("=" * 112)
    sup = [e for e in d["entries"] if e.get("module") == "补漏剧情"]
    c = [e for e in sup if 0x3A5000 <= to_int(e["address"]) - BASE < 0x3A6000]
    in_menu = [e for e in c
               if 0x3A5740 <= to_int(e["address"]) - BASE < 0x3A5C00]
    print(f"  C 类 {len(c)} 条中，落在音效菜单区间的: {len(in_menu)}")
    for e in c:
        off = to_int(e["address"]) - BASE
        mark = "菜单内" if 0x3A5740 <= off < 0x3A5C00 else "菜单外"
        print(f"    0x{off:06X} [{mark}] {e['original']!r}")

    print()
    print("=" * 112)
    print("3) 定性")
    print("=" * 112)
    print("""
  这是游戏的 **Sound Check（サウンドチェック）调试菜单**：
    · 标题 'サウンドチェック'
    · 操作提示 'Ａ‥さいせい Ｂ‥おわり' / 'Ｌ‥ＵＰ Ｒ‥ＤＯＷＮ'
    · 参数名 ＶＯＩＣＥ / ＶＯＬＵＭＥ / ＰＡＮＰＯＴ / ＰＩＴＣＨ / ＬＥＮＧＴＨ /
             ＲＥＬＥＡＳＥ / ＰＲＯＧＲＥＳＳ / ＣＨＯＲＵＳ / ＰＲＩＯＲＩＴＹ
    · 音名 ＢＧＭ / ＳＥ / ＰＡＮ / ＰＣＣ / ＧＩＭ / ＥＮＤ / ＢＯＯ / Ｎ / ＫＯＮ / ＥＸＰ

  **它会显示在屏幕上**（是菜单），但**只有调试/开发者能进**，
  玩家正常流程走不到。宝可梦红宝石的 Sound Check 是通过
  特定按键组合从标题画面进入的隐藏功能。

  → 翻译判断：
     · 若目标是「完整汉化」，可翻（它确实是可见文本）
     · 若目标是「玩家流程可见文本」，**可跳过**
     · 风险：翻它需要理解音频参数术语（ＰＡＮＰＯＴ = 声像电位器 等），
       价值低、成本高
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
