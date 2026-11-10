#!/usr/bin/env python3
"""A2 关键问题：改成「指针数组」后，index×stride 的代码怎么办？

现状（道具名）：
  - 代码：r0 = 0x39A648 + idx*40，然后 ldrh [r0, #0xa] 之类取字段
  - 我们把基址改成「指针数组地址」
  - 但代码仍会算 ptrarr_base + idx*40 ← 完全错位！

所以「改字面量指向指针数组」**只在 stride==4 时成立**。
道具名 stride=40，不行。

两条正确路线：

  路线 A（保持 stride，简单）
    新表 = 同样的 40 字节结构，只把名字字段换成中文
    字面量改成新表基址 → 代码无感
    约束：中文 ≤ 40 字节（实测原文最长 9B，空间充裕）
    ✅ 这是道具名该走的路

  路线 B（变长 + 指针数组，需改代码）
    必须同时把 index×40 改成 index×4
    要改机器码，风险高

本脚本验证路线 A：新表保持 40 字节结构，中文塞进去。

用法：
    python scripts/research/ruby/a2_route_a.py
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

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000

BASE = 0x39A648
STRIDE = 40
NAME_OFF = 0x28
NAME_CAP = STRIDE        # 名字可用 40 字节（到下个名字）
N = 348


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import (ExpandAllocator, expand_fixed,
                                     encode_body, describe)

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    items = {}
    for e in d.get("entries") or []:
        if e.get("module") != "道具名":
            continue
        try:
            addr = int(str(e.get("address") or "").replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        items[addr] = e

    print(f"=== 路线 A：保持 stride=40，整体复制结构 ===")
    print(f"  base=0x{BASE:06X} stride={STRIDE} name@+0x{NAME_OFF:X} "
          f"名字可用 {NAME_CAP}B\n")

    # 构造新表：整体复制原 40B 结构，只替换 +0x28 的名字
    blob = bytearray()
    fits = over = 0
    over_samples = []

    for i in range(N):
        base = BASE + i * STRIDE
        item = bytearray(rom[base:base + STRIDE])

        # 名字部分在 item[0x28:0x28+40] 但超出 item 边界
        # 实际名字跨越了本项 40B 之后的 40B —— 说明结构是：
        #   item[i] 的 40B 是「头」，名字紧跟在头之后
        # 更准确：名字区 = [base+0x28, base+0x28+40)
        name_at = base + NAME_OFF
        name_seg = rom[name_at:name_at + NAME_CAP]

        e = items.get(name_at)
        text = (e.get("translated") or "") if e else ""
        if text:
            body = encode_body(cm, text)
        else:
            ff = name_seg.find(b"\xFF")
            body = name_seg[:ff + 1] if ff >= 0 else name_seg

        if len(body) <= NAME_CAP:
            fits += 1
        else:
            over += 1
            if len(over_samples) < 5:
                over_samples.append((i, text, len(body)))
            body = body[:NAME_CAP - 1] + bytes([0xFF])

        # 写入：头部 40B + 名字 40B = 80B 组合？
        # 不 —— 结构是每项 40B 头 + 40B 名字，交错的。
        # 简化：新表 = [头0][名0][头1][名1]...  步长 80
        blob += rom[base:base + NAME_OFF]
        blob += body + bytes([0x00]) * (NAME_CAP - len(body))

    print(f"  塞得下: {fits}   超长: {over}")
    for i, t, n in over_samples:
        print(f"    item{i} {t!r} = {n}B")

    print()
    print(f"  新表大小 {len(blob):,} B（{N} 项 × {NAME_OFF + NAME_CAP}B = "
          f"{N * (NAME_OFF + NAME_CAP):,}）")

    # 注意：如果结构是「头 40B + 名字 40B」交错，则新步长是 80，不是 40
    # 那代码里的 index*40 依然不匹配！
    print()
    print("  ⚠️ 关键：若名字与头交错（步长 80），代码的 index*40 仍不匹配。")
    print("  必须确认：名字是「头的一部分」还是「独立数组」。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
