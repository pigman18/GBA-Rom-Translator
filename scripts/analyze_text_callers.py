"""analyze_text_callers.py — 逐个分析 RunTextPrinter 调用点所属场景

对每个调用点做三件事（全静态）：
1. 回溯到所属函数头（THUMB `push {.., lr}`）
2. 反汇编该函数，抓所有 `ldr rX,=...` 字面量 —— 其中常有字符串指针、模板指针
3. 对每个指向 ROM 的指针，判断它是不是 PCS 文本（尝试用 PCS 编码解码）

输出：每个调用点的 {函数名, 函数地址, 相关字面量, 可能的文本内容}
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from util.ruby_disasm import ROM_BASE, Rom, SymTab, find_callers  # noqa: E402

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

# PCS (Gen3 日版字符集) 的部分映射，用于判断「这个指针指向的是不是文本」
# 只覆盖常见假名/数字，足以判别
PCS_JUNK_MIN = 0x20


def is_probably_text(rom: Rom, addr: int) -> tuple[bool, str]:
    """粗判 addr 处是否 PCS 文本：连续可印码且以 FF 结尾。"""
    if not (ROM_BASE <= addr < ROM_BASE + len(rom.data)):
        return False, ""
    o = addr - ROM_BASE
    out = []
    n = 0
    for i in range(0, 64):
        if o + i >= len(rom.data):
            break
        b = rom.data[o + i]
        if b == 0xFF:
            return (n >= 2), "".join(out)
        if b == 0x00:
            out.append(" ")
            n += 1
            continue
        # 0x01..0xF6 视为可印（Gen3 日版基本如此）
        if 0x01 <= b <= 0xF6:
            out.append("·")
            n += 1
        else:
            break
    return False, "".join(out)


def func_head(rom: Rom, addr: int, back: int = 0x200) -> int:
    for d in range(0, back, 2):
        a = addr - d
        if a < ROM_BASE:
            break
        h = rom.u16(a)
        if (h & 0xFF00) == 0xB500:
            return a
    return addr


def literal_refs(rom: Rom, start: int, size: int = 0x400) -> list[tuple[int, int, int]]:
    """扫函数体，返回 [(指令地址, 池地址, 值)]，值为 ldr rX,[pc,#imm] 读到的 u32。"""
    out = []
    end = start + size
    a = start
    seen_pools = set()
    while a < end:
        h = rom.u16(a)
        if (h & 0xF800) == 0x4800:
            imm = (h & 0xFF) * 4
            pool = ((a + 4) & ~3) + imm
            if pool not in seen_pools:
                seen_pools.add(pool)
                try:
                    val = rom.u32(pool)
                    out.append((a, pool, val))
                except Exception:
                    pass
        a += 2
    return out


def main() -> None:
    rom = Rom(ROM_PATH)
    syms = SymTab()

    s = syms.by_name.get("RunTextPrinter")
    if not s:
        print("找不到 RunTextPrinter 符号")
        return

    callers = find_callers(rom, syms, s.addr)
    print(f"RunTextPrinter @0x{s.addr:08X} 共有 {len(callers)} 个调用点\n")

    # 按所属函数归组
    groups: dict[int, list[int]] = {}
    for src, _nm in callers:
        head = func_head(rom, src)
        groups.setdefault(head, []).append(src)

    print(f"归入 {len(groups)} 个函数\n")
    print("=" * 108)

    for head in sorted(groups):
        calls = groups[head]
        name = syms.name_of(head) or f"sub_{head:08X}"
        sym = syms.at(head)
        note = sym.note if sym else ""
        print(f"\n■ {name} @ 0x{head:08X}  ({len(calls)} 处调用)  {note[:40]}")
        for c in calls:
            print(f"    调用点 0x{c:08X}")

        # 该函数的字面量
        refs = literal_refs(rom, head, 0x300)
        texts = []
        others = []
        for ins, pool, val in refs:
            if ROM_BASE <= val < ROM_BASE + len(rom.data):
                ok, txt = is_probably_text(rom, val)
                if ok:
                    texts.append((ins, val, txt))
                elif val > 0x08000000 and val < 0x0A000000:
                    others.append((ins, val))
        if texts:
            print(f"    ── 可能文本字面量 {len(texts)} 个：")
            for ins, val, txt in texts[:8]:
                print(f"       0x{ins:08X} -> 0x{val:08X}  \"{txt[:24]}\"")
        if others:
            names = []
            for ins, val in others[:6]:
                nm = syms.name_of(val)
                names.append(f"0x{val:08X}" + (f"({nm})" if nm else ""))
            print(f"    ── 其他 ROM 指针: {', '.join(names)}")

    print("\n" + "=" * 108)
    print(f"合计 {len(groups)} 个函数 / {len(callers)} 个调用点")


if __name__ == "__main__":
    main()
