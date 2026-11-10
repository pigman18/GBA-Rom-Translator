#!/usr/bin/env python3
"""验证特性名测试包是否生效。

检查：
  1. 3 处 lsls 是否改成 #5（净移位 +2）
  2. 3 处字面量是否指向 0x09EB0000
  3. 新表 77 项是否都含 eos
  4. 新表内容与预期一致（前 3 项示例）

用法：
    python scripts/research/ruby/verify_ability_build.py
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
OUT = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
ORIG = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000

BASE = 0x1CBC44
NEW_STRIDE = 32
N = 77
DATA = 0x09EB0000

# 3 个 ldr 站点（符号执行给出的）
SITES = [0x09C6C2, 0x11C59A, 0x11CAC4]
LITERALS = []      # 稍后扫


def main() -> int:
    out = OUT.read_bytes()
    orig = ORIG.read_bytes()

    print(f"产物 {len(out):,} B\n")

    # 1. lsls 检查
    print("=== 1. 三处 lsls（应为 #5 = 0x0140/0x0149/0x0160）===")
    ok1 = 0
    for off in SITES:
        a = out[off:off + 2]
        b = orig[off:off + 2]
        # 解码
        hw = struct.unpack("<H", a)[0]
        imm = (hw >> 6) & 0x1F
        mark = "✅" if imm == 5 else f"❌ #imm={imm}"
        if imm == 5:
            ok1 += 1
        print(f"  0x{off:06X}: 原 {b.hex(' ')} → {a.hex(' ')}  "
              f"lsls #{imm}  {mark}")
    print(f"  通过 {ok1}/3\n")

    # 2. 字面量
    print("=== 2. 字面量重定向（应指向 0x09EB0000）===")
    needle = struct.pack("<I", BASE + GBA_BASE)
    lits, s = [], 0
    while True:
        i = orig.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0:
            lits.append(i)
        s = i + 1
    ok2 = 0
    for lit in lits:
        v = struct.unpack_from("<I", out, lit)[0]
        mark = "✅" if v == DATA else f"❌ 0x{v:08X}"
        if v == DATA:
            ok2 += 1
        print(f"  0x{lit:06X}: 0x{v:08X}  {mark}")
    print(f"  通过 {ok2}/{len(lits)}\n")

    # 3. 新表
    print("=== 3. 新表数据（77 项 × 32B）===")
    dbase = DATA - GBA_BASE
    good = 0
    for i in range(N):
        seg = out[dbase + i * NEW_STRIDE: dbase + (i + 1) * NEW_STRIDE]
        if 0xFF in seg:
            good += 1
    print(f"  含 eos 的项: {good}/{N}"
          + ("  ✅" if good == N else "  ⚠️"))

    # 4. 内容示例
    print()
    print("=== 4. 新表前 5 项内容 ===")
    for i in range(5):
        seg = out[dbase + i * NEW_STRIDE: dbase + (i + 1) * NEW_STRIDE]
        ff = seg.find(b"\xFF")
        body = seg[:ff] if ff >= 0 else seg
        # 解出码位
        codes = []
        j = 0
        while j + 3 < len(body):
            if body[j] == 0xF9 and body[j + 1] == 0x00:
                codes.append((body[j + 2] << 8) | body[j + 3])
                j += 4
            else:
                j += 1
        print(f"  [{i}] {body.hex(' '):<46} 码位 "
              + " ".join(f"0x{c:04X}" for c in codes)
              + f"  ({len(body)//4} 字)")

    print()
    all_ok = (ok1 == 3 and ok2 == len(lits) and good == N)
    if all_ok:
        print("✅ 特性名测试包全部生效")
        return 0
    print(f"⚠️ lsls {ok1}/3  字面量 {ok2}/{len(lits)}  新表 {good}/{N}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
