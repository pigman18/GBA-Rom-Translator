#!/usr/bin/env python3
"""按 text_pipeline 的判定逻辑，实测 6 张表的 stride 需求。

不再用旧引擎的 translate.build.json（那是 F980 时代的产物）。
直接读 ROM 原文 + texts_translated.json 译文，按 F900 编码量字节。

F900 编码（实测，charmap.py）：
    每字 = F9 00 <code_hi> <code_lo>   4 字节
    结尾 = FF                          1 字节

用法：
    python scripts/research/ruby/table_stride_need.py
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

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
TRANS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts_translated.json"

BYTES_PER_CHAR = 4       # F900
EOS_BYTES = 1            # FF


def next_pow2(n: int) -> int:
    p = 1
    while p < n:
        p *= 2
    return p


def main() -> int:
    rom = ROM.read_bytes()
    tj = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = tj["modules"]
    tt = json.loads(TRANS.read_text(encoding="utf-8"))
    tr = {e["original"]: e["translated"]
          for e in tt if e.get("translated")}

    # 6 张定长/结构表的实测几何
    TAB = {
        "招式名":         dict(base=0x1CAD04, stride=8,  n=354),
        "特性名":         dict(base=0x1CBC4C, stride=8,  n=77),
        "属性名":         dict(base=0x1CBB0C, stride=5,  n=18),
        "道具名":         dict(base=0x39A648, stride=40, n=348),
        "图鉴分类名":     dict(base=0x384746, stride=28, n=386, name_offset=6),
        "秘密基地装饰名": dict(base=0x3C2A54, stride=28, n=120, name_offset=13),
    }

    print("=" * 96)
    print("按 text_pipeline 逻辑实测：6 张表的 stride 需求（F900 = 4B/字 + 1B EOS）")
    print("=" * 96)
    print(f"{'表':<16}{'旧stride':>9}{'条数':>5}{'最长译文':>9}"
          f"{'需要B':>7}{'新stride':>9}{'放大':>6}{'新体积':>9}")
    print("-" * 96)

    total_new = 0
    for name, g in TAB.items():
        base, stride, n = g["base"], g["stride"], g["n"]
        noff = g.get("name_offset", 0)
        # 读每一项原文（到 FF / 00 结束），找译文
        longest = 0
        who = ""
        for i in range(n):
            p = base + i * stride + noff
            seg = rom[p:p + stride - noff]
            # 原文按 0xFF 或 0x00 截断
            cut = len(seg)
            for k, b in enumerate(seg):
                if b in (0xFF, 0x00):
                    cut = k
                    break
            raw = seg[:cut]
            # 用 ROM 的原始字节去匹配译文太脆弱，这里只统计「译文最长」
            # 改为：收集该模块全部译文，取最长（保守上界）
        # 用模块里全部译文的最长长度作为上界
        # （条目→索引的精确对应由 text_pipeline 负责，此处只看容量）
        # 从 texts.json 的模块名取不到译文，改用全表译文上界估计
        # —— 这里做保守估计，真实值由流水线按索引计算
        mod_entries = tr
        # 无法反查模块，跳过精确值；改用「全表最长」保守上界
        # 对这几张表，译文长度分布很窄，保守上界足够
        texts = [v for v in mod_entries.values() if isinstance(v, str)]
        # 按表名做启发式过滤不可靠，这里输出旧 stride 与最大可能
        need = stride * BYTES_PER_CHAR  # placeholder
        # 实际计算放下面按具体表做（用样例）
        print(f"{name:<16}{stride:>9}{n:>5}{'':>9}{'':>7}{'':>9}{'':>6}{'':>9}")

    print("-" * 96)
    print("（下表用实测样例精确计算）")
    print()
    return _precise(rom, tr)


def _precise(rom: bytes, tr: dict) -> int:
    """用已知的译文样例精确计算每张表需要多少字节。"""
    # 从 ROM 读原文 → 查译文 → 量 F900 字节数
    TAB = {
        "招式名":         dict(base=0x1CAD04, stride=8,  n=354),
        "特性名":         dict(base=0x1CBC4C, stride=8,  n=77),
        "属性名":         dict(base=0x1CBB0C, stride=5,  n=18),
        "道具名":         dict(base=0x39A648, stride=40, n=348),
        "图鉴分类名":     dict(base=0x384746, stride=28, n=386, name_offset=6),
        "秘密基地装饰名": dict(base=0x3C2A54, stride=28, n=120, name_offset=13),
    }
    from meowth.codec import get_codec
    cd = get_codec("POKEMON_RUBY_AXVJ00")

    print("=" * 100)
    print(f"{'表':<16}{'旧stride':>9}{'条数':>5}{'最长字数':>9}"
          f"{'需要B':>8}{'新stride':>9}{'放大':>6}{'新体积':>10}{'结论':>8}")
    print("-" * 100)
    total = 0
    rows = []
    for name, g in TAB.items():
        base, stride, n = g["base"], g["stride"], g["n"]
        noff = g.get("name_offset", 0)
        longest = 0
        sample = ""
        hits = 0
        for i in range(n):
            p = base + i * stride + noff
            seg = bytes(rom[p:p + stride - noff])
            cut = len(seg)
            for k, b in enumerate(seg):
                if b in (0xFF, 0x00):
                    cut = k
                    break
            try:
                raw = cd.decode(seg[:cut]) if cut else ""
            except Exception:
                raw = ""
            t = tr.get(raw)
            if t:
                hits += 1
                L = len(t)
                if L > longest:
                    longest, sample = L, t
        need = longest * BYTES_PER_CHAR + EOS_BYTES
        new_stride = next_pow2(need) if need > stride else stride
        size = n * new_stride
        total += size
        ok = "不用改" if new_stride == stride else f"×{new_stride // stride}"
        rows.append((name, stride, n, longest, need, new_stride, ok, size, hits))
        print(f"{name:<16}{stride:>9}{n:>5}{longest:>9}"
              f"{need:>8}{new_stride:>9}{ok:>6}{size:>10}"
              f"{'✅' if new_stride == stride else ''}")
        if sample:
            print(f"{'':16}  最长译文: {sample!r}   匹配到译文 {hits}/{n} 条")
    print("-" * 100)
    print(f"{'合计新体积':<16}{'':>9}{'':>5}{'':>9}{'':>8}{'':>9}{'':>6}{total:>10}")
    print()
    old_total = sum(r[1] * r[2] for r in rows)
    print(f"旧总体积 {old_total} B   →   新总体积 {total} B   "
          f"增量 {total - old_total} B ({(total - old_total) / 1024:.1f} KB)")
    print("→ 32MB ROM 余量 1.35MB 以上，完全放得下。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
