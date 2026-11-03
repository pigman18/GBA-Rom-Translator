#!/usr/bin/env python3
"""用「合理坐标 + ROM 指针」在 SaveBlock1 里定位 ObjectEventTemplate 数组。

── 前一版为什么失败 ────────────────────────────────────────────────────
我假设 template 里存当前地图的 (10,7)，但实测 SaveBlock1 里
**一次都没出现 (10,7)**。可能原因：
  · 字段顺序是 (mapNum, mapGroup) 而不是 (mapGroup, mapNum)
  · template 里根本不存地图 ID（只存 localId/坐标/script）

所以这一版**不用地图 ID**，改用两个更本质的特征：
  ① 合理的格子坐标 s16 对（0..60）
  ② 附近有 u32 落在 0x08xxxxxx（script 指针）

扫描 SaveBlock1 全域，找出「同一偏移上连续多项都满足」的 (base, step)。

用法：python scripts/find_template_scan.py [sav路径]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))
from savedit import rebuild, SB1_OFF  # noqa: E402

SB1_SIZE = 0x3AC0


def s16(b, o): return int.from_bytes(b[o:o + 2], "little", signed=True)
def u32(b, o): return int.from_bytes(b[o:o + 4], "little")


def is_rom_ptr(v: int) -> bool:
    return 0x08000000 <= v < 0x0A000000


def main() -> int:
    sav = (Path(sys.argv[1]) if len(sys.argv) > 1
           else ROOT / "work" / "_probe" / "teleport.sav")
    logical, _ = rebuild(sav.read_bytes())
    sb1 = logical[SB1_OFF:SB1_OFF + SB1_SIZE]
    print(f"{sav.name}  map={sb1[4]}:{sb1[5]}  pos=({s16(sb1,0)},{s16(sb1,2)})")

    # 1) 统计「哪 4 字节偏移上是 ROM 指针」的分布，找指针最密的区段
    ptr_offs = [o for o in range(0, SB1_SIZE - 4, 2) if is_rom_ptr(u32(sb1, o))]
    print(f"\nSaveBlock1 里 ROM 指针共 {len(ptr_offs)} 个")
    # 按 0x100 窗口统计
    from collections import Counter
    win = Counter(o // 0x100 for o in ptr_offs)
    print("指针最密的 0x100 窗口：")
    for w, n in win.most_common(8):
        print(f"  0x{w*0x100:04X}..0x{w*0x100+0xFF:04X}  {n} 个")

    # 2) 在最密的窗口里，试 (base, step, coord_off, script_off) 组合
    print("\n在这些窗口里搜「坐标合理 + 有 script 指针」的数组：")
    best = None
    for w, _ in win.most_common(4):
        wbase = w * 0x100
        for step in range(0x10, 0x30, 2):
            for coord_off in (0, 2, 4, 6, 8):
                for script_off in (0x08, 0x0C, 0x10, 0x14):
                    for start in range(wbase, wbase + 0x100, 2):
                        n_ok = 0
                        n_ptr = 0
                        for i in range(6):
                            o = start + i * step
                            if o + script_off + 4 > SB1_SIZE:
                                break
                            x = s16(sb1, o + coord_off)
                            y = s16(sb1, o + coord_off + 2)
                            ok_coord = 0 <= x <= 60 and 0 <= y <= 60
                            sp = u32(sb1, o + script_off)
                            ok_ptr = is_rom_ptr(sp)
                            if ok_coord:
                                n_ok += 1
                            if ok_ptr:
                                n_ptr += 1
                        if n_ok >= 4 and n_ptr >= 2:
                            score = (n_ptr, n_ok)
                            if best is None or score > best[0]:
                                best = (score, start, step, coord_off, script_off,
                                        n_ok, n_ptr)
    if best:
        score, start, step, co, so, n_ok, n_ptr = best
        print(f"\n★ 候选布局：base=0x{start:04X} step=0x{step:02X} "
              f"coord@+0x{co:02X} script@+0x{so:02X}")
        print(f"  合理坐标 {n_ok}/6，script 指针 {n_ptr}/6")
        print("\n  前 6 项明细：")
        for i in range(6):
            o = start + i * step
            if o + 0x18 > SB1_SIZE:
                break
            x, y = s16(sb1, o + co), s16(sb1, o + co + 2)
            sp = u32(sb1, o + so)
            print(f"    [{i}] 0x{o:04X} coord=({x},{y}) script=0x{sp:08X}")
    else:
        print("  没找到满足条件的布局")

    # 3) 兜底：把 0x9E0 与 0xC20 前后打出来人工看
    print("\n参考：0x9E0 前后 48 字节")
    print(f"  {sb1[0x9C0:0x9F0].hex(' ')}")
    print("参考：0xC20 前后 48 字节")
    print(f"  {sb1[0xC00:0xC30].hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
