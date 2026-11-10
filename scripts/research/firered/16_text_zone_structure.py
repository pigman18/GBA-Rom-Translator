#!/usr/bin/env python3
"""调研⑯ 解剖火红新增文本区的内部结构：等长块 / 等距块 / 超短文本。

═══════════════════════════════════════��═══════════════════════════════════
【上一轮的缺口】
═══════════════════════════════════════════════════════════════════════════
`10_text_pointers.py` 只做到「段长大量重复（9/6/12/15）」，
但**块边界在哪、是不是整块一个指针、等长块里怎么补位**都没查。

本脚本逐个坐实：
  A) 等长块：连续 N 段长度完全相同（说明是固定宽度数组）
  B) 等距块：段与段之间只隔 1 个 0x00（说明是 00 分隔的数组）
  C) 超短文本：≤6 字节的段，看看有没有独立指针
  D) 这些块是否「整块一个指针」（块内地址不被任何指针引用）

用法：python scripts/research/firered/16_text_zone_structure.py
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

BASE = 0x08000000
# 三个已确认纯文本区（ROM 偏移）
ZONES = [
    (0x6D0000, 0x4C000, "主文本区"),
    (0x71D000, 0xA000, "文本区2"),
    (0xAF5000, 0x6000, "文本区3"),
]

# 文本控制符（Gen3）：FF=结束/换行, FB/F9=控制, 00=补位
TERMINATOR = 0xFF


def u32(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "little")


def collect_pointers(zh: bytes) -> dict[int, int]:
    """返回 {目标ROM偏移: 槽位个数}，只收指向三个文本区的。"""
    lo = min(z[0] for z in ZONES)
    hi = max(z[0] + z[1] for z in ZONES)
    refs: Counter = Counter()
    for o in range(0, len(zh) - 4, 4):
        v = u32(zh, o)
        if not (BASE <= v < 0x0A000000):
            continue
        off = v - BASE
        if lo <= off < hi:
            refs[off] += 1
    return refs


def decode_segment(seg: bytes) -> str:
    """把 F7 hi lo 解成 ⟨codepoint⟩，其他字节原样。"""
    out = []
    i = 0
    while i < len(seg):
        if seg[i] == 0xF7 and i + 2 < len(seg) + 1 and i + 2 <= len(seg) - 1:
            out.append(f"⟨{seg[i+1]:02X}{seg[i+2]:02X}⟩")
            i += 3
        else:
            out.append(f"{seg[i]:02X}")
            i += 1
    return "".join(out)


def split_segments(seg: bytes) -> list[tuple[int, int]]:
    """按 0xFF 切，返回 [(相对起点, 长度)]，跳过空段。"""
    out = []
    start = 0
    for i, b in enumerate(seg):
        if b == TERMINATOR:
            if i > start:
                out.append((start, i - start))
            start = i + 1
    if len(seg) > start:
        out.append((start, len(seg) - start))
    return out


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    print("=" * 74)
    print("火红新增文本区结构解剖")
    print("=" * 74)

    refs = collect_pointers(zh)
    print(f"\n指向文本区的指针：{sum(refs.values()):,} 个槽位，"
          f"{len(refs):,} 个不同目标")

    all_segs: list[tuple[int, int, int]] = []   # (绝对偏移, 长度, 来源区)
    for base, size, label in ZONES:
        seg = zh[base:base + size]
        for rel, ln in split_segments(seg):
            all_segs.append((base + rel, ln, ZONES.index((base, size, label))))
    print(f"按 0xFF 切出非空段：{len(all_segs):,}")

    # ── A) 等长块 ────────────────────────────────────────────────────
    print("\n" + "-" * 74)
    print("A) 等长块检测：连续段长度完全相同（≥4 段视为固定宽度数组）")
    print("-" * 74)
    segs_sorted = sorted(all_segs)
    runs = []
    i = 0
    while i < len(segs_sorted):
        j = i
        L = segs_sorted[i][1]
        # 连续且长度相同、地址紧邻（间隔 = L + 1，即中间一个 FF）
        while (j + 1 < len(segs_sorted)
               and segs_sorted[j + 1][1] == L
               and segs_sorted[j + 1][0] == segs_sorted[j][0] + L + 1):
            j += 1
        if j - i + 1 >= 4:
            runs.append((j - i + 1, L, segs_sorted[i][0], segs_sorted[j][0]))
        i = j + 1

    runs.sort(reverse=True)
    print(f"  找到 {len(runs)} 个等长连续块（≥4 段）")
    if runs:
        print(f"  {'段数':>5} {'每段长':>7} {'起始 ROM':>12} {'字节数':>9} {'块首有指针?':>12}")
        for n, L, s, e in runs[:12]:
            span = e + L - s
            has = "是" if s in refs else "**否**"
            print(f"  {n:>5} {L:>7} 0x{BASE+s:08X} {span:>9} {has:>12}")
        print(f"\n  等长块总段数：{sum(r[0] for r in runs):,}"
              f"（占全部段 {sum(r[0] for r in runs)/len(all_segs)*100:.1f}%）")

    # ── B) 等距块 ────────────────────────────────────────────────────
    print("\n" + "-" * 74)
    print("B) 等距块检测：段之间只隔 1 个 0x00（00 分隔数组）")
    print("-" * 74)
    # 等距 = 段本身以 00 结尾再跟 FF？不，等距是 段 + 00 + 段 + 00
    # 重新按 00 切：在文本区里找「连续多个 00 结尾的短块」
    gap_runs = []
    for base, size, label in ZONES:
        seg = zh[base:base + size]
        # 找 00 作为分隔符：块 = 可打印内容 + 00
        pos = 0
        cur = []
        while pos < len(seg):
            end = seg.find(b"\x00", pos)
            if end < 0:
                break
            ln = end - pos
            if 2 <= ln <= 16 and seg[pos:end].count(0xF7) * 3 == ln:
                cur.append((pos, ln))
            else:
                if len(cur) >= 4:
                    gap_runs.append((len(cur), base + cur[0][0], [c[1] for c in cur[:6]]))
                cur = []
            pos = end + 1
        if len(cur) >= 4:
            gap_runs.append((len(cur), base + cur[0][0], [c[1] for c in cur[:6]]))
    gap_runs.sort(reverse=True)
    print(f"  找到 {len(gap_runs)} 段「0x00 分隔的纯 F7 短块」（≥4 项）")
    if gap_runs:
        print(f"  {'项数':>5} {'起始 ROM':>12}  前 6 项长度")
        for n, s, lens in gap_runs[:12]:
            has = "块首有指针" if s in refs else "**块首无指针**"
            print(f"  {n:>5} 0x{BASE+s:08X}  {lens}  {has}")

    # ── C) 超短文本 ──────────────────────────────────────────────────
    print("\n" + "-" * 74)
    print("C) 超短文本：≤6 字节的段，是否有独立指针")
    print("-" * 74)
    short = [(o, L) for o, L, _ in all_segs if L <= 6]
    print(f"  ≤6 字节段：{len(short):,}")
    with_ptr = sum(1 for o, L in short if o in refs)
    print(f"  其中**段首有指针**：{with_ptr:,}"
          f"（{with_ptr/max(1,len(short))*100:.1f}%）")
    print(f"  无指针：{len(short)-with_ptr:,}"
          f"（{(len(short)-with_ptr)/max(1,len(short))*100:.1f}%）")
    print(f"\n  抽样 12 个超短段（段首指针 / 内容）：")
    shown = 0
    for o, L in short:
        if shown >= 12:
            break
        content = decode_segment(zh[o:o + L])
        ptr = f"×{refs[o]}" if o in refs else "无"
        print(f"    0x{BASE+o:08X} L={L:<2} ptr={ptr:>4}  {content}")
        shown += 1

    # ── D) 指针密度：块首 vs 块内 ────────────────────────────────────
    print("\n" + "-" * 74)
    print("D) 指针是打在「段首」还是「段内任意位置」？")
    print("-" * 74)
    seg_starts = {o for o, L, _ in all_segs}
    ptr_at_start = sum(1 for o in refs if o in seg_starts)
    ptr_elsewhere = len(refs) - ptr_at_start
    print(f"  指向段首：{ptr_at_start:,} 个不同目标")
    print(f"  指向段内其他位置：{ptr_elsewhere:,} 个不同目标")
    print(f"  ⇒ {'段首为主，符合「一段一指针」' if ptr_at_start > ptr_elsewhere else '存在大量段内指针，需细查'}")

    # ── E) 那些 64 字节块 ────────────────────────────────────────────
    print("\n" + "-" * 74)
    print("E) 两个「64 字节日文→F7」块的内容（疑似名字表）")
    print("-" * 74)
    for off in (0x126300, 0x138540):
        a = ja[off:off + 64]
        b = zh[off:off + 64]
        print(f"\n  ROM 0x{BASE+off:08X}")
        print(f"    原版: {a.hex(' ')}")
        print(f"    汉化: {b.hex(' ')}")
        print(f"    解码: {decode_segment(b)}")
        # 整块是否被指针引用
        print(f"    块首指针: {'×'+str(refs[off]) if off in refs else '无'}")
        u32hits = [o for o in range(max(0, off - 0x2000), min(len(zh) - 4, off + 0x2000), 4)
                   if u32(zh, o) == BASE + off]
        print(f"    附近指向块首的 u32：{len(u32hits)} 个")

    print("\n" + "=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
