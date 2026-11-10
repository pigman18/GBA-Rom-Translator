#!/usr/bin/env python3
"""对比两份 .sav 的 SaveBlock1 头部，找出「换地图到底靠哪些字段」。

背景：把 Route118_68-7.sav 的 location 改成 10:7（MauvilleCity_Mart）后，
      prove 读到 loc=(10,7) pos=(3,3) 都对了，但画面仍是 Route118 地形，
      而且主角不见了 —— 说明光改 location 不够，还有别的字段参与。

现成的 MauvilleCity_Mart_3-3.sav 是**真的**在商店里的存档，
把它和改过的存档在 SaveBlock1 前 0x100 字节逐字节对比，
就能直接看出哪些字节不同，而不是靠猜结构体。

用法：python scripts/diff_sav_heads.py <a.sav> <b.sav>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bot" / "tools"))
from savedit import rebuild, SB1_OFF  # noqa: E402

# pokeruby struct WarpData 是 8 字节：mapGroup, mapNum, warpId, pad, x(s16), y(s16)
# SaveBlock1 开头这一串 WarpData 字段（候选偏移，靠下面的对比验证）
FIELDS = [
    (0x00, "pos / Coords16"),
    (0x04, "location / WarpData"),
    (0x0C, "continueGameWarp"),
    (0x14, "dynamicWarp"),
    (0x1C, "lastHealLocation"),
    (0x24, "escapeWarp"),
]


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    a_path, b_path = Path(sys.argv[1]), Path(sys.argv[2])
    la, _ = rebuild(a_path.read_bytes())
    lb, _ = rebuild(b_path.read_bytes())

    a = la[SB1_OFF:SB1_OFF + 0x100]
    b = lb[SB1_OFF:SB1_OFF + 0x100]

    print(f"A = {a_path.name}")
    print(f"B = {b_path.name}")
    print("\n逐字节差异（SaveBlock1 +0x000..0x0FF）：")
    diffs = [i for i in range(0x100) if a[i] != b[i]]
    if not diffs:
        print("  无差异")
    else:
        for i in diffs:
            print(f"  +0x{i:03X}  A={a[i]:02X}  B={b[i]:02X}")

    print("\n按 WarpData 字段解读（每段 8 字节：g,n,warp,pad,x,y）：")
    for off, name in FIELDS:
        sa = a[off:off + 8]
        sb = b[off:off + 8]
        same = "" if sa == sb else "   <<< 不同"
        print(f"  +0x{off:03X} {name:<22} A={sa.hex(' ')}  B={sb.hex(' ')}{same}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
