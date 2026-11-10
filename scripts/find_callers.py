"""精确找 Thumb BL/BLX 调用点。

为什么不用 capstone 线性扫描：GBA 代码段里到处是**内联数据**（跳转表、
literal pool、脚本字节流），线性扫描一旦落到数据上就会错位，之后整段
解错，甚至 `push` 反解。实测找 `0x4F7AC` 的调用者时，capstone 从 0 线性
扫 0x200000 字节返回 0 命中，而按半字解码 BL 编码能准确找到 `0x4FD24`。

做法是反过来：**每个 2 字节位置**都当 BL 解码，算出目标地址后比对。
BL 编码本身有 11 位立即数 + S/J1/J2，误命中率极低（数据段要恰好拼出
合法 BL 且目标正好等于要找的地址）。

用法::

    PYTHONPATH=src python scripts/find_callers.py 0x4F7AC
    PYTHONPATH=src python scripts/find_callers.py 0x4F7AC --ctx 12
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

GBA_BASE = 0x08000000
CODE_END = 0x200000  # 前 2MB 为代码段（AXVJ）


def _decode_bl(rom: bytes, q: int) -> tuple[int, int] | None:
    """返回 (目标地址, 指令长度)；不是 BL/BLX 则 None。"""
    h1, h2 = struct.unpack_from("<HH", rom, q)
    # BL:  11110 S imm10 | 11 J1 1 J2 imm11
    # BLX: 11110 S imm10 | 11 J1 0 J2 imm10H 0
    if (h1 & 0xF800) != 0xF000:
        return None
    is_bl = (h2 & 0xD000) == 0xD000
    is_blx = (h2 & 0xE800) == 0xE800 and (h2 & 1) == 0
    if not (is_bl or is_blx):
        return None
    s = (h1 >> 10) & 1
    j1 = (h2 >> 13) & 1
    j2 = (h2 >> 11) & 1
    i1 = 0 if (j1 ^ j2) else 1
    i2 = i1
    imm10 = h1 & 0x3FF
    imm11 = (h2 & 0x7FF) if is_bl else (h2 & 0x7FE)
    imm = (
        (s << 24) | (i1 << 23) | (i2 << 22) | (j1 << 21) | (j2 << 20)
        | (imm10 << 12) | (imm11 << 1)
    )
    if s:
        imm -= 1 << 25
    return (GBA_BASE + q + 4 + imm) & 0xFFFFFFFF, 4


def find_callers(rom: bytes, target: int) -> list[int]:
    out: list[int] = []
    for q in range(0, min(CODE_END, len(rom) - 4), 2):
        r = _decode_bl(rom, q)
        if r and r[0] == target:
            out.append(q)
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    target = int(sys.argv[1], 16)
    if target < GBA_BASE:
        target += GBA_BASE
    ctx = 8
    if "--ctx" in sys.argv:
        ctx = int(sys.argv[sys.argv.index("--ctx") + 1])
    rom = Path("roms/origin/POKEMON_RUBY_AXVJ00.gba").read_bytes()
    hits = find_callers(rom, target)
    print(f"{target:#010x} 的 BL/BLX 调用点：{len(hits)}")
    try:
        from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

        md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        for h in hits:
            print(f"\n=== 调用点 {h:#08x}（上下文 {ctx} 条）")
            start = max(0, h - ctx * 2)
            for i in md.disasm(rom[start:h + 16], GBA_BASE + start):
                mark = "  <<< call" if i.address == GBA_BASE + h else ""
                print(f"  {i.address:#010x}  {i.mnemonic:8s} {i.op_str}{mark}")
    except ImportError:
        for h in hits:
            print(f"  {h:#08x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
