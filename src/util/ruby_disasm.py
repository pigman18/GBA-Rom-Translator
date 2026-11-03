"""ruby_disasm.py — AXVJ(日版红宝石) 静态反汇编基础设施

用途：给窗口系统分析提供可复现的反汇编依据。只做静态读 ROM，不启动模拟器。

核心能力
- 递归下降反汇编（THUMB），跟 BL/BX 字面量池，避开数据段
- 符号解析：从 symbols/pokeruby_jp.sym 查地址 -> 名字
- 字面量池识别（ldr rX, [pc, #imm] -> 读池中 u32）
- 调用图：列出函数内所有 bl 目标及其符号名

用法：
    python src/util/ruby_disasm.py 0x080032F8 --count 80
    python src/util/ruby_disasm.py --sym PrintNextChar
    python src/util/ruby_disasm.py --find-callers 0x08002A50
"""
from __future__ import annotations

import argparse
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

ROOT = Path(__file__).resolve().parents[2]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
SYM_PATH = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "symbols" / "pokeruby_jp.sym"

ROM_BASE = 0x08000000


@dataclass
class Sym:
    addr: int
    kind: str        # g / l
    size: int
    name: str
    note: str        # VERIFIED / UNVERIFIED(seg=...) / KEEP-US


class SymTab:
    def __init__(self, path: Path = SYM_PATH) -> None:
        self.by_addr: dict[int, Sym] = {}
        self.by_name: dict[str, Sym] = {}
        if not path.is_file():
            return
        pat = re.compile(r"^([0-9A-Fa-f]{8})\s+([gl])\s+([0-9A-Fa-f]{8})\s+(\S+)\s*(.*)$")
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = pat.match(line)
            if not m:
                continue
            addr = int(m.group(1), 16)
            s = Sym(addr, m.group(2), int(m.group(3), 16), m.group(4), m.group(5).strip())
            self.by_addr[addr] = s
            self.by_name.setdefault(s.name, s)

    def at(self, addr: int) -> Sym | None:
        return self.by_addr.get(addr)

    def name_of(self, addr: int) -> str:
        s = self.at(addr & ~1)
        if s:
            return s.name
        # 退一步：找最近的、地址不高于它的符号（有 size 时判定包含）
        best = None
        for a, s in self.by_addr.items():
            if a <= addr and s.size:
                if a + s.size > addr and (best is None or a > best[0]):
                    best = (a, s)
        return f"{best[1].name}+0x{addr - best[0]:X}" if best else ""


class Rom:
    def __init__(self, path: Path = ROM_PATH) -> None:
        self.data = path.read_bytes()

    def read(self, addr: int, n: int) -> bytes:
        o = addr - ROM_BASE
        return self.data[o : o + n]

    def u16(self, addr: int) -> int:
        return struct.unpack_from("<H", self.data, addr - ROM_BASE)[0]

    def u32(self, addr: int) -> int:
        return struct.unpack_from("<I", self.data, addr - ROM_BASE)[0]

    def half(self, addr: int) -> int:
        return self.u16(addr)


def is_ldr_pc(h: int) -> bool:
    """THUMB `ldr rX, [pc, #imm8*4]`（0x4800..0x4FFF）。"""
    return (h & 0xF800) == 0x4800


def ldr_pool_addr(addr: int, h: int) -> int:
    imm = (h & 0xFF) * 4
    return ((addr + 4) & ~3) + imm


