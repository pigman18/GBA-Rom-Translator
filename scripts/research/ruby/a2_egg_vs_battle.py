#!/usr/bin/env python3
"""对比：为什么战斗界面宝可梦名正常，队伍列表却是「蛋」？

实测：
  battle/006.png        长翅鸥 → 显示正确「长翅鸥」
  pokemon_menu/010.png  ラグラージ/ジュカイン/サナギラス/キノココ → 全显示「蛋」

两者都经 SLT2 查表，为什么结果不同？

关键差异（详见 docs/ruby_text.md）：
  战斗界面宝可梦名 → textMode=2（tm2 缓冲，fontNum 被强制为 4）
  队伍列表宝可梦名 → 可能是别的 textMode / fontNum

假说：队伍列表的字形分配走了不同路径，
      而「蛋」这个字形恰好落在某个被复用的 tile 上。

验证思路：
  1. 查「蛋」在字库里的 gidx
  2. 查四个宝可梦名首字的 gidx
  3. 看它们的 tile 分配是否冲突

用法：
    python scripts/research/ruby/a2_egg_vs_battle.py
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
sys.path.insert(0, str(ROOT / "src"))

BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"


def pack_glyph_index(lead: int, trail: int) -> int:
    idx = lead
    if idx >= 6:
        if idx >= 0x1B:
            idx -= 1
        idx -= 1
    idx -= 1
    return ((idx << 8) | trail) & 0xFFFF


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")

    # 1. 「蛋」的编码
    print("=== 「蛋」的编码 ===")
    b = cm.encode("蛋")
    print(f"  encode('蛋') = {b.hex(' ')}")
    if len(b) >= 4 and b[0] == 0xF9:
        g = pack_glyph_index(b[2], b[3])
        print(f"  lead=0x{b[2]:02X} trail=0x{b[3]:02X} → gidx=0x{g:04X} ({g})")

    # 2. 四个宝可梦名首字
    print()
    print("=== 四个宝可梦名首字 ===")
    for name in ("巨沼怪", "蜥蜴王", "沙基拉斯", "蘑蘑菇"):
        b = cm.encode(name[0])
        print(f"  {name} 首字 {name[0]!r}: {b.hex(' ')}", end="")
        if len(b) >= 4 and b[0] == 0xF9:
            g = pack_glyph_index(b[2], b[3])
            print(f" → gidx=0x{g:04X}")
        else:
            print()

    # 3. 查 build.json 里这些名字的实际 target_hex
    print()
    print("=== build.json 里的实际码位 ===")
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    targets = {"ラグラージ": "巨沼怪", "ジュカイン": "蜥蜴王",
               "サナギラス": "沙基拉斯", "キノココ": "蘑蘑菇"}
    for e in d.get("entries") or []:
        if e.get("module") != "宝可梦名":
            continue
        orig = e.get("original") or ""
        if orig not in targets:
            continue
        th = (e.get("target_hex") or "").replace(" ", "")
        raw = bytes.fromhex(th)
        codes = []
        i = 0
        while i + 3 <= len(raw):
            if raw[i] == 0xF9 and raw[i + 1] == 0x00:
                lead, trail = raw[i + 2], raw[i + 3]
                g = pack_glyph_index(lead, trail)
                codes.append(f"0x{g:04X}")
                i += 4
            else:
                i += 1
        print(f"  {orig} → {e.get('translated')!r}")
        print(f"    target_hex={th[:48]}")
        print(f"    gidx: {' '.join(codes)}")

    # 4. 关键：这些 gidx 是否都相同（映射到同一字形 = 显示成同一个字）
    print()
    print("=== 检查首字 gidx 是否相同 ===")
    first_g = []
    for e in d.get("entries") or []:
        if e.get("module") != "宝可梦名":
            continue
        if (e.get("original") or "") not in targets:
            continue
        th = (e.get("target_hex") or "").replace(" ", "")
        raw = bytes.fromhex(th)
        if len(raw) >= 4 and raw[0] == 0xF9:
            first_g.append((e.get("original"), pack_glyph_index(raw[2], raw[3])))
    for n, g in first_g:
        print(f"  {n}: 首字 gidx=0x{g:04X}")
    if len(set(g for _, g in first_g)) == len(first_g):
        print("  ✅ 首字 gidx 各不相同 → 数据层没问题")
    else:
        print("  ❌ 有重复 gidx → 数据层就错了")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
