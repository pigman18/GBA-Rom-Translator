#!/usr/bin/env python3
"""texts_21: 修正 texts_20 暴露的两处文档错误，并定出树果名的精确 end。

要证伪/证实的三件事：
  E1 「道具名 需要 name_offset=0x28」 —— 错。
     index 0 @0x39A648 就是占位符 '？？？？？？？？'，
     name@0 + 跳过占位符 已经能拿到全部 281 条，加 name_offset 反而错。
  E2 「宝可梦名 末条 チリーン 是跨槽误读」 —— 错。
     0x1CACF6 的 5 字节 61 78 ae 7e ff 就是 'チリーン'，且在图鉴词表里命中。
     end=0x1CACFB 的 412 槽全对；条目 411 = 412 - 1 个占位符被 filter 跳过，属正常。
  E3 树果名 stride=28 时，end 仍为 0x3A14E8 只能拿到 42 条（末槽 'ナゾ' 落在槽外）。
     要收到 43 条（含 ナゾ），end 需 >= 0x3A14E8 + 28 - 1 = 0x3A1503。

用法: python scripts/research/ruby/texts_21_fix_boundaries.py
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
LEX = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "lexicon"

sys.path.insert(0, str(ROOT / "src"))
import util.texts_patcher as TP  # noqa: E402
from meowth.jp_pcs import decode_pcs  # noqa: E402


def slot_text(rom: bytes, off: int, window: int, eos: int = 0xFF) -> str:
    lim = min(len(rom), off + window)
    for i in range(off, lim):
        if rom[i] == eos:
            return decode_pcs(rom[off:i + 1])
    return ""


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    by_mod: dict[str, list] = {}
    for e in d["entries"]:
        by_mod.setdefault(e.get("module"), []).append(e)

    print("=" * 112)
    print("E1 道具名：name@0 是否正确？")
    print("=" * 112)
    total = (0x39DCA7 - 0x39A648 + 1) // 40
    real = 0
    holders = 0
    for i in range(total):
        t = slot_text(rom, 0x39A648 + i * 40, 40)
        if not t:
            continue
        if set(t) <= set("？ー- "):
            holders += 1
        else:
            real += 1
    print(f"  槽总数 {total}；非名槽 {holders}（含占位符）；真名字槽 {real}")
    print(f"  texts.json 条目 {len(by_mod.get('道具名', []))}")
    print(f"  => name@0 可直接取到 {real} 条 {'✅ 与配置一致' if real == len(by_mod.get('道具名', [])) else '❌ 不一致'}")
    print("  结论：道具名无需 name_offset，文档原建议作废。")
    print()

    print("=" * 112)
    print("E2 宝可梦名：末槽 'チリーン' 是真名字还是误读？")
    print("=" * 112)
    s, e, st = 0x1CA354, 0x1CACFB, 6
    n = (e - s + 1) // st
    lex = json.loads((LEX / "图鉴.json").read_text(encoding="utf-8"))
    raw = rom[s + (n - 1) * st: s + (n - 1) * st + st]
    t = slot_text(rom, s + (n - 1) * st, st)
    print(f"  末槽 index {n-1} @0x{s + (n-1)*st:06X}")
    print(f"    原始字节 {raw.hex(' ')}  ->  {t!r}")
    print(f"    在 图鉴.json 词表: {t in lex}")
    # 词表里 チリーン 的译名
    print(f"    词表值: {lex.get(t)!r}")
    print(f"  槽总数 {n}，配置条目 {len(by_mod.get('宝可梦名', []))}"
          f"（差 {n - len(by_mod.get('宝可梦名', []))} = 被跳过的那 1 个 '？？？？？'）")
    print("  结论：チリーン 是真名字，宝可梦名几何完全正确，文档原建议作废。")
    print()

    print("=" * 112)
    print("E3 树果名：收满 43 条所需的 end")
    print("=" * 112)
    bs, be, bst = 0x3A1050, 0x3A14E8, 28
    for end in (0x3A14E8, 0x3A14FF, 0x3A1503, 0x3A1504):
        cnt = (end - bs + 1) // bst
        last = slot_text(rom, bs + (cnt - 1) * bst, bst)
        print(f"  end=0x{end:06X} -> {cnt:>3} 槽，末槽 {last!r}")
    print()
    # 用真实抽取器验证
    for end in ("0x3a14e8", "0x3a1503"):
        mod = {"id": "树果名", "type": "struct", "start": "0x3a1050", "end": end,
               "read": {"entry_size": 28, "name_offset": 0, "desc_ptr_offset": 0x10}}
        out = TP.extract_module(rom, mod, "AXVJ", filters=None)
        print(f"  抽取器 end={end}: {len(out)} 条，末条 {out[-1]['original']!r} "
              f"@0x{int(out[-1]['address'],16):X}" if out else f"  end={end}: 0 条")
    print()
    print("  0x3A1504 起是什么：")
    print(f"    {rom[0x3A1504:0x3A1504+16].hex(' ')}")
    print("  结论：stride=28 且 end=0x3A1503 才收满 43 条；"
          "end 保持 0x3A14E8 只有 42 条（丢 ナゾ）。")
    print()

    print("=" * 112)
    print("E4 复核仍成立的两条：地点名起点 / 训练家名起点")
    print("=" * 112)
    print(f"  地点名 0x3BECB0 -> {slot_text(rom, 0x3BECB0, 16)!r}（当前起点之前，真地名）")
    print(f"  训练家名 0x1C4A10 -> {slot_text(rom, 0x1C4A10, 24)!r}（含前导碎片）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
