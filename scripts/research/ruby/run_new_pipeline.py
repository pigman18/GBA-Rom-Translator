#!/usr/bin/env python3
"""用 text_pipeline 跑一遍完整四步（不接 engine，先验证可行性）。

输入：texts.json（模块几何）+ texts_translated.json（译文）
输出：容器分布 + 表处理结果 + patch 统计

关键：encoder 用工程实际的 Charmap.encode，它把中文编成
      F9 00 hi lo（零运行时查表），末尾补 0xFF —— 正是火红协议的对齐形态。

用法：
    python scripts/research/ruby/run_new_pipeline.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

GAME = "POKEMON_RUBY_AXVJ00"
ROM = ROOT / "roms" / "origin" / f"{GAME}.gba"
TEXTS = ROOT / "configs" / GAME / "translate" / "texts.json"
TRANS = ROOT / "configs" / GAME / "translate" / "texts_translated.json"

# 定长表几何（实测，texts_ground_truth.py 确认）
TABLES = {
    "招式名":         dict(base=0x1CAD04, stride=8,  n=354, usable=8,  eos=0xFF),
    "特性名":         dict(base=0x1CBC4C, stride=8,  n=77,  usable=8,  eos=0xFF),
    "属性名":         dict(base=0x1CBB0C, stride=5,  n=18,  usable=5,  eos=0xFF),
    "道具名":         dict(base=0x39A648, stride=40, n=348, usable=40, eos=0xFF,
                          name_offset=0),
    "图鉴分类名":     dict(base=0x384746, stride=28, n=386, usable=22, eos=0x00,
                          name_offset=6),
    "秘密基地装饰名": dict(base=0x3C2A54, stride=28, n=120, usable=15, eos=0xFF,
                          name_offset=13),
}


def build_charmap():
    """按 engine 的方式构造 Charmap。

    关键：charmap_path 是中文→码位映射表，engine 通过
    ``_resolve_charmap_cfg_path`` 注入（config_loader.get_charmap_path）。
    不传它的话 char_to_bytes 为空，中文会被静默丢弃 —— 实测踩到过。
    """
    import meowth.config_loader as CL
    from meowth.charmap import Charmap

    cfg = CL.load_game_config(GAME)
    cm_cfg = dict(cfg.get("charmap") or {})
    codec_cm = (CL.load_codec(GAME) or {}).get("charmap") or {}
    if isinstance(codec_cm, dict):
        cm_cfg = {**codec_cm, **cm_cfg}
    cm_cfg["charmap_path"] = str(CL.get_charmap_path(GAME))
    return Charmap(target_lang="zh-Hans", charmap_cfg=cm_cfg)


def main() -> int:
    from meowth.text_pipeline import run_pipeline

    rom = ROM.read_bytes()
    tj = json.loads(TEXTS.read_text(encoding="utf-8"))
    entries = tj["entries"]
    tt = json.loads(TRANS.read_text(encoding="utf-8"))
    tr = {e["original"]: e["translated"] for e in tt if e.get("translated")}

    n_tr = 0
    for e in entries:
        t = tr.get(e.get("original") or "")
        if t:
            e["translated"] = t
            n_tr += 1

    charmap = build_charmap()

    def encoder(text: str) -> bytes:
        return charmap.encode(text)

    # 冒烟测试：确认编码是 F9 00 形态
    sample = encoder("拍击")
    print("=" * 84)
    print("text_pipeline 实跑（READ → CLASSIFY → PLACE → RELINK）")
    print("=" * 84)
    print(f"编码冒烟: '拍击' -> {sample.hex(' ')}")
    print(f"  形态检查: {'✓ F9 00 单字流' if sample[:2] == b'\\xf9\\x00' else '⚠ 非 F9 00'}")
    print()
    print(f"条目 {len(entries)}   有译文 {n_tr}   定长表 {len(TABLES)}")

    result = run_pipeline(rom, entries, TABLES, encoder=encoder)

    print()
    print("容器分布:")
    for k, v in Counter(e.container for e in result.entries).most_common():
        print(f"  {k:<16} {v:>6}")

    print()
    print(f"tables 处理: {len(result.tables)}")
    for t in result.tables:
        print(f"  {t.name:<14} {t.mode:<9} stride {t.orig_stride}→{t.new_stride}  "
              f"{t.n_entries:>4} 条  {t.size:>7} B  @0x{t.new_base:06X}")

    print()
    print(f"byte_patches: {len(result.byte_patches)}")
    s = result.summary
    print(f"新区占用: {s.get('alloc_used')} B   剩余: {s.get('alloc_remaining')} B")

    # 关键：确认没有任何 F9 80 引用
    bad = [e for e in result.entries if b"\\xf9\\x80" in e.encoded[:4]]
    print(f"F9 80 短语引用: {len(bad)} 条 "
          f"{'✓ 零查表' if not bad else '⚠ 仍有残留'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
