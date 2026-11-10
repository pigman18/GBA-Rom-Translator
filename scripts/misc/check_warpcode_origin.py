#!/usr/bin/env python3
"""比对美版/日版 ROM，确认 GameShark warp 码地址属于哪个版本。

── 背景 ────────────────────────────────────────────────────────────────
用户从别处拿到「日版红宝石瞬移金手指」：
    02031F84:XXXX   （首位）    020322E4:XXXX    （备用）
实测两个地址在 AXVJ 里都能写入并**保持住**（08 00 一直不丢），
但穿门后地图仍是 0:2，没有跳到天元市。

符号表给出决定性证据：
    020300A0 g 000083d0 gPokemonStorage
⇒ 0x02031F84 落在 [0x020300A0, 0x020300A0+0x83d0) = **PC 宝可梦存储区内部**，
  根本不是 warp 变量。写进去只是污染了箱子数据。

那这些码是哪来的？本脚本做两件事：
  ① 打印 AXVJ / US 两个 ROM 的头信息（确认版本）
  ② 在符号表里查这两个地址在各版对应什么符号，给出书面结论

用法：python scripts/check_warpcode_origin.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYM = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "symbols" / "pokeruby_jp.sym"

ROMS = {
    "AXVJ (日版)": ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba",
    "US 1.0": ROOT / "roms" / "origin" / "Pokemon Ruby Version(US).gba",
    "US 1.1": ROOT / "roms" / "origin" / "Pokemon Ruby Version 1.1(US).gba",
    "US 1.2": ROOT / "roms" / "origin" / "Pokemon Ruby Version 1.2(US).gba",
}

ADDRS = [0x02031F84, 0x020322E4]

SIG = 0x08012025


def load_syms():
    """符号表：地址 -> (size, name)。"""
    out = []
    if not SYM.is_file():
        return out
    for line in SYM.read_text(encoding="utf-8", errors="replace").splitlines():
        p = line.split()
        if len(p) >= 4:
            try:
                addr = int(p[0], 16)
                size = int(p[2], 16)
            except ValueError:
                continue
            out.append((addr, size, p[3]))
    return out


def main() -> int:
    # ① ROM 头
    print("ROM 头信息（+0xA0 标题 / +0xAC 游戏码 / +0x10C 版本）")
    for label, p in ROMS.items():
        if not p.is_file():
            print(f"  {label:<12} 缺失")
            continue
        b = p.read_bytes()[:0x200]
        title = b[0xA0:0xAC].decode("ascii", "replace").strip("\x00 ")
        code = b[0xAC:0xB0].decode("ascii", "replace")
        maker = b[0xB0:0xB2].decode("ascii", "replace")
        rev = b[0xBC]
        print(f"  {label:<12} size={p.stat().st_size:>9}  title={title!r:<16} "
              f"code={code} maker={maker} rev={rev}")
        print(f"                sha1={__import__('hashlib').sha1(p.read_bytes()).hexdigest().upper()}")

    # ② 地址归属
    syms = load_syms()
    print(f"\n符号表 {SYM.name} 共 {len(syms)} 项")
    for a in ADDRS:
        owner = None
        for addr, size, name in syms:
            if addr <= a < addr + size and size > 0:
                owner = (addr, size, name)
                break
        if owner:
            addr, size, name = owner
            print(f"\n0x{a:08X} 落在 {name} 内"
                  f"（0x{addr:08X}..0x{addr + size:08X}，共 0x{size:X} 字节）")
            if "PokemonStorage" in name or "SaveBlock" in name:
                print("  ⇒ **是存档数据区，不是 warp 变量**。"
                      "写这个地址只会污染箱子/存档，不会传送。")
        else:
            print(f"\n0x{a:08X} 不在任何符号范围内（可能是未命名区或越界）")

    print("\n结论：")
    print("  这两个地址在 AXVJ 里对应的是存档数据（gPokemonStorage 内部），")
    print("  不是 warp 目的地变量。网传码表多半是**美版或绿宝石**的，")
    print("  跨版本直接套用无效 —— 写进去只是改了无关数据。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
