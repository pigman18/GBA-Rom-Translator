#!/usr/bin/env python3
"""反推日版 SaveBlock1 里 ObjectEventTemplate 的真实偏移与步长。

── 为什么不能照抄美版 ──────────────────────────────────────────────────
按 pokeruby 的 `/*0xC20*/ objectEventTemplates[64]` + `sizeof=0x18` 读，
得到 map=0:83、pos=(1112,0) 这种荒谬值 ⇒ 日版结构不同（本项目已多次验证）。

── 反推方法：用「已知正确答案」当锚 ────────────────────────────────────
我们知道当前地图是 **10:7**（商店），且实机截图里能看到：
  · 店里有店员 NPC（可对话）
  · 玩家在 (3,7)

所以在 SaveBlock1 的 0x3AC0 字节里，一定存在一段数组：
  · 每项里有一对 s16 = 合理的格子坐标（0..60）
  · 有一对 u8 = (mapGroup, mapNum) = (10, 7)  ← 当前地图
  · 有一个 u32 落在 0x08xxxxxx（script 指针）或 0（无脚本）

本脚本在 SaveBlock1 全域滑动，用「(10,7) 相邻字节 + 附近有合理坐标 + 有 ROM 指针」
三重条件定位数组起点与步长。

用法：python scripts/derive_template_layout.py [sav路径]
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))
from savedit import rebuild, SB1_OFF  # noqa: E402

SB1_SIZE = 0x3AC0


def u16(b, o): return int.from_bytes(b[o:o + 2], "little")
def s16(b, o): return int.from_bytes(b[o:o + 2], "little", signed=True)
def u32(b, o): return int.from_bytes(b[o:o + 4], "little")


def main() -> int:
    sav = (Path(sys.argv[1]) if len(sys.argv) > 1
           else ROOT / "work" / "_probe" / "teleport.sav")
    logical, _ = rebuild(sav.read_bytes())
    sb1 = logical[SB1_OFF:SB1_OFF + SB1_SIZE]

    mg, mn = sb1[4], sb1[5]
    px, py = s16(sb1, 0), s16(sb1, 2)
    print(f"{sav.name}  当前 map={mg}:{mn}  pos=({px},{py})")

    # 1) 在 SaveBlock1 里找所有「(mg, mn) 相邻出现」的位置
    print(f"\n[1] 搜索字节对 ({mg}, {mn}) 的所有出现位置（前后 0x40 字节内的上下文）：")
    hits = []
    for o in range(0x100, SB1_SIZE - 2):
        if sb1[o] == mg and sb1[o + 1] == mn:
            hits.append(o)
    print(f"  共 {len(hits)} 处")
    # 只保留「附近有 ROM 指针」的
    good = []
    for o in hits:
        lo, hi = max(0, o - 0x40), min(SB1_SIZE - 4, o + 0x40)
        nptr = sum(1 for k in range(lo, hi)
                   if 0x08000000 <= u32(sb1, k) < 0x0A000000)
        if nptr:
            good.append((o, nptr))
    good.sort(key=lambda x: -x[1])
    print(f"  其中附近有 ROM 指针的 {len(good)} 处，按指针数排序：")
    for o, n in good[:12]:
        print(f"    0x{o:04X}  附近指针 {n} 个   前8字节={sb1[o:o+8].hex(' ')}")

    # 2) 取最热的那处当锚，试各种步长，看能不能凑出「多个合理项」
    if not good:
        print("\n[!] 没有候选，无法继续")
        return 1
    anchor = good[0][0]
    print(f"\n[2] 用 0x{anchor:04X} 当锚，试步长（找能连续凑出 4+ 个合理项的）：")
    best = None
    for step in range(0x10, 0x30, 2):
        for back in range(0, step * 4, 2):
            base = anchor - back
            if base < 0 or base + step * 4 > SB1_SIZE:
                continue
            n_ok = 0
            for i in range(4):
                o = base + i * step
                x, y = s16(sb1, o + 4), s16(sb1, o + 6)
                if 0 <= x <= 60 and 0 <= y <= 60:
                    n_ok += 1
            if n_ok >= 3:
                score = (n_ok, -step)
                if best is None or score > best[0]:
                    best = (score, base, step, n_ok)
    if best:
        _, base, step, n_ok = best
        print(f"  ★ 最佳：base=0x{base:04X} step=0x{step:02X} 合理项 {n_ok}/4")
        print(f"    该段 32 字节：{sb1[base:base+32].hex(' ')}")
    else:
        print("  没找到")

    # 3) 无论上面结果如何，把 0x9E0 / 0xC20 附近的字节打出来人工看
    for name, off in (("0x9E0 (objectEvents)", 0x9E0),
                      ("0xC20 (templates)", 0xC20)):
        print(f"\n[3] {name} 处前 48 字节：")
        print(f"    {sb1[off:off+48].hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
