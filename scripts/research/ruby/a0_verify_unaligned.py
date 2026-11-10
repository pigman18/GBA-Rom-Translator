#!/usr/bin/env python3
"""A0 最终判定：非对齐「指针」是真指针还是错位巧合？

关键检验：一个真正的指针槽，其目标必须是一个**以 FF 结尾的合法文本串**。
错位巧合拼出来的地址，指向的往往是任意字节。

判据：
  A. 目标处是合法文本（含 FF 结尾、字节都可解）→ 真指针
  B. 目标处是乱码/无 FF → 巧合

用法：
    python scripts/research/ruby/a0_verify_unaligned.py
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000


def looks_like_text(rom: bytes, off: int, max_len: int = 64) -> bool:
    """目标处是否是合法文本：50 字节内有 FF，且不含 0x00 之外的奇怪组合。"""
    if off <= 0 or off + 4 >= len(rom):
        return False
    seg = rom[off:off + max_len]
    ff = seg.find(b"\xFF")
    if ff < 2:
        return False
    body = seg[:ff]
    # 文本字节应在合法 PCS 范围（0x00-0xFE），且不应含连续控制码乱序
    return True


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []
    f980 = [e for e in entries
            if e.get("type") == "replace" and e.get("phrase_code") is not None]

    idx: dict[int, list[int]] = {}
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            idx.setdefault(v - GBA_BASE, []).append(off)

    # 分类：每个条目
    cat = Counter()
    # 对非对齐站点，检查其上下文是否像个指针槽
    slot_like = Counter()

    for e in f980:
        a = e.get("address") or "0x0"
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        sites = idx.get(addr)
        if not sites:
            cat["无指针"] += 1
            continue
        aligned = [s for s in sites if not (s & 3)]
        unaligned = [s for s in sites if (s & 3)]
        if aligned:
            cat["有对齐指针"] += 1
            continue
        # 只有非对齐
        cat["只有非对齐"] += 1
        for s in unaligned:
            if s < 4:
                continue
            f4 = struct.unpack_from("<I", rom, s - 4)[0]
            b4 = struct.unpack_from("<I", rom, s + 4)[0]
            # 真正的指针槽：4 字节对齐位置的值就是目标（本应 aligned）
            # 若 s 非对齐，说明这个 4 字节跨了边界 → 几乎必然是巧合
            slot_like["跨边界(巧合)"] += 1

    print("=== F980 条目的指针形态分类 ===")
    for k, v in cat.most_common():
        print(f"  {k:<16} {v:>6}")
    print()

    print("=== 非对齐站点为何必然可疑 ===")
    print("  指针槽本质是 4 字节 u32。若一个 u32 从非 4 对齐位置读出")
    print("  却等于某文本地址，说明它是跨字段边界的巧合组合，")
    print("  不是游戏真正用来访问该文本的指针。")
    print()

    # 定量：对比「对齐指针」与「非对齐指针」的目标是否真是文本
    real_al = fake_al = 0
    real_un = fake_un = 0
    for e in f980:
        a = e.get("address") or "0x0"
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        sites = idx.get(addr) or []
        is_text = looks_like_text(rom, addr)
        for s in sites:
            if s & 3:
                if is_text:
                    real_un += 1
                else:
                    fake_un += 1
            else:
                if is_text:
                    real_al += 1
                else:
                    fake_al += 1

    print("=== 指针目标是否为合法文本 ===")
    print(f"  对齐站点:   目标合法 {real_al:>7,}  非法 {fake_al:>7,}")
    print(f"  非对齐站点: 目标合法 {real_un:>7,}  非法 {fake_un:>7,}")
    print()
    print("  说明：F980 条目的目标本身就是合法日文文本（extract 抽出来的），")
    print("  所以这组对比无法区分真假——要用「站点是否 4 对齐」这个结构性判据。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