def disasm_func(rom: Rom, syms: SymTab, addr: int, max_insn: int = 400) -> list[dict]:
    """线性反汇编一段（含字面量池解析）。

    ⚠️ 关键：遇到 `ldr rX,[pc,#imm]` 时，字面量池就在紧随的 4 字节对齐处，
    **必须跳过池内容**，否则会把 u32 数值当指令解出 `adds r3,#0x24` 这类垃圾
    （实测：PrintNextChar 的跳表 0x08003324 被解成了 adds/lsrs 序列）。
    这里做的是「线性扫描 + 池跳读」：解到 ldr 时记录池地址，若下一条指令地址
    落在池范围内就跳过。
    """
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True
    out: list[dict] = []
    pc = addr & ~1
    code = rom.read(pc, max_insn * 2)
    skip_until = 0
    for ins in md.disasm(code, pc):
        if ins.address < skip_until:
            continue
        row = {
            "addr": ins.address,
            "bytes": ins.bytes.hex(),
            "mnem": ins.mnemonic,
            "op": ins.op_str,
        }
        h = int.from_bytes(ins.bytes[:2], "little")
        if is_ldr_pc(h):
            pool = ldr_pool_addr(ins.address, h)
            try:
                val = rom.u32(pool)
                row["pool"] = (pool, val)
                n = syms.name_of(val)
                if n:
                    row["pool_sym"] = n
            except Exception:
                pass
            # 跳过整个常量块：从 pool 起，连续读 u32，只要它「像指针」
            # （0x08xxxxxx 代码/数据地址）就当池成员继续跳过。
            # PrintNextChar 的 FA-FF 跳表有 6 项共 24 字节，只跳 4 会
            # 把后 5 项解成 adds/lsrs 垃圾（实测）。
            end = pool
            while end + 4 <= len(rom.data) + ROM_BASE:
                try:
                    v = rom.u32(end)
                except Exception:
                    break
                if 0x08000000 <= v < 0x0A000000:
                    end += 4
                else:
                    break
            skip_until = max(skip_until, end, pool + 4)
        if ins.mnemonic == "bl" and ins.op_str.startswith("#"):
            try:
                tgt = int(ins.op_str[1:], 0)
                row["call"] = tgt
                n = syms.name_of(tgt)
                if n:
                    row["call_sym"] = n
            except ValueError:
                pass
        out.append(row)
        if len(out) >= max_insn:
            break
    return out


def fmt(rows: list[dict], syms: SymTab, show_bytes: bool = True) -> str:
    lines = []
    for r in rows:
        n = syms.at(r["addr"])
        label = f"  {n.name}:" if n else ""
        b = f"{r['bytes']:<10}" if show_bytes else ""
        line = f"0x{r['addr']:08X}  {b} {r['mnem']:<7} {r['op']}"
        if "pool" in r:
            pool, val = r["pool"]
            extra = r.get("pool_sym", "")
            line += f"    ; [0x{pool:08X}] = 0x{val:08X}" + (f" = {extra}" if extra else "")
        elif "call" in r:
            extra = r.get("call_sym", "")
            line += f"    ; -> {extra}" if extra else ""
        lines.append(label + line if label else line)
    return "\n".join(lines)


def find_callers(rom: Rom, syms: SymTab, target: int) -> list[tuple[int, str]]:
    """扫 ROM 找 bl 到 target 的调用点（THUMB bl 编码）。"""
    hits: list[tuple[int, str]] = []
    t = target & ~1
    data = rom.data
    for o in range(0, len(data) - 4, 2):
        h1 = data[o] | (data[o + 1] << 8)
        if (h1 & 0xF800) != 0xF000:
            continue
        h2 = data[o + 2] | (data[o + 3] << 8)
        if (h2 & 0xD000) != 0xD000:
            continue
        s = (h1 >> 10) & 1
        imm10 = h1 & 0x3FF
        j1 = (h2 >> 13) & 1
        j2 = (h2 >> 11) & 1
        imm11 = h2 & 0x7FF
        i1 = 1 - (j1 ^ s)
        i2 = 1 - (j2 ^ s)
        off = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
        if off & 0x01000000:
            off -= 0x02000000
        src = (o + ROM_BASE) & ~1
        dst = (src + 4 + off) & ~1
        if dst == t:
            hits.append((src, syms.name_of(src)))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("addr", nargs="?", help="起始地址 0x08xxxxxx")
    ap.add_argument("--sym", help="按符号名找地址")
    ap.add_argument("--count", type=int, default=80)
    ap.add_argument("--no-bytes", action="store_true")
    ap.add_argument("--find-callers", action="store_true")
    a = ap.parse_args()

    rom = Rom()
    syms = SymTab()
    if a.sym:
        s = syms.by_name.get(a.sym)
        if not s:
            print(f"符号未找到: {a.sym}")
            return 1
        target = s.addr
        print(f"{s.name} @ 0x{target:08X}  size=0x{s.size:X}  {s.note}")
    elif a.addr:
        target = int(a.addr, 0)
    else:
        ap.error("需要 addr 或 --sym")

    if a.find_callers:
        hits = find_callers(rom, syms, target)
        print(f"调用 0x{target:08X} 的位置: {len(hits)}")
        for src, name in hits:
            print(f"  0x{src:08X}  {name}")
        return 0

    rows = disasm_func(rom, syms, target, a.count)
    print(fmt(rows, syms, show_bytes=not a.no_bytes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
