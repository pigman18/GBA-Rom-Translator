#!/usr/bin/env python3
"""A 方案的巧解：不改指令，改「adds 用的是哪个寄存器」。

招式名现状：
  0x02B536: ldrh r1, [r4]        r1 = index
  0x02B538: lsls r1, r1, #3      r1 = idx*8
  0x02B53A: ldr  r0, [pc, #0x44] r0 = base
  0x02B53C: adds r1, r1, r0      r1 = base + idx*8
  0x02B53E: adds r0, r7, #0      r0 = r7（覆盖 r0，不影响 r1）
  0x02B540: bl   #0x4308         调用，r1 = 文本地址

关键观察：**r0 在 0x02B53E 被覆盖了**，说明 r0 用完即弃。

巧解：把 0x02B53C 的 `adds r1,r1,r0` 改成 `ldr r1,[r1,r0]`？
  Thumb 没有「基址+索引」的 ldr（只有 ldr rX,[rY,#imm]）。

另一种巧解：把 0x02B53A 的 ldr 目标从 r0 改成 r1！
  0x02B53A: ldr  r1, [pc, #0x44]  ← r1 被基址覆盖，index 丢了
  ✗ 不行，index 在 r1 里

再想：能否让「指针数组的地址」被当成「文本地址」直接用？
  → 只有当指针数组每项 4 字节且解引用后才对，不能省 ldr

真正可行的巧解：**利用 ldr 的偏移形式**
  0x02B53A: ldr r1, [pc, #0x44]  → 改成 ldr r1,[rX,rY]？Thumb 不支持。

结论：Thumb 指令集限制，无法在不插指令的前提下做「基址+索引 后解引用」。

但还有一条路：**改「调用前的最后一步」**
  若 0x02B540 的 bl 目标是我们的函数，可以在函数入口做解引用！
  这样 6 个调用点都不用改，只需在共同的被调函数里加一次 ldr。

验证：0x4308 / 0x42e8 / 0x6f16c 等是否为「取文本并打印」的共同函数？

用法：
    python scripts/research/ruby/a_plan_common_func.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import capstone

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

# 各站点 ldr/adds 之后调用的函数
CALLS = [
    ("招式名",         0x02B540, 0x00004308),
    ("特性名",         0x09C6CE, 0x000F40E0),
    ("属性名",         0x02B6B6, 0x00004308),
    ("道具名",         0x0A5392, None),
    ("图鉴分类名",     0x08C1DE, 0x0008DD60),
    ("秘密基地装饰名", 0x0AF2E2, 0x0006F16C),
]


def main() -> int:
    rom = ROM.read_bytes()

    print("=" * 76)
    print("=== 解法探索：能否在「共同被调函数」里做解引用 ===")
    print("=" * 76)
    print()

    from collections import Counter
    cnt = Counter(c[2] for c in CALLS if c[2] is not None)
    print("被调函数分布:")
    for fn, n in cnt.most_common():
        print(f"  bl 0x{fn:06X}  被 {n} 个站点调用")

    print()
    print("=== 各被调函数的头部 ===")
    for fn, _n in cnt.most_common():
        print(f"\n--- 0x{fn:06X} ---")
        insns = list(md.disasm(rom[fn:fn + 24], fn))
        for ins in insns[:6]:
            print(f"  0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}")

    print()
    print("=" * 76)
    print("=== 关键判断 ===")
    print("=" * 76)
    print()
    print("若多个站点调用**同一个**函数，且该函数接收「文本地址」参数，")
    print("则可以在函数入口统一做「解引用」，站点无需逐个改！")
    print()
    print("但这要求：")
    print("  1. 该函数的参数确实是「文本地址」")
    print("  2. 该函数只被这些表访问调用（不含其它用途）")
    print("  3. 函数入口有空间插入 ldr")
    print()
    print("⚠️ 风险：若函数被多处复用（正常文本也传地址给它），")
    print("   就不能统一解引用，会误伤正常文本。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
