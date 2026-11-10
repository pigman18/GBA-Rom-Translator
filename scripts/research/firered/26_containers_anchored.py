#!/usr/bin/env python3
"""调研㉖ 用锚点区直接观察火红的实际文本容器（等长 / 等距 / 超短）。

═══════════════════════════════════════════════════════════════════════════
【为什么这次能成】
═══════════════════════════════════════════════════════════════════════════
㉕ 从「汉化改过的指针」反推出 **3,613 个真实的原版日文文本地址**，
集中在这几片：

    0x083DD000..0x083E2000   1,163 个   ← 主文本区
    0x083C2000..0x083C4000    426 个
    0x0819B000..0x081AA000   ~600 个
    0x08409000..0x0840E000    337 个
    0x08175000..0x08193000   ~350 个

这些地址 100% 是文本，用它当锚点看物理布局，不需要猜字符集。

═══════════════════════════════════════════════════════════════════════════
【看什么】
═══════════════════════════════════════════════════════════════════════════
  ① 对齐：这些文本起点 mod 4 / mod 8 / mod 16 的分布
     → 若都 ≡0 mod 4，说明是 u32 数组；全随机说明是连续串流
  ② 间隔：相邻两个文本起点之间的距离
     → 恒定间隔 = 等长块；间隔 = 上串长+1 = 等距块；无规律 = 串流
  ③ 每条串的实际长度分布（用 FF 结尾实测）
  ④ 超短串（≤6 字节）在这几片里长什么样、占多少
  ⑤ 同一片区的原始 hex dump（人眼看真实结构）

用法：python scripts/research/firered/26_containers_anchored.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

BASE = 0x08000000
NEW_TEXT = [(0x6D0000, 0x722000), (0xAF5000, 0xAFB000)]


def in_new_text(off: int) -> bool:
    return any(lo <= off < hi for lo, hi in NEW_TEXT)


def main() -> int:
    zh_b = FR_ZH.read_bytes()
    ja_b = FR_JA.read_bytes()
    n = min(len(zh_b), len(ja_b))
    m = n // 4 * 4

    pa = np.frombuffer(ja_b[:m], dtype=np.uint32).astype(np.uint64)
    pz = np.frombuffer(zh_b[:m], dtype=np.uint32).astype(np.uint64)
    is_rom = (pa >= BASE) & (pa < BASE + n) & (pz >= BASE) & (pz < BASE + n)
    old_off = (pa - BASE).astype(np.int64)
    new_off = (pz - BASE).astype(np.int64)
    new_in_cn = np.array([in_new_text(int(x)) for x in new_off])
    old_in_cn = np.array([in_new_text(int(x)) for x in old_off])
    sel = np.flatnonzero((pa != pz) & is_rom & new_in_cn & ~old_in_cn)
    olds = np.sort(old_off[sel])

    print("=" * 78)
    print(f"锚点：{len(olds):,} 个真实原版日文文本地址")
    print("=" * 78)

    # ── ① 对齐 ────────────────────────────────────────────────────
    print("\n① 文本起点的对齐分布（mod 4 / mod 8 / mod 16）")
    for mod in (4, 8, 16):
        c = Counter((olds % mod).tolist())
        tot = len(olds)
        top = ", ".join(f"{k}:{v/tot*100:.1f}%" for k, v in c.most_common(5))
        print(f"  mod {mod:>2}: {top}")

    # ── ② 间隔 ────────────────────────────────────────────────────
    print("\n② 相邻文本起点的间隔")
    gaps = np.diff(olds)
    c = Counter(gaps.tolist())
    print(f"  间隔种类 {len(c):,} 种，前 15 个：")
    for g, cnt in c.most_common(15):
        print(f"    间隔 {g:>4} 字节 × {cnt:>4}"
              f"（{cnt/len(gaps)*100:>5.1f}%）")
    print(f"  间隔中位 {np.median(gaps):.0f}  均值 {gaps.mean():.1f}")

    # 间隔 == 上一层串长+1 的比例（等距特征）
    eq_gap = 0
    tot_gap = 0
    for i in range(len(olds) - 1):
        o = int(olds[i])
        L = ja_b.find(b"\xff", o, o + 300)
        if L < 0:
            continue
        tot_gap += 1
        if int(olds[i + 1]) == L + 1:
            eq_gap += 1
    print(f"  间隔正好等于「本串长+1」的比例：{eq_gap/max(1,tot_gap)*100:.1f}%"
          f"（{eq_gap}/{tot_gap}）")
    print(f"   ⇒ 高比例 = 等距块（串后紧接下一串）；低 = 混有其他数据")

    # ── ③ 串长分布 ────────────────────────────────────────────────
    print("\n③ 锚点串的实测长度分布")
    lens = []
    for o in olds.tolist():
        e = ja_b.find(b"\xff", o, o + 400)
        if e > 0:
            lens.append(e - o)
    la = np.array(lens)
    print(f"  有效 {len(la):,} 条")
    print(f"  均值 {la.mean():.1f} 中位 {np.median(la):.0f} "
          f"最小 {la.min()} 最大 {la.max()}")
    c = Counter(la.tolist())
    print(f"  最常见长度 top 10：")
    for L, cnt in c.most_common(10):
        print(f"    长度 {L:>3}: {cnt:>4} 条（{cnt/len(la)*100:>5.1f}%）")
    print(f"  ≤6 字节：{int((la<=6).sum()):,} 条（{(la<=6).mean()*100:.1f}%）")

    # ── ④ 超短串实例 ──────────────────────────────────────────────
    print("\n④ 超短串（≤6 字节）在锚点里的样子")
    short = [(o, int(e - o)) for o, e in
             ((o, ja_b.find(b"\xff", o, o + 400)) for o in olds.tolist()[:4000])
             if e > 0 and e - o <= 6]
    print(f"  前 4000 个锚点里，超短串 {len(short)} 条")
    for o, L in short[:14]:
        nxt = ja_b.find(b"\xff", o + L + 1, o + L + 80)
        nxts = ja_b[o + L + 1:nxt].hex(' ') if nxt > 0 else '?'
        print(f"    0x{BASE+o:08X} L={L}  {ja_b[o:o+L].hex(' ')}"
              f"   |下一串| {nxts[:32]}")

    # ── ⑤ 主文本区原始 dump ───────────────────────────────────────
    print("\n⑤ 主文本区 0x083DD000 附近的原始布局（前 320 字节）")
    off = 0x3DD000
    blob = ja_b[off:off + 320]
    for i in range(0, len(blob), 32):
        chunk = blob[i:i + 32]
        printable = "".join(
            "." if b < 0x20 or b > 0xF5 else chr(ord('A') + (b % 26))
            for b in chunk)
        print(f"    0x{BASE+off+i:08X}  {chunk.hex(' '):<96} |{printable}|")

    # 标注锚点位置
    print("\n  同一区域里锚点（被改指针指向）的位置：")
    in_region = olds[(olds >= off) & (olds < off + 320)]
    for o in in_region.tolist()[:20]:
        print(f"    ★ 0x{BASE+o:08X} (区域+0x{o-off:X})")

    # ── ⑥ 判定这块到底是「指针数组」还是「串流」──────────────────
    print("\n" + "=" * 78)
    print("⑥ 关键判定：0x083DD000 区是「u32 指针数组」还是「连续文本串流」")
    print("=" * 78)
    off = 0x3DD000
    seg = ja_b[off:off + 256]
    print(f"  原始 hex（前 128 B）：{seg[:128].hex(' ')}")
    # 把每 4 字节当 u32 看，是否像 ROM 指针
    struct_like = 0
    for i in range(0, len(seg) - 4, 4):
        v = int.from_bytes(seg[i:i + 4], "little")
        if 0x08000000 <= v < 0x0A000000:
            struct_like += 1
    print(f"  按 u32 读，{struct_like}/{len(seg)//4} 个落在 ROM 地址范围")
    if struct_like > len(seg) // 4 * 0.5:
        print("  ⇒ 这里是**指针/结构数组**，文本在别处")
    else:
        print("  ⇒ 这里就是**文本本体**（不是指针数组）")

    # 锚点是文本起点还是指针槽位
    print(f"\n  0x083DD000 区里，锚点是「文本起点」还是「u32 槽位」？")
    # 检查锚点前后的字节
    for o in in_region.tolist()[:10]:
        lo = max(0, o - 8)
        print(f"    0x{BASE+o:08X}  前后: {ja_b[lo:o+16].hex(' ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
