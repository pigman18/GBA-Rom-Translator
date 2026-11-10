#!/usr/bin/env python3
"""texts_63: 结论 —— 0x3B3E64 表与 926 条词库的最终判定。

汇总 texts_56~62 全部实测，给出可执行的结论。

事实清单：
  F1 表 @0x3B3E64，22 项，全指向词库；22 项地址单调递增（词库有序子集）
  F2 有 9 处代码字面量（0xE6058..0xE6D24）加载该表地址 → 表被代码使用
  F3 9 个函数是匿名 sub_80E9xxx/sub_80EAxxx，各自独立（不同 size）
  F4 表项内容：16 短词/称呼 + 1 句 + 1 单字 + 4 空
  F5 词库本体 980 段 / 926 干净词条，按假名排序
  F6 926 条中仅 15 条被 u32 指针直接指向（含这 22 项中的 15 条）
  F7 表前 0x3B3C6A..0x3B3E64 有 253 个 u16（值 0..249）
  F8 表后 0x3B3EBC.. 是 u16（值 256~786）

用法: python scripts/research/ruby/texts_63_final.py
"""
from __future__ import annotations

import struct
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
BASE = 0x08000000
TABLE = 0x3B3E64

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402


def read_str(rom: bytes, off: int) -> str:
    for i in range(off, min(len(rom), off + 64)):
        if rom[i] == 0xFF:
            return decode_pcs(rom[off:i + 1])
    return ""


def main() -> int:
    rom = ROM_PATH.read_bytes()
    import json
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    have = {e["address"] for e in d["entries"]}

    print("=" * 112)
    print("22 项：是否已在 texts.json 中收录")
    print("=" * 112)
    in_t = 0
    for k in range(22):
        v = struct.unpack_from("<I", rom, TABLE + k * 4)[0]
        if not (BASE <= v < BASE + len(rom)):
            continue
        t = v - BASE
        va = f"0x{BASE + t:08X}"
        ok = va in have
        in_t += 1 if ok else 0
        print(f"  [{k:>2}] 0x{t:06X} {read_str(rom, t)!r:<24} "
              f"{'已收录' if ok else '未收录'}")
    print(f"\n  已收录 {in_t} / 22")

    print()
    print("=" * 112)
    print("最终判定")
    print("=" * 112)
    print("""
  【表 0x3B3E64 是什么】
    · 22 项指针，指向词库 926 条中的 22 条（有序子集，按假名序）
    · 被 9 个独立函数用字面量引用（0xE6058..0xE6D24）→ 确有代码在用
    · 22 项内容混合：称呼/短词 16 + 句子 1 + 单字 1 + 空 4
    · 序号差 42~109 不等距 → 不是规则采样，是「功能所需的具体词条」

  【它是不是「显示给玩家的文本」】
    · 是。'きみにきめた！'(经典开场)、'ありがとう'、'あいて'、
      'アルバイト'、'アイドル'、'アピール' 都是玩家可见的通用词
    · 9 个函数规模都不大（0x24~0x1FC 字节），像「按索引取词显示」的小函数

  【800+ 条无指针词条该不该翻译】
    结论：**该翻，但优先级低**。
    · 依据 1：这 22 项证明词库是会被显示的文本源
    · 依据 2：那 9 个函数只用了 22 项，剩余 904 条没有任何直接引用路径
    · 依据 3：但「零引用 ≠ 不显示」——本项目已有 842 条剧情零指针却是真台词的先例，
      很可能是「基址 + 计算索引」访问（表前的 253 个 u16 数组就是索引结构）
    · 风险：整块翻译成本高（926 条），而只有 22 条确认被显示

  【建议】
    1. 不建独立模块去「抢」这 926 条——它们已在 剧情/UI界面 里，无害
    2. 若要翻译，只翻这 22 项（已收录 15 项），其余标为「待实测」
    3. 彻底结论需阶段 C 用 bot 走到那个界面，看是否真有词库内容显示
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
