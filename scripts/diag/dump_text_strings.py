"""dump_text_strings.py — 提取指定函数引用的 PCS 字符串并解码

用于「窗口用途」判定：窗口显示什么文字，是它用途最直接的证据。

用法：
    python scripts/dump_text_strings.py 0x0800B140 0x0800B34C ...
    python scripts/dump_text_strings.py --from-callers   # 自动取 RunTextPrinter 的调用者
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from util.ruby_disasm import ROM_BASE, Rom, SymTab, find_callers  # noqa: E402

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"


def decode_pcs(rom: Rom, addr: int, limit: int = 96) -> tuple[str, int] | None:
    """从 addr 解码 PCS 文本，返回 (文本, 字节数)；不像文本则 None。"""
    if not (ROM_BASE <= addr < ROM_BASE + len(rom.data)):
        return None
    o = addr - ROM_BASE
    raw = []
    for i in range(limit):
        if o + i >= len(rom.data):
            return None
        b = rom.data[o + i]
        raw.append(b)
        if b == 0xFF:
            break
    else:
        return None
    if raw[-1] != 0xFF:
        return None
    try:
        from meowth.jp_pcs import decode_pcs as dec
        txt = dec(bytes(raw))
    except Exception:
        return None
    if not txt or len(txt) < 1:
        return None
    # 过滤明显垃圾：控制字符过多
    junk = sum(1 for c in txt if ord(c) < 0x20 and c not in "\n\r")
    if junk > len(txt) // 2:
        return None
    return txt, len(raw)


def func_head(rom: Rom, addr: int, back: int = 0x200) -> int:
    for d in range(0, back, 2):
        a = addr - d
        if a < ROM_BASE:
            break
        h = rom.u16(a)
        if (h & 0xFF00) == 0xB500:
            return a
    return addr


def literals(rom: Rom, start: int, size: int = 0x300) -> list[tuple[int, int]]:
    """[(指令地址, 字面量值)]"""
    out = []
    seen = set()
    a = start
    end = start + size
    while a < end:
        h = rom.u16(a)
        if (h & 0xF800) == 0x4800:
            imm = (h & 0xFF) * 4
            pool = ((a + 4) & ~3) + imm
            if pool not in seen:
                seen.add(pool)
                try:
                    out.append((a, rom.u32(pool)))
                except Exception:
                    pass
        a += 2
    return out


def report(rom: Rom, syms: SymTab, head: int, calls: list[int] | None = None) -> None:
    name = syms.name_of(head) or f"sub_{head:08X}"
    print(f"\n{'='*92}")
    print(f"■ {name}  @ 0x{head:08X}")
    if calls:
        print(f"  RunTextPrinter 调用点: {', '.join(f'0x{c:08X}' for c in calls)}")
    found = 0
    for ins, val in literals(rom, head, 0x300):
        r = decode_pcs(rom, val)
        if r:
            txt, n = r
            print(f"  0x{ins:08X} -> 0x{val:08X} [{n}B] \"{txt}\"")
            found += 1
    if not found:
        print("  （本函数无直接 PCS 文本字面量 —— 文本多由参数传入）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("addrs", nargs="*", help="函数地址")
    ap.add_argument("--from-callers", action="store_true")
    a = ap.parse_args()

    rom = Rom(ROM_PATH)
    syms = SymTab()

    if a.from_callers:
        s = syms.by_name.get("RunTextPrinter")
        if not s:
            print("找不到 RunTextPrinter")
            return 1
        calls = find_callers(rom, syms, s.addr)
        groups: dict[int, list[int]] = {}
        for src, _ in calls:
            groups.setdefault(func_head(rom, src), []).append(src)
        for head in sorted(groups):
            report(rom, syms, head, groups[head])
        return 0

    for x in a.addrs:
        head = func_head(rom, int(x, 0))
        report(rom, syms, head)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
