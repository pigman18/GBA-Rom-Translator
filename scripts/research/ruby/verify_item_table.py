#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 gen/table_data.asm 里道具名新表的字段位置是否与补丁假设一致。

必须有这一步：字段排布一旦和补丁里的立即数对不上，游戏就会读到
名字尾部当指针用 —— 背包卡死。所以生成后必须逐字段核对。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ASM = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "gen" / "table_data.asm"
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

# 期望的字段排布（与 emit_table_data.TABLES["道具名"]["field_map"] 一致）
EXPECT = [
    (0x0A, 0x12, 2, "u16"),
    (0x0C, 0x14, 2, "u16"),
    (0x0E, 0x16, 1, "u8"),
    (0x0F, 0x17, 1, "u8"),
    (0x10, 0x24, 4, "ptr"),
    (0x14, 0x18, 1, "u8"),
    (0x15, 0x19, 1, "u8"),
    (0x16, 0x1A, 1, "u8"),
    (0x17, 0x1B, 1, "u8"),
    (0x18, 0x20, 4, "ptr"),
    (0x1C, 0x1C, 2, "u16"),
    (0x20, 0x28, 4, "u32"),
]

STRIDE = 48
NAME_CAP = 17
OLD_BASE = 0x39A648
OLD_STRIDE = 40


def main() -> int:
    src = ASM.read_text(encoding="utf-8")
    i = src.find("; ---- 道具名")
    if i < 0:
        print("[ERR] table_data.asm 里找不到道具名段")
        return 3
    j = src.find("TblItemNames", i)
    k = src.find("; ----", j)
    seg = src[j:k]

    bs: list[int] = []
    for line in seg.splitlines():
        if ".byte" in line:
            bs += [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})", line)]
    new = bytes(bs)
    rom = ROM.read_bytes()

    print(f"道具名新表 {len(new):,} B  = {len(new) // STRIDE} 项 × {STRIDE} B")
    if len(new) % STRIDE:
        print("  ★ 长度不是 stride 整数倍")
        return 1

    bad = 0
    # 抽查 5 项（含首尾）
    for idx in (0, 1, 2, 100, 347):
        print(f"\nentry[{idx}]")
        old_e = OLD_BASE + idx * OLD_STRIDE
        new_e = idx * STRIDE
        name_seg = rom[old_e:old_e + 9]
        name_ok = new[new_e:new_e + 9][:1] == b"\xf9" or name_seg[:1] != b"\xf9"
        print(f"  名字  {new[new_e:new_e + NAME_CAP].hex(' ')}")
        for old_off, new_off, width, kind in EXPECT:
            want = rom[old_e + old_off:old_e + old_off + width]
            got = new[new_e + new_off:new_e + new_off + width]
            ok = "OK" if want == got else "★MISMATCH"
            if want != got:
                bad += 1
            print(f"  +0x{new_off:02X} {kind:4s} (旧+0x{old_off:02X}) "
                  f"want={want.hex():10s} got={got.hex():10s} {ok}")

    print()
    if bad:
        print(f"★ {bad} 处字段校验失败 —— 补丁的立即数会与表内容脱节")
        return 1
    print("全部字段位置与预期一致。")
    print()
    print("对应补丁（scripts/research/ruby/gen_item_stride.py 生成）：")
    print("  ldrh/ldrb 立即数 → 0x12/0x14/0x16/0x17/0x18/0x19/0x1A/0x1B")
    print("  adds r4 立即数   → 0x24/0x20/0x28")
    print("  +0x1C 三处访问点保持原偏移，不改")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
