#!/usr/bin/env python3
"""调研⑱ 定位火红在**代码区**改动的每一处 —— 这就是汉化 hook 的全部入口。

═══════════════════════════════════════════════════════════════════════════
【为什么这一步最关键】
═══════════════════════════════════════════════════════════════════════════
已知：低地址区（代码）与原版差异只有 **0.2%**。

⇒ 汉化**没重写引擎**，只打了少量补丁。
⇒ 把这 0.2% 全部列出来 = 拿到「火红实现汉化的全部逻辑」清单。

这比逐条猜「它怎么处理超短文本/等长块/宝可梦名」可靠得多：
每个补丁点上反汇编一下，就知道它打了什么钩子。

═══════════════════════════════════════════════════════════════════════════
【做法】
═══════════════════════════════════════════════════════════════════════════
1. 在 0x000000..0x6D0000（代码 + 低地址数据，即主文本区之前）逐字节比对
2. 把差异合并成连续 run
3. 过滤掉已确认的文本区/指针池（那些属于「改指针」，不是 hook）
4. 按 run 长度和地址分类打印，长的、落在代码区的优先

同时给出 Thumb 反汇编提示：
  · 若 run 里出现 `xx 4A` / `xx 48` 且附近有字面量池被改 → 改指针
  · 若 run 以 `bl`（FF F7 xx F8）跳向新区 → 打补丁

用法：python scripts/research/firered/18_code_diffs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

BASE = 0x08000000
SCAN_END = 0x6D0000          # 主文本区之前
MERGE_GAP = 8                 # 差异间隔 ≤8 字节合并成一个 run


def u32(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "little")


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    assert len(zh) == len(ja), "两版长度不同，不能用同偏移比对"

    print("=" * 76)
    print(f"火红代码区（0x000000..0x{SCAN_END:X}）逐字节差异")
    print("=" * 76)
    n = min(len(zh), len(ja))

    diffs = [i for i in range(SCAN_END) if zh[i] != ja[i]]
    print(f"差异字节总数：{len(diffs):,} / {SCAN_END:,}"
          f"（{len(diffs)/SCAN_END*100:.3f}%）")

    if not diffs:
        print("无差异")
        return 0

    # 合并成 run
    runs = []
    s = p = diffs[0]
    for i in diffs[1:]:
        if i - p <= MERGE_GAP:
            p = i
        else:
            runs.append((s, p))
            s = p = i
    runs.append((s, p))

    total_bytes = sum(e - s + 1 for s, e in runs)
    print(f"合并后 {len(runs):,} 个 run，覆盖 {total_bytes:,} 字节")

    # 按大小分布
    from collections import Counter
    sz = Counter()
    for s, e in runs:
        L = e - s + 1
        if L <= 4:
            sz["1-4"] += 1
        elif L <= 16:
            sz["5-16"] += 1
        elif L <= 64:
            sz["17-64"] += 1
        elif L <= 256:
            sz["65-256"] += 1
        else:
            sz["257+"] += 1
    print(f"  大小分布：{dict(sz)}")

    # ── 大 run（≥17 字节）优先：这些最像真补丁 ────────────────────
    big = [(s, e) for s, e in runs if e - s + 1 >= 17]
    print(f"\n{'='*76}")
    print(f"大 run（≥17 字节，最可能是真补丁）：{len(big)} 个，"
          f"共 {sum(e-s+1 for s,e in big):,} 字节")
    print(f"{'='*76}")
    for s, e in big[:40]:
        L = e - s + 1
        a = ja[s:e + 1]
        b = zh[s:e + 1]
        # 目标里是否出现指向新文本区的指针
        tgts = []
        for o in range(s, min(e + 1, n - 3)):
            v = u32(zh, o)
            if 0x086D0000 <= v - BASE < 0x08720000:
                tgts.append(v)
        hint = ""
        if tgts:
            uniq = sorted(set(tgts))[:3]
            hint = "  → 改指针: " + ", ".join(f"0x{v:08X}" for v in uniq)
        print(f"\n  0x{BASE+s:08X}  L={L}{hint}")
        print(f"    原: {a[:40].hex(' ')}{' …' if L > 40 else ''}")
        print(f"    汉: {b[:40].hex(' ')}{' …' if L > 40 else ''}")

    # ── 中等 run 只列表 ────────────────────────────────────────────
    mid = [(s, e) for s, e in runs if 5 <= e - s + 1 <= 16]
    print(f"\n{'='*76}")
    print(f"中等 run（5-16 字节）：{len(mid)} 个，以下全部列出地址")
    print(f"{'='*76}")
    line = []
    for s, e in mid:
        line.append(f"0x{BASE+s:07X}({e-s+1})")
        if len(line) == 6:
            print("  " + "  ".join(line))
            line = []
    if line:
        print("  " + "  ".join(line))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
