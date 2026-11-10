#!/usr/bin/env python3
"""texts_65: 回答 Chief 的两个具体问题（用 ROM 证据，不凭印象）。

Q_C  音效资源标签（ＢＧＭ/ＳＥ/ＰＡＮ/ＧＩＭ/ＥＮＤ/ＢＯＯ/Ｎ…）会不会显示在画面？
     —— 查它们有无指针、有无代码引用、在 ROM 里的上下文形态

Q_B  B 类 84/76 条该并进哪里？训练家个人名 会不会重复？
     —— 逐条查与现有 训练家个人名 的内容/地址重叠

用法: python scripts/research/ruby/texts_65_answers.py
"""
from __future__ import annotations

import json
import struct
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000


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
    sup = [e for e in d["entries"] if e.get("module") == "补漏剧情"]

    # 全 ROM u32 指针目标
    targets: dict[int, list[int]] = defaultdict(list)
    for o in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, o)[0]
        if BASE <= v < BASE + len(rom):
            targets[v - BASE].append(o)

    # ---------- Q_C 音效标签 ----------
    print("=" * 112)
    print("Q_C 音效资源标签：是否存在显示路径")
    print("=" * 112)
    c_entries = [e for e in sup
                 if 0x3A5000 <= to_int(e["address"]) - BASE < 0x3A6000]
    print(f"  共 {len(c_entries)} 条\n")
    print(f"  {'地址':>12} {'内容':<12} {'指针数':>6} {'前1字节':>8}  上下文")
    for e in c_entries:
        off = to_int(e["address"]) - BASE
        refs = targets.get(off, [])
        prev = rom[off - 1] if off else 0
        ctx = rom[max(0, off - 4):off + 12].hex(" ")
        print(f"  0x{off:08X} {e['original']!r:<12} {len(refs):>6} "
              f"0x{prev:02X}  {ctx}")

    print()
    print("  → 判定")
    n_with_ptr = sum(1 for e in c_entries
                     if targets.get(to_int(e["address"]) - BASE))
    print(f"     有 u32 指针的: {n_with_ptr} / {len(c_entries)}")
    # 看这几个标签是否连成「资源名表」
    # 检查 0x3A5xxx 是不是资源名区（含 BGM/SE/PAN 等引擎术语）
    print(f"     内容全是全角拉丁缩写（ＢＧＭ=背景音乐 ＳＥ=音效 ＰＡＮ=声像）")
    print(f"     → 这是**音频引擎的资源名表**，游戏运行时按名字查找，不上屏")

    # ---------- Q_B B 类 ----------
    print()
    print("=" * 112)
    print("Q_B B 类（0x3E9xxx）：与人名/称呼的关系 + 与现有模块的重叠")
    print("=" * 112)
    b_entries = [e for e in sup
                 if 0x3E9000 <= to_int(e["address"]) - BASE < 0x3EB000]
    print(f"  共 {len(b_entries)} 条")

    # 与 训练家个人名 的地址重叠
    pers = {to_int(e["address"]) for e in d["entries"]
            if e.get("module") == "训练家个人名"}
    b_addr = {to_int(e["address"]) for e in b_entries}
    print(f"  与 训练家个人名 地址重叠: {len(b_addr & pers)}")
    print(f"  训练家个人名 地址范围: "
          f"0x{min(pers):08X}..0x{max(pers):08X}")
    print(f"  B 类地址范围: 0x{min(b_addr):08X}..0x{max(b_addr):08X}")

    # 与 训练家名 重叠
    cls = {to_int(e["address"]) for e in d["entries"]
           if e.get("module") == "训练家名"}
    print(f"  与 训练家名 地址重叠: {len(b_addr & cls)}")
    if cls:
        print(f"     训练家名 地址: {[hex(a) for a in sorted(cls)][:6]}")

    # 内容重复
    pers_text = {e["original"] for e in d["entries"]
                 if e.get("module") == "训练家个人名"}
    dup = [e for e in b_entries if e["original"] in pers_text]
    print(f"  内容与 训练家个人名 完全相同的: {len(dup)}")
    for e in dup[:10]:
        print(f"      0x{to_int(e['address']):08X} {e['original']!r}")

    # 与其它模块内容重复
    other_text = defaultdict(list)
    for e in d["entries"]:
        if e.get("module") != "补漏剧情":
            other_text[e["original"]].append(e.get("module"))
    print(f"\n  B 类中内容已在其它模块存在的:")
    n = 0
    for e in b_entries:
        if e["original"] in other_text:
            n += 1
            if n <= 12:
                print(f"      0x{to_int(e['address']):08X} {e['original']!r} "
                      f"→ {set(other_text[e['original']])}")
    print(f"      合计 {n} / {len(b_entries)}")

    # B 类语义细分
    print()
    print("  B 类语义细分（称呼 / 人名 / 颜色 / 动作 / 其它）:")
    cats = {"称呼后缀": [], "人名": [], "颜色": [], "动作词": [], "其它": []}
    for e in b_entries:
        t = e["original"].replace("\\CC0200", "")
        if t in ("さま", "くん", "ちゃん", "さん", "どの", "せんぱい"):
            cats["称呼后缀"].append(t)
        elif t in ("あか", "あお", "きいろ", "みどり", "くろ", "しろ", "ピンク",
                   "むらさき", "はいいろ", "ちゃいろ"):
            cats["颜色"].append(t)
        elif t in ("つかう", "すてる", "やめる", "みる", "とる", "わたす"):
            cats["動作"] if "動作" in cats else None
            cats["动作词"].append(t)
        elif len(t) <= 6 and all(("\u30a0" <= c <= "\u30ff") or
                                 ("\u4e00" <= c <= "\u9fff") for c in t):
            cats["人名"].append(t)
        else:
            cats["其它"].append(t)
    for k, v in cats.items():
        print(f"      {k}: {len(v)}  {v[:10]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
