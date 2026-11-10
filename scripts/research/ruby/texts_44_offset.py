#!/usr/bin/env python3
"""texts_44: 为什么「0x3B2 局部 scan 模块」行不通 —— 串起点错位证明。

texts_43 的矛盾：
  剧情整段扫（0x144000..0x7F0FFF）在 0x3B2 收到 68 条
  新模块局部扫（0x3B2000..0x3B29FF）同样 filter 只收到 1 条、裸扫收到 129 条碎片

假设：extract_scan 从 start 起按「上一 FF 之后」定串起点。
局部 start=0x3B2000 落在某个串中间，于是切出一堆错位碎片。

本脚本验证：
  V1 0x3B2000 前一个 FF 在哪里（真实串起点应该在那儿之后）
  V2 把 start 往前挪到真实串起点，产出是否变干净
  V3 与剧情整段扫的条目集合对比

用法: python scripts/research/ruby/texts_44_offset.py
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

sys.path.insert(0, str(ROOT / "src"))
import util.texts_patcher as TP  # noqa: E402
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


def off_of(e) -> int:
    return to_int(e.get("address")) - 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    ptr_index = TP._build_ptr_index(rom)

    print("=" * 112)
    print("V1 0x3B2000 附近：真实串起点在哪")
    print("=" * 112)
    for probe in (0x3B2000, 0x3B2800):
        prev = rom.rfind(b"\xFF", max(0, probe - 256), probe)
        print(f"  0x{probe:06X} 之前最近的 FF 在 0x{prev:06X}"
              f"  （距 probe {probe - prev} 字节）")
        print(f"    从 probe 解码: {decode_pcs(rom[probe:probe + 40])!r}")
        if prev > 0:
            print(f"    从 FF 之后解码: {decode_pcs(rom[prev + 1:prev + 41])!r}")

    print()
    print("=" * 112)
    print("V2 剧情整段扫 vs 局部扫：0x3B2 区段的产出对比")
    print("=" * 112)
    story = d["modules"]["剧情"]
    main_f = TP.resolve_filters({"texts": {}}, story)

    # 剧情整段扫
    full = TP.extract_module(rom, dict(story, id="剧情"), "AXVJ",
                             ptr_index=ptr_index, filters=main_f)
    full_z = {off_of(e) for e in full if 0x3B2000 <= off_of(e) < 0x3B2A00}
    print(f"  剧情整段扫在 0x3B2 区段: {len(full_z)} 条")
    for off in sorted(full_z)[:6]:
        print(f"      0x{off:06X} {decode_pcs(rom[off:off + 24])!r}")

    # 局部扫（start 对齐到真实串起点）
    prev = rom.rfind(b"\xFF", 0x3B2000 - 256, 0x3B2000)
    for label, s in (("start=0x3B2000(错位)", 0x3B2000),
                     (f"start=0x{prev+1:06X}(对齐)", prev + 1)):
        m = {"id": "词库-0x3B2", "type": "scan",
             "start": f"0x{s:X}", "end": "0x3B29FF"}
        out = TP.extract_module(rom, m, "AXVJ", ptr_index=ptr_index, filters=None)
        got = {off_of(e) for e in out}
        print(f"\n  {label}: {len(got)} 条  与剧情交集 {len(got & full_z)}")
        for off in sorted(got)[:4]:
            print(f"      0x{off:06X} {decode_pcs(rom[off:off + 24])!r}")

    print()
    print("=" * 112)
    print("结论")
    print("=" * 112)
    print("  scan 模块的串起点取决于 start 之前的 FF 位置。")
    print("  局部切区间会让起点落在串中间，切出错位碎片 —— ")
    print("  所以「新建局部 scan 模块抢归属」这条路不可行。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
