#!/usr/bin/env python3
"""方案对比：招式名/特性名/属性名 塞不下，怎么办？

三个候选：
  A. VARLEN（变长 + 指针数组）—— 必须把 index×stride 改成 index×4，改机器码
  B. SWAP_STRIDE（放大 stride 到 8×2=16）—— 只需把 `lsls #3` 改成 `lsls #4`
  C. 缩句 —— 用户明确只在没办法时才用

方案 B 为什么更优：
  招式名 sum 的乘法展开是 `lsls r0, r6, #0x14` 之类，
  若 stride 从 8 → 16，只需把移位量 +1。
  但要注意 stride 放大后表体积翻倍、且元素间隔变化，
  必须确认代码里所有 index 计算点都改到。

本脚本：
  1. 确认每个表的乘法指令位置
  2. 评估 SWAP_STRIDE 可行性（倍数是否是 2 的幂）
  3. 对比三种方案的成本

用法：
    python scripts/research/ruby/a2_stride_swap.py
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import capstone

for _s in (Path(__file__).name, sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

# (表名, 基址, 旧stride, name_offset, n, 已知遍历指令)
TABLES = [
    ("招式名",         0x1CACFC, 8,  0, 354, 0x02B53A),
    ("特性名",         0x1CBC44, 8,  0, 77,  0x09C6C2),
    ("属性名",         0x1CBB0C, 5,  0, 18,  0x02B6B0),
    ("秘密基地装饰名", 0x3C2A44, 28, 13, 120, 0x0AF2D2),
]


def find_ldr(rom: bytes, lit: int, back: int = 4096) -> list[int]:
    out = []
    for off in range(max(0, lit - back), lit, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit:
            out.append(off)
    return out


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import encode_body

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    for name, base, stride, noff, n, insn_hint in TABLES:
        cap = stride - noff
        # 统计最长译文
        longest = 0
        cnt = 0
        for e in d.get("entries") or []:
            if e.get("module") != name:
                continue
            if e.get("type") != "replace" or e.get("phrase_code") is None:
                continue
            t = e.get("translated") or ""
            if not t:
                continue
            cnt += 1
            longest = max(longest, len(encode_body(cm, t)))

        print(f"=== {name} @0x{base:06X} stride={stride} cap={cap} "
              f"条数={cnt} 最长={longest}B ===")

        if longest <= cap:
            print(f"  ✅ 塞得下 → FIXED（只改字面量）")
            print()
            continue

        # 评估 swap stride（只考虑 2 的幂倍数，因为 Thumb 乘法展开靠移位）
        new_stride = None
        mult = None
        for k in (2, 4, 8):
            if longest <= stride * k:
                new_stride = stride * k
                mult = k
                break
        if new_stride:
            is_pow2 = (new_stride & (new_stride - 1)) == 0
            print(f"  方案 B: stride {stride} → {new_stride}（×{mult}），"
                  f"{'2的幂 ✅ 只改移位量' if is_pow2 else '非2幂 ⚠️ 需多条指令'}")
            print(f"    表体积 {n*stride:,}B → {n*new_stride:,}B")
        else:
            print(f"  方案 B: 即使 ×8 也塞不下，只能 VARLEN 或缩句")

        # 看遍历指令（find_ldr 要文件偏移，不能传 GBA 地址）
        lits = find_ldr(rom, base)
        print(f"  方案 A: VARLEN（改 index×stride → index×4）")
        print(f"    指向文件偏移 0x{base:06X} 的字面量: {len(lits)} 处")
        if lits:
            ldr = lits[0]
            print(f"    首个 ldr @0x{ldr:X}，后续 32 字节:")
            for ins in md.disasm(rom[ldr:ldr + 32], ldr):
                mark = ""
                if ins.mnemonic in ("lsls", "lsl", "muls"):
                    mark = "   ← 乘法，需改"
                print(f"      0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}{mark}")
                if ins.address - ldr > 24:
                    break
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
